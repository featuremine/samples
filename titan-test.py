#!/usr/bin/env python3
"""Run a bounded, seeded order-flow check against a local Titan fixture.

Use --fixture FILE --transport tcp|websocket --seed N --orders N --verbose.
The fixture JSON supplies host, token, tcp_orders_port, tcp_market_port,
websocket_port, rest_market_port, and rest_reference_port; schemas is optional.
Only loopback endpoints are accepted. Keep synthetic credentials in that file,
or pass --fixture - to read JSON from stdin. Logs omit connection identities.

The integration test starts Titan's titan_test_fixture executable, substitutes
local quotes for the external feed, and runs both transports against the real
gateways and execution service. Set TITAN_TEST_FIXTURE to that executable when
running unittest discovery in tests/. Success prints a JSON completion summary.
"""

import argparse
import asyncio
import importlib.util
import ipaddress
import json
import math
from pathlib import Path
import random
import struct
import sys
import time
from types import SimpleNamespace
import urllib.request

import capnp
import msgpack
import websocket


def load_sample(filename):
    """Import a sibling sample without executing its command-line entry point."""
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_"),
                                                Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tcp = load_sample("tcp-strategy.py")
ws = load_sample("ws-strategy.py")


class TestFailure(RuntimeError):
    """A validation failure whose message contains no fixture identifiers."""


class FixtureSettings(SimpleNamespace):
    """Give each blocking REST call only the remaining overall time budget."""

    @property
    def timeout(self):
        remaining = self.deadline - time.monotonic()
        require(remaining > 0, "Local test deadline expired")
        return remaining


def require(condition, message):
    """Raise a controlled, safe-to-log failure."""
    if not condition:
        raise TestFailure(message)


class OrderTracker:
    """Check each output channel and correlate only this run's order replies."""

    def __init__(self, schema, verbose=False):
        self.schema = schema
        self.verbose = verbose
        self.sequences = {}
        self.orders = {}

    def add(self, identifier, order):
        """Register before sending, so immediate local replies can be checked."""
        self.orders[identifier] = dict(order, ordinal=len(self.orders) + 1,
                                       cumulative=0.0, terminal=False)

    @property
    def completed(self):
        return sum(order["terminal"] for order in self.orders.values())

    def observe(self, payload, channel, historical=False):
        """Validate application sequence numbers independently for each channel."""
        message = self.schema.ManagerMessage.from_bytes_packed(payload)
        sequence = int(message.seqnum)
        require(sequence == self.sequences.get(channel, 0) + 1,
                "Nonconsecutive application sequence on an output channel")
        self.sequences[channel] = sequence
        if historical:
            return
        value = message.message
        if value.which() == "ctrl":
            control = value.ctrl
            if control.which() in ("failed", "placeForwarded"):
                reply = getattr(control, control.which())
                order = self.orders.get(reply.strgOrdID)
                if order is not None:
                    require(control.which() != "failed", "An order request failed before forwarding")
                    require(reply.accountID == order["accountID"], "Forwarding account mismatch")
                    require(reply.venueID == order["venueID"], "Forwarding venue mismatch")
                    require(math.isclose(reply.quantity, order["quantity"], abs_tol=1e-9),
                            "Forwarded quantity mismatch")
            return
        if value.which() != "sess":
            return
        session = value.sess
        require(session.which() != "failed", "An order request failed at the execution session")
        if session.which() not in ("exec", "exec2"):
            return
        execution = getattr(session, session.which())
        order = self.orders.get(execution.strgOrdID)
        if order is None:
            return
        require(not order["terminal"], "Execution received after terminal order state")
        require(execution.accountID == order["accountID"]
                and execution.securityId == order["securityId"]
                and execution.venueID == order["venueID"], "Execution identity mismatch")
        require(str(execution.orderSide) == order["orderSide"], "Execution side mismatch")
        event = execution.data.which()
        detail = getattr(execution.data, event)
        if event == "placed":
            require(math.isclose(float(detail.orderQuantity), order["quantity"], abs_tol=1e-9),
                    "Placed quantity mismatch")
        elif event in ("filled", "partiallyFilled"):
            last, price, cumulative, leaves = map(float, (
                detail.lastQuantity, detail.lastPrice, detail.cumQty, detail.leaves))
            require(all(math.isfinite(number) for number in (last, price, cumulative, leaves)),
                    "Nonfinite fill values")
            require(last > 0 and price > 0 and leaves >= 0, "Invalid fill or remaining quantity")
            require(order["cumulative"] <= cumulative <= order["quantity"] + 1e-9,
                    "Cumulative fill outside order bounds")
            require(math.isclose(cumulative, order["cumulative"] + last, abs_tol=1e-9),
                    "Cumulative fill does not match individual fills")
            require(math.isclose(cumulative + leaves, order["quantity"], abs_tol=1e-9),
                    "Fill and remaining quantity do not match order quantity")
            require(price <= order["price"] + 1e-9 if order["orderSide"] == "buy"
                    else price >= order["price"] - 1e-9, "Fill violates limit price")
            order["cumulative"] = cumulative
            # An IOC partial fill can be followed by cancellation of its remainder.
            order["terminal"] = leaves == 0
        elif event == "canceled":
            leaves, canceled = float(detail.leaves), float(detail.quantity)
            require(math.isfinite(leaves) and math.isfinite(canceled)
                    and leaves >= 0 and canceled >= 0, "Invalid cancellation quantities")
            require(math.isclose(order["cumulative"] + canceled + leaves,
                                 order["quantity"], abs_tol=1e-9),
                    "Canceled quantity does not match remaining order quantity")
            require(leaves == 0, "Canceled IOC order still has a remaining quantity")
            order["terminal"] = True
        elif event == "rejected":
            raise TestFailure("A generated valid order was rejected")
        if self.verbose:
            print(f"Order {order['ordinal']}: {event}", flush=True)


