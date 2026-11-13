#!/usr/bin/env python3
"""Local demo strategy using Titan WebSocket orders and REST reference/prices."""

import argparse
import asyncio
import json
import math
from pathlib import Path
import random
import sys
import time
import urllib.error
import urllib.request

import capnp
import websocket


def request(args, port, path, data=None):
    """Fetch one REST resource, returning None while its snapshot is loading."""
    scheme = "https" if args.tls else "http"
    headers = {"Authorization": args.token}
    if data is not None:
        headers["Content-Type"] = "text/plain; charset=us-ascii"
    message = urllib.request.Request(
        f"{scheme}://{args.host}:{port}{path}", data=data, headers=headers)
    try:
        with urllib.request.urlopen(message, timeout=args.timeout) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        if error.code == 503:
            return None
        raise RuntimeError(f"REST request failed (HTTP {error.code})") from error


def reference_data(args):
    """Load token-visible accounts and the mappings needed to place orders."""
    records = {}
    for path in ("securities", "accounts", "venueAccountMappings",
                 "venueSecurityAttributes", "positions"):
        body = request(args, args.reference_port, "/" + path)
        if body is None:
            return None
        records[path] = json.loads(body)
    securities = {int(record["message"]["securityDefinition"]["identifier"]):
                  record["message"]["securityDefinition"]["symbol"]
                  for record in records["securities"]}
    accounts = {int(record["message"]["account"]["identifier"])
                for record in records["accounts"]}
    mappings = {(int(record["message"]["venueAccountMapping"]["identifier"]),
                 int(record["message"]["venueAccountMapping"]["venueID"]))
                for record in records["venueAccountMappings"]}
    attributes = {(int(record["message"]["venueSecurityAttribute"]["securityId"]),
                   int(record["message"]["venueSecurityAttribute"]["venueID"]))
                  for record in records["venueSecurityAttributes"]}
    positions = {(int(record["message"]["position"]["accountId"]),
                  int(record["message"]["position"]["securityId"])):
                 int(record["message"]["position"]["quantity"])
                 for record in records["positions"]}
    return securities, accounts, mappings, attributes, positions


def price_data(args, securities):
    """Read bid/ask prices and quantities as alternating field/value pairs."""
    body = "22 25 730 735\n" + " ".join(str(identifier) for identifier in sorted(securities)) + "\n"
    response = request(args, args.market_port, "/api/prices", body.encode("ascii"))
    if response is None:
        return None
    prices = {}
    for line in response.decode("ascii").splitlines():
        values = line.split()
        if not values:
            continue
        identifier = int(values[0])
        if values[1:] == ["N/A"]:
            continue
        if len(values) % 2 != 1:
            raise RuntimeError("Incomplete REST field/value response")
        fields = prices.setdefault(identifier, {})
        for index in range(1, len(values), 2):
            if values[index + 1] != "N/A":
                fields[int(values[index])] = float(values[index + 1])
    return prices


def receive(connection):
    """Receive an application message while processing Ping/Pong frames."""
    while True:
        opcode, payload = connection.recv_data(control_frame=True)
        if opcode in (websocket.ABNF.OPCODE_PING, websocket.ABNF.OPCODE_PONG):
            continue
        if opcode == websocket.ABNF.OPCODE_CLOSE:
            raise RuntimeError("WebSocket connection closed")
        return opcode, payload


def recover(connection):
    """Consume the announced historical replies before placing a new batch."""
    opcode, payload = receive(connection)
    if opcode != websocket.ABNF.OPCODE_TEXT:
        raise RuntimeError("Missing WebSocket recovery information")
    snapshot = json.loads(payload)
    for field in ("received", "pending"):
        if type(snapshot.get(field)) is not int or snapshot[field] < 0:
            raise RuntimeError("Invalid WebSocket recovery information")
    connection.settimeout(None)
    for _ in range(snapshot["pending"]):
        opcode, _ = receive(connection)
        if opcode != websocket.ABNF.OPCODE_BINARY:
            raise RuntimeError("Invalid WebSocket recovery message")


def usable_quotes(fields):
    """Return executable sides with a finite price and at most one unit."""
    quotes = []
    for side, price_field, quantity_field in (("buy", 25, 735), ("sell", 22, 730)):
        price = fields.get(price_field)
        quantity = fields.get(quantity_field, 0)
        if (isinstance(price, (int, float)) and math.isfinite(price) and price > 0
                and isinstance(quantity, (int, float)) and math.isfinite(quantity) and quantity > 0):
            quotes.append((side, price, min(quantity, 1.0)))
    return quotes


