#!/usr/bin/env python3
# Copyright (c) 2026 Featuremine. All rights reserved.
#
# Featuremine Proprietary - Restricted Use.
#
# This file is not covered by the repository's MIT License.
# Use, copying, and modification are permitted only for use with local
# Featuremine Titan or Featuremine-owned hosted services. Retain this
# license and all original notices. Sharing and redistribution require
# prior written authorization from Featuremine.
#
# See LICENSE-RESTRICTED for the complete license terms.

"""Local demo strategy using Carnitas v031 reference, price and order streams."""

import argparse
import asyncio
import math
from pathlib import Path
import random
import struct
import sys
import time

import capnp
import msgpack

MAGIC = b"tcn v031"
HANDSHAKE = struct.Struct("<8sHHHH")
HEADER = struct.Struct("<BBHIqQ")
STREAM_ANNOUNCEMENT = 0
TRANSPORT_HEARTBEAT = 1
MANAGER_MESSAGE = 100
SYMBOLOGY = 101
VENUE_DATA = 102
RISK_DATA = 103
FMTRON = 108


def frame(kind, payload, sequence, timestamp, stream=0):
    """Encode a Carnitas frame; the checksum covers the header only."""
    header = HEADER.pack(0, kind, len(payload), sequence, timestamp, stream)
    return bytes([(-sum(header)) & 255]) + header[1:] + payload


async def read_frame(reader):
    """Read one complete frame regardless of TCP read boundaries."""
    header = await reader.readexactly(HEADER.size)
    if sum(header) & 255:
        raise RuntimeError("Invalid Carnitas header checksum")
    checksum, kind, size, sequence, timestamp, stream = HEADER.unpack(header)
    return kind, sequence, stream, await reader.readexactly(size)


def usable_quotes(fields):
    """Return executable sides with a finite price and at most one unit."""
    quotes = []
    # Buy at ask FID 25/size 735; sell at bid FID 22/size 730.
    for side, price_field, quantity_field in (("buy", 25, 735), ("sell", 22, 730)):
        price = fields.get(price_field)
        quantity = fields.get(quantity_field, 0)
        if (isinstance(price, (int, float)) and math.isfinite(price) and price > 0
                and isinstance(quantity, (int, float)) and math.isfinite(quantity) and quantity > 0):
            quotes.append((side, price, min(quantity, 1.0)))
    return quotes


def remaining_time(deadline):
    """Return the remaining phase budget or stop when it has expired."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeError("Operation timed out")
    return remaining


def update_position(execution, positions, order_fills):
    """Apply the change in an order's signed cumulative executed quantity."""
    event = execution.data.which()
    if event not in ("partiallyFilled", "filled", "correction", "bust", "status", "restated"):
        return
    try:
        cumulative = float(getattr(execution.data, event).cumQty)
    except (TypeError, ValueError, OverflowError) as error:
        raise RuntimeError("Invalid cumulative execution quantity") from error
    if not math.isfinite(cumulative) or cumulative < 0:
        raise RuntimeError("Invalid cumulative execution quantity")
    side = str(execution.orderSide)
    if side not in ("buy", "sell", "sellShort"):
        raise RuntimeError("Invalid execution side")
    signed = cumulative if side == "buy" else -cumulative
    key = (execution.accountID, execution.securityId, execution.strgOrdID)
    delta = signed - order_fills.get(key, 0)
    positions[key[:2]] = positions.get(key[:2], 0) + delta
    order_fills[key] = signed