def combinations(reference, prices):
    """Select authorized account/security/venue combinations with usable quotes."""
    securities, accounts, mappings, attributes, _ = reference
    result = []
    for security, venue in sorted(attributes):
        quotes = ws.usable_quotes(prices.get(security, {}))
        if security in securities and quotes:
            for account in sorted(accounts):
                if (account, venue) in mappings:
                    result.append((account, security, venue, quotes))
    return result


def make_orders(schema, choices, count, rng, tracker):
    """Generate reproducible IOC requests; actual order IDs remain run-unique."""
    require(bool(choices), "No usable account/security/venue combinations")
    identifier = time.time_ns()
    messages = []
    for index in range(count):
        account, security, venue, quotes = rng.choice(choices)
        side, price, available = rng.choice(quotes)
        quantity = available * rng.uniform(0.1, 1.0)
        order = {"accountID": account, "securityId": security, "venueID": venue,
                 "orderSide": side, "price": price, "quantity": quantity}
        tracker.add(identifier + index, order)
        message = schema.ManagerMessage.new_message()
        message.from_dict({"message": {"strg": {"new": {
            "strgOrdID": identifier + index, "accountID": account,
            "securityId": security, "venueID": venue, "orderSide": side,
            "orderType": {"limit": price}, "quantity": quantity,
            "maxFloor": {"none": None}, "timeInForce": "ioc", "algorithm": {"dma": None},
        }}}})
        messages.append(message.to_bytes_packed())
        if tracker.verbose:
            print(f"Order {index + 1}: submit {side} quantity={quantity:.8g}", flush=True)
    return messages