async def main(args):
    """Recover replies, discover reference/prices and submit one IOC batch.

    Each mapped account/security/venue combination gets one random usable side.
    Positions demonstrate reference-data retrieval rather than order sizing.
    Continue through forwarding acknowledgements until every order is terminal.

    Historical replies are discarded, not used to reconstruct outstanding orders.
    There is no overall recovery/data-readiness deadline; --timeout bounds REST
    calls, connection setup and the post-send response wait. ctrl.failed is
    ignored; sess.failed stops the sample. New runs create fresh order IDs.
    See strategy.capnp for packed order and response messages. Use one execution
    venue: Titan routes this token to its first venue.
    """
    strategy = capnp.load(str(args.schemas / "strategy.capnp"))
    if len(args.token) != 256 or not args.token.isascii():
        raise ValueError("Titan requires a 256-byte ASCII token")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError("Timeout must be positive and finite")
    connection = None
    reader = None
    responses = asyncio.Queue()
    orders_sent = False

    async def read_responses():
        """Queue live replies concurrently, including replies during batch sends."""
        try:
            while True:
                opcode, payload = await asyncio.to_thread(receive, connection)
                if opcode != websocket.ABNF.OPCODE_BINARY:
                    raise RuntimeError("Unexpected WebSocket text message")
                if orders_sent:
                    responses.put_nowait(payload)
        except Exception as error:
            responses.put_nowait(error)

    try:
        scheme = "wss" if args.tls else "ws"
        connection = await asyncio.to_thread(
            websocket.create_connection, f"{scheme}://{args.host}:{args.port}",
            header={"Authorization": args.token}, timeout=args.timeout,
            enable_multithread=True)
        await asyncio.to_thread(recover, connection)
        reader = asyncio.create_task(read_responses())
        pending = set()
        while not orders_sent:
            if not responses.empty():
                raise responses.get_nowait()
            reference = await asyncio.to_thread(reference_data, args)
            if reference is None:
                continue
            securities, accounts, mappings, attributes, positions = reference
            identifiers = {security for security, venue in attributes if security in securities}
            if not identifiers or not accounts:
                continue
            prices = await asyncio.to_thread(price_data, args, identifiers)
            if prices is None:
                continue
            combinations = []
            for security, venue in sorted(attributes):
                quotes = usable_quotes(prices.get(security, {}))
                if security not in securities or not quotes:
                    continue
                for account in sorted(accounts):
                    if (account, venue) in mappings:
                        side, price, quantity = random.choice(quotes)
                        combinations.append((account, security, venue, side, price, quantity))
            if not combinations:
                continue
            if not responses.empty():
                raise responses.get_nowait()
            messages = []
            for account, security, venue, side, price, quantity in combinations:
                order_id = time.time_ns()
                while order_id in pending:
                    order_id += 1
                message = strategy.ManagerMessage.new_message()
                message.from_dict({"message": {"strg": {"new": {
                    "strgOrdID": order_id, "accountID": account, "securityId": security,
                    "venueID": venue, "orderSide": side, "orderType": {"limit": price},
                    "quantity": quantity, "maxFloor": {"none": None},
                    "timeInForce": "ioc", "algorithm": {"dma": None},
                }}}})
                pending.add(order_id)
                messages.append(message.to_bytes_packed())
            # Queue replies before sending any request: a local fill may arrive
            # while the rest of the batch is still being written.
            orders_sent = True
            for payload in messages:
                await asyncio.to_thread(connection.send, payload, websocket.ABNF.OPCODE_BINARY)
            deadline = time.monotonic() + args.timeout
            print(f"Placed {len(pending)} orders using live prices", flush=True)
        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("Timed out waiting for order responses")
            try:
                payload = await asyncio.wait_for(responses.get(), remaining)
            except asyncio.TimeoutError as error:
                raise RuntimeError("Timed out waiting for order responses") from error
            if isinstance(payload, Exception):
                raise payload
            message = strategy.ManagerMessage.from_bytes_packed(payload)
            if message.message.which() != "sess":
                continue
            session = message.message.sess
            if session.which() in ("exec", "exec2"):
                execution = getattr(session, session.which())
                event = execution.data.which()
                print(f"Order update: {event}", flush=True)
                if event in ("filled", "canceled", "rejected"):
                    pending.discard(execution.strgOrdID)
            elif session.which() == "failed":
                raise RuntimeError("Fill model rejected an order request")
        print("Done", flush=True)
    finally:
        if connection is not None:
            connection.abort()
        if reader is not None:
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)
        if connection is not None:
            await asyncio.to_thread(connection.close)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8034)
    parser.add_argument("--market-port", type=int, default=8035)
    parser.add_argument("--reference-port", type=int, default=8036)
    parser.add_argument("--token", required=True, help="Order-entry token shown in Titan Profile configuration")
    parser.add_argument("--schemas", type=Path, default=Path(__file__).resolve().parent,
                        help="Schema directory (default: the directory containing this script)")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--tls", action="store_true", help="Use WSS and HTTPS through a TLS endpoint")
    args = parser.parse_args()
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        pass
    except (OSError, urllib.error.URLError, websocket.WebSocketException):
        print("Network connection failed", file=sys.stderr)
        sys.exit(1)
    except (RuntimeError, ValueError, KeyError, TypeError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