async def main(args):
    """Recover reference/prices, send one IOC batch, then await terminal replies."""
    version = (1, 0, 11)
    strategy = capnp.load(str(args.schemas / "strategy.capnp"))
    reference = capnp.load(str(args.schemas / "reference.capnp"))
    if len(args.token) != 256 or not args.token.isascii():
        raise ValueError("Carnitas requires a 256-byte ASCII token")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError("Timeout must be positive and finite")
    token = args.token.encode("ascii")
    # Startup covers both connections, recovery, quote readiness and batch writes.
    deadline = time.monotonic() + args.timeout
    connections = []
    try:
        # Use separate order and market connections. Use one execution venue:
        # Titan routes this token's orders to its first venue.
        for port in (args.port, args.market_port):
            timeout = remaining_time(deadline)
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(args.host, port), timeout)
            connection = {"reader": reader, "writer": writer, "task": None,
                          "sequence": 0, "received": 0, "catchup": 0}
            connections.append(connection)
            # Recovery offset zero requests all history on this token's route.
            remaining_time(deadline)
            writer.write(HANDSHAKE.pack(MAGIC, *version, 264) + token + struct.pack("<Q", 0))
            timeout = remaining_time(deadline)
            await asyncio.wait_for(writer.drain(), timeout)
            timeout = remaining_time(deadline)
            hello = await asyncio.wait_for(reader.readexactly(32), timeout)
            magic, major, minor, patch, size = HANDSHAKE.unpack(hello[:16])
            # This sample requires an exact schema-version match on both services.
            if magic != MAGIC or (major, minor, patch) != version or size != 16:
                raise RuntimeError("Carnitas handshake or schema version mismatch")
            # Transport sequences and catch-up counts belong to each connection.
            connection["sequence"], connection["catchup"] = struct.unpack("<QQ", hello[16:])
        streams, securities, channels, prices = {}, {}, {}, {}
        accounts, mappings, attributes, positions = set(), set(), set(), {}
        # Keep reference seeds separate from replayed and live execution deltas.
        initial_positions, order_fills = {}, {}
        pending = set()
        orders_sent = False
        last_heartbeat = 0.0
        while True:
            remaining_time(deadline)
            now = time.monotonic()
            # Keep both connections active during recovery and order-response waits.
            if now - last_heartbeat >= 10:
                for connection in connections:
                    connection["sequence"] += 1
                    remaining_time(deadline)
                    connection["writer"].write(frame(
                        TRANSPORT_HEARTBEAT, b"", connection["sequence"], time.time_ns()))
                    timeout = remaining_time(deadline)
                    await asyncio.wait_for(connection["writer"].drain(), timeout)
                last_heartbeat = now
            for connection in connections:
                if connection["task"] is None:
                    connection["task"] = asyncio.create_task(read_frame(connection["reader"]))
            done, _ = await asyncio.wait(
                {connection["task"] for connection in connections},
                timeout=min(1, remaining_time(deadline)),
                return_when=asyncio.FIRST_COMPLETED)
            if not done:
                continue
            connection_index, connection = next((index, connection)
                for index, connection in enumerate(connections) if connection["task"] in done)
            kind, received_sequence, stream, payload = connection["task"].result()
            connection["task"] = None
            # Stream IDs are scoped to the connection that announced them.
            stream = (connection_index, stream)
            if kind == STREAM_ANNOUNCEMENT:
                if payload:
                    _, channel = payload.decode().split(":", 1)
                    streams[stream] = channel
                # Announcements do not count toward advertised catch-up totals.
                continue
            connection["received"] += 1
            # Reference schemas supply securities, quote channels and venue mappings.
            if kind == SYMBOLOGY:
                message = reference.Symbology.from_bytes_packed(payload)
                value = message.message
                if value.which() == "securityDefinition":
                    definition = value.securityDefinition
                    securities[definition.identifier] = definition.symbol
                elif value.which() == "riskChannel":
                    channels[value.riskChannel.referenceId] = value.riskChannel.channelName
            elif kind == VENUE_DATA:
                message = reference.VenueData.from_bytes_packed(payload)
                value = message.message
                if value.which() == "venueAccountMapping":
                    mappings.add((value.venueAccountMapping.identifier, value.venueAccountMapping.venueID))
                elif value.which() == "venueSecurityAttribute":
                    attributes.add((value.venueSecurityAttribute.securityId, value.venueSecurityAttribute.venueID))
            elif kind == RISK_DATA:
                message = reference.RiskData.from_bytes_packed(payload)
                value = message.message
                if value.which() == "account":
                    accounts.add(value.account.identifier)
                elif value.which() == "position":
                    # Reference updates replace the seed without erasing fill deltas.
                    key = (value.position.accountId, value.position.securityId)
                    new_seed = value.position.quantity
                    positions[key] = positions.get(key, 0) + (new_seed - initial_positions.get(key, 0))
                    initial_positions[key] = new_seed
            elif kind == FMTRON:
                if stream not in streams:
                    raise RuntimeError("fmtron message precedes stream announcement")
                # fmtron is a sequence of field/value objects, not a MessagePack map.
                decoder = msgpack.Unpacker(raw=False)
                decoder.feed(payload)
                values = list(decoder)
                if decoder.tell() != len(payload) or len(values) % 2:
                    raise RuntimeError("Incomplete fmtron field/value update")
                prices.setdefault(streams[stream], {}).update(zip(values[::2], values[1::2]))
            elif kind == MANAGER_MESSAGE:
                message = strategy.ManagerMessage.from_bytes_packed(payload)
                # This example ignores control replies, including ctrl.failed.
                if message.message.which() == "sess":
                    session = message.message.sess
                    if session.which() in ("exec", "exec2"):
                        execution = getattr(session, session.which())
                        update_position(execution, positions, order_fills)
                        if orders_sent:
                            event = execution.data.which()
                            print(f"Order update: {event}", flush=True)
                            # Forwarding acknowledgements do not complete an order.
                            if event in ("filled", "canceled", "rejected"):
                                pending.discard(execution.strgOrdID)
                    elif session.which() == "failed" and orders_sent:
                        raise RuntimeError("Fill model rejected an order request")
                    if orders_sent and not pending:
                        print("Done", flush=True)
                        return
            # Wait for both replays before selecting one batch from available mappings.
            if orders_sent or any(connection["received"] < connection["catchup"]
                                  for connection in connections):
                continue
            combinations = []
            # Each eligible account/security/venue combination gets a random usable side.
            for security, venue in sorted(attributes):
                quotes = usable_quotes(prices.get(channels.get(security), {}))
                if security not in securities or not quotes:
                    continue
                for account in sorted(accounts):
                    if (account, venue) in mappings:
                        side, price, quantity = random.choice(quotes)
                        combinations.append((account, security, venue, side, price, quantity))
            if not combinations:
                continue
            for account, security, venue, side, price, quantity in combinations:
                order_id = time.time_ns()
                # strategy.capnp defines the packed order request sent on the order socket.
                message = strategy.ManagerMessage.new_message()
                message.from_dict({
                    "message": {
                        "strg": {
                            "new": {
                                "strgOrdID": order_id,
                                "accountID": account,
                                "securityId": security,
                                "venueID": venue,
                                "orderSide": side,
                                "orderType": {"limit": price},
                                "quantity": quantity,
                                "maxFloor": {"none": None},
                                "timeInForce": "ioc",
                                "algorithm": {"dma": None}
                            }
                        }
                    }
                })
                connections[0]["sequence"] += 1
                remaining_time(deadline)
                connections[0]["writer"].write(frame(
                    MANAGER_MESSAGE, message.to_bytes_packed(), connections[0]["sequence"], time.time_ns()))
                pending.add(order_id)
            timeout = remaining_time(deadline)
            await asyncio.wait_for(connections[0]["writer"].drain(), timeout)
            orders_sent = True
            # --timeout bounds the response wait after the complete batch is written.
            deadline = time.monotonic() + args.timeout
            print(f"Placed {len(pending)} orders using live prices", flush=True)
    except asyncio.TimeoutError as error:
        raise RuntimeError("Operation timed out") from error
    finally:
        # Stop pending reader tasks before closing both sockets.
        tasks = [connection["task"] for connection in connections if connection["task"] is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for connection in connections:
            connection["writer"].close()
        try:
            await asyncio.wait_for(
                asyncio.gather(*(connection["writer"].wait_closed() for connection in connections),
                               return_exceptions=True),
                args.timeout)
        except asyncio.TimeoutError:
            for connection in connections:
                connection["writer"].transport.abort()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8032)
    parser.add_argument("--market-port", type=int, default=8033)
    parser.add_argument("--token", required=True, help="Order-entry token shown in Titan Profile configuration")
    parser.add_argument("--schemas", type=Path, default=Path(__file__).resolve().parent,
                        help="Schema directory (default: the directory containing this script)")
    parser.add_argument("--timeout", type=float, default=30,
                        help="Seconds allowed for startup and, separately, order responses (default: 30)")
    args = parser.parse_args()
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        pass
    except (OSError, RuntimeError, ValueError, asyncio.IncompleteReadError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