async def websocket_check(args, fixture, schema, tracker):
    """Exercise real local WebSocket and REST services using the sample helpers."""
    settings = FixtureSettings(host=fixture["host"], token=fixture["token"], tls=False,
                               deadline=args.deadline, reference_port=fixture["rest_reference_port"],
                               market_port=fixture["rest_market_port"])
    connection = await asyncio.to_thread(
        websocket.create_connection,
        f"ws://{settings.host}:{fixture['websocket_port']}",
        header={"Authorization": settings.token}, timeout=settings.timeout,
        enable_multithread=True, http_no_proxy=[settings.host])
    try:
        opcode, payload = await asyncio.to_thread(ws.receive, connection)
        require(opcode == websocket.ABNF.OPCODE_TEXT, "Missing WebSocket recovery announcement")
        snapshot = json.loads(payload)
        require(all(type(snapshot.get(field)) is int and snapshot[field] >= 0
                    for field in ("received", "pending")), "Invalid WebSocket recovery counts")
        for _ in range(snapshot["pending"]):
            opcode, payload = await asyncio.to_thread(ws.receive, connection)
            require(opcode == websocket.ABNF.OPCODE_BINARY, "Invalid historical WebSocket frame")
            tracker.observe(payload, "orders", historical=True)
        choices = []
        while not choices:
            reference = await asyncio.to_thread(ws.reference_data, settings)
            if reference is not None:
                prices = await asyncio.to_thread(ws.price_data, settings, reference[0])
                if prices is not None:
                    choices = combinations(reference, prices)
            if not choices:
                await asyncio.sleep(0.01)
        for payload in make_orders(schema, choices, args.orders, random.Random(args.seed), tracker):
            await asyncio.to_thread(connection.send, payload, websocket.ABNF.OPCODE_BINARY)
        while tracker.completed < args.orders:
            opcode, payload = await asyncio.to_thread(ws.receive, connection)
            require(opcode == websocket.ABNF.OPCODE_BINARY, "Unexpected live WebSocket text frame")
            tracker.observe(payload, "orders")
    finally:
        connection.abort()
        await asyncio.to_thread(connection.close)


async def tcp_check(args, fixture, schema, tracker):
    """Recover both Carnitas services and validate each announced output separately."""
    version = (1, 0, 11)
    reference_schema = capnp.load(str(args.schemas / "reference.capnp"))
    connections = []
    streams, securities, channels, prices = {}, {}, {}, {}
    accounts, mappings, attributes = set(), set(), set()
    try:
        for name in ("tcp_orders_port", "tcp_market_port"):
            reader, writer = await asyncio.open_connection(fixture["host"], fixture[name])
            state = {"reader": reader, "writer": writer, "task": None, "received": 0}
            connections.append(state)
            writer.write(tcp.HANDSHAKE.pack(tcp.MAGIC, *version, 264)
                         + fixture["token"].encode("ascii") + struct.pack("<Q", 0))
            await writer.drain()
            hello = await reader.readexactly(32)
            require(tcp.HANDSHAKE.unpack(hello[:16]) == (tcp.MAGIC, *version, 16),
                    "Carnitas handshake or schema mismatch")
            state["sequence"], state["catchup"] = struct.unpack("<QQ", hello[16:])
        sent = False
        choices = []
        while tracker.completed < args.orders:
            for state in connections:
                if state["task"] is None:
                    state["task"] = asyncio.create_task(tcp.read_frame(state["reader"]))
            done, _ = await asyncio.wait({state["task"] for state in connections},
                                         return_when=asyncio.FIRST_COMPLETED)
            index, state = next((index, state) for index, state in enumerate(connections)
                                if state["task"] in done)
            kind, _, stream, payload = state["task"].result()
            state["task"] = None
            channel = (index, stream)
            if kind == tcp.STREAM_ANNOUNCEMENT:
                if payload:
                    streams[channel] = payload.decode().split(":", 1)[1]
                continue
            state["received"] += 1
            if kind == tcp.MANAGER_MESSAGE:
                tracker.observe(payload, channel, historical=not sent)
            elif kind == tcp.SYMBOLOGY:
                value = reference_schema.Symbology.from_bytes_packed(payload).message
                if value.which() == "securityDefinition":
                    securities[value.securityDefinition.identifier] = value.securityDefinition.symbol
                elif value.which() == "riskChannel":
                    channels[value.riskChannel.referenceId] = value.riskChannel.channelName
            elif kind == tcp.RISK_DATA:
                value = reference_schema.RiskData.from_bytes_packed(payload).message
                if value.which() == "account":
                    accounts.add(value.account.identifier)
            elif kind == tcp.VENUE_DATA:
                value = reference_schema.VenueData.from_bytes_packed(payload).message
                if value.which() == "venueAccountMapping":
                    mappings.add((value.venueAccountMapping.identifier, value.venueAccountMapping.venueID))
                elif value.which() == "venueSecurityAttribute":
                    attributes.add((value.venueSecurityAttribute.securityId, value.venueSecurityAttribute.venueID))
            elif kind == tcp.FMTRON:
                require(channel in streams, "Price record precedes channel announcement")
                decoder = msgpack.Unpacker(raw=False)
                decoder.feed(payload)
                values = list(decoder)
                require(decoder.tell() == len(payload) and len(values) % 2 == 0,
                        "Incomplete Carnitas price record")
                prices.setdefault(streams[channel], {}).update(zip(values[::2], values[1::2]))
            if not sent and all(item["received"] >= item["catchup"] for item in connections):
                by_security = {security: prices.get(channels.get(security), {}) for security in securities}
                choices = combinations((securities, accounts, mappings, attributes, {}), by_security)
                if choices:
                    for payload in make_orders(schema, choices, args.orders, random.Random(args.seed), tracker):
                        connections[0]["sequence"] += 1
                        connections[0]["writer"].write(tcp.frame(
                            tcp.MANAGER_MESSAGE, payload, connections[0]["sequence"], time.time_ns()))
                    await connections[0]["writer"].drain()
                    sent = True
    finally:
        tasks = [state["task"] for state in connections if state["task"] is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for state in connections:
            state["writer"].close()
        await asyncio.gather(*(state["writer"].wait_closed() for state in connections),
                             return_exceptions=True)


async def run(args, fixture):
    """Reject nonlocal endpoints before opening any connection."""
    host = fixture.get("host")
    try:
        local = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except (ValueError, TypeError):
        local = False
    require(local, "The tester requires a loopback fixture host")
    # Proxy environment settings must never redirect fixture traffic off-machine.
    urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
    token = fixture.get("token")
    require(isinstance(token, str) and len(token) == 256 and token.isascii() and "\0" not in token,
            "Invalid fixture order-entry token")
    ports = (("tcp_orders_port", "tcp_market_port") if args.transport == "tcp"
             else ("websocket_port", "rest_market_port", "rest_reference_port"))
    require(all(type(fixture.get(name)) is int and 1 <= fixture[name] <= 65535 for name in ports),
            "Invalid fixture service port")
    args.schemas = Path(fixture.get("schemas", Path(__file__).resolve().parent))
    schema = capnp.load(str(args.schemas / "strategy.capnp"))
    tracker = OrderTracker(schema, args.verbose)
    operation = tcp_check if args.transport == "tcp" else websocket_check
    args.deadline = time.monotonic() + args.timeout
    await asyncio.wait_for(operation(args, fixture, schema, tracker), args.timeout)
    return {"status": "passed", "transport": args.transport, "seed": args.seed,
            "submitted": len(tracker.orders), "completed": tracker.completed}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True, help="Local synthetic fixture JSON, or - for stdin")
    parser.add_argument("--transport", choices=("tcp", "websocket"), required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--orders", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    try:
        require(args.orders > 0 and math.isfinite(args.timeout) and args.timeout > 0,
                "Order count and timeout must be positive and finite")
        if args.fixture == "-":
            fixture = json.load(sys.stdin)
        else:
            with open(args.fixture, encoding="utf-8") as source:
                fixture = json.load(source)
        print(json.dumps(asyncio.run(run(args, fixture))), flush=True)
    except TestFailure as error:
        print(json.dumps({"status": "failed", "reason": str(error)}), file=sys.stderr)
        sys.exit(1)
    except asyncio.TimeoutError:
        print(json.dumps({"status": "failed", "reason": "Local test deadline expired"}), file=sys.stderr)
        sys.exit(1)
    except Exception:
        # Third-party errors may include URLs or authentication headers.
        print(json.dumps({"status": "failed", "reason": "Local fixture or transport error"}), file=sys.stderr)
        sys.exit(1)
