#!/usr/bin/env python3
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
    for side, price_field, quantity_field in (("buy", 25, 735), ("sell", 22, 730)):
        price = fields.get(price_field)
        quantity = fields.get(quantity_field, 0)
        if (isinstance(price, (int, float)) and math.isfinite(price) and price > 0
                and isinstance(quantity, (int, float)) and math.isfinite(quantity) and quantity > 0):
            quotes.append((side, price, min(quantity, 1.0)))
    return quotes


async def main(args):
    """Recover reference/prices, send one IOC batch, then await terminal replies.

    Each mapped account/security/venue combination gets one random usable side.
    Positions are retrieved as a reference-data example, not used for sizing.
    Forwarding acknowledgements do not complete orders in this sample.

    Both connections request full history and match the complete schema version.
    Catch-up/data readiness has no overall timeout; connection and post-send
    response waits use --timeout. Empty heartbeat frames are sent every ten
    seconds. ctrl.failed is ignored; sess.failed stops the sample with an error.
    New runs create fresh IDs without managing orders from previous runs.
    See strategy.capnp for orders and reference.capnp for reference messages.
    Use one execution venue: Titan routes this token to its first venue.
    """
    version = capnp.load(str(args.schemas / "schemas_version.capnp"))
    expected = (version.schemasVersionMajor, version.schemasVersionMinor, version.schemasVersionPatch)
    strategy = capnp.load(str(args.schemas / "strategy.capnp"))
    reference = capnp.load(str(args.schemas / "reference.capnp"))
    if len(args.token) != 256 or not args.token.isascii():
        raise ValueError("Carnitas requires a 256-byte ASCII token")
    token = args.token.encode("ascii")
    connections = []
    try:
        for port in (args.port, args.market_port):
            reader, writer = await asyncio.wait_for(asyncio.open_connection(args.host, port), args.timeout)
            connection = {"reader": reader, "writer": writer, "task": None,
                          "sequence": 0, "received": 0, "catchup": 0}
            connections.append(connection)
            # Recovery offset zero requests all history on this token's route.
            writer.write(HANDSHAKE.pack(MAGIC, *expected, 264) + token + struct.pack("<Q", 0))
            await writer.drain()
            hello = await asyncio.wait_for(reader.readexactly(32), args.timeout)
            magic, major, minor, patch, size = HANDSHAKE.unpack(hello[:16])
            if magic != MAGIC or (major, minor, patch) != expected or size != 16:
                raise RuntimeError("Carnitas handshake or schema version mismatch")
            connection["sequence"], connection["catchup"] = struct.unpack("<QQ", hello[16:])
        streams, securities, channels, prices = {}, {}, {}, {}
        accounts, mappings, attributes, positions = set(), set(), set(), {}
        deadline = None
        pending = set()
        orders_sent = False
        last_heartbeat = 0.0
        while True:
            now = time.monotonic()
            if deadline is not None and now >= deadline:
                raise RuntimeError("Timed out waiting for order responses")
            if now - last_heartbeat >= 10:
                for connection in connections:
                    connection["sequence"] += 1
                    connection["writer"].write(frame(1, b"", connection["sequence"], time.time_ns()))
                    await connection["writer"].drain()
                last_heartbeat = now
            for connection in connections:
                if connection["task"] is None:
                    connection["task"] = asyncio.create_task(read_frame(connection["reader"]))
            done, _ = await asyncio.wait(
                {connection["task"] for connection in connections},
                timeout=1 if deadline is None else min(1, deadline - now),
                return_when=asyncio.FIRST_COMPLETED)
            if not done:
                continue
            connection_index, connection = next((index, connection)
                for index, connection in enumerate(connections) if connection["task"] in done)
            kind, received_sequence, stream, payload = connection["task"].result()
            connection["task"] = None
            stream = (connection_index, stream)
            if kind == 0:
                if payload:
                    _, channel = payload.decode().split(":", 1)
                    streams[stream] = channel
                continue
            connection["received"] += 1
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
                    positions[value.position.accountId, value.position.securityId] = value.position.quantity
            elif kind == FMTRON:
                if stream not in streams:
                    raise RuntimeError("fmtron message precedes stream announcement")
                decoder = msgpack.Unpacker(raw=False)
                decoder.feed(payload)
                values = list(decoder)
                if decoder.tell() != len(payload) or len(values) % 2:
                    raise RuntimeError("Incomplete fmtron field/value update")
                prices.setdefault(streams[stream], {}).update(zip(values[::2], values[1::2]))
            elif kind == 100 and orders_sent:
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
                if not pending:
                    print("Done", flush=True)
                    return
            # Announcement frames do not count toward advertised catch-up totals.
            if orders_sent or any(connection["received"] < connection["catchup"]
                                  for connection in connections):
                continue
            combinations = []
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
                while order_id in pending:
                    order_id += 1
                message = strategy.ManagerMessage.new_message()
                message.from_dict({"message": {"strg": {"new": {
                    "strgOrdID": order_id, "accountID": account, "securityId": security,
                    "venueID": venue, "orderSide": side, "orderType": {"limit": price},
                    "quantity": quantity, "maxFloor": {"none": None},
                    "timeInForce": "ioc", "algorithm": {"dma": None},
                }}}})
                connections[0]["sequence"] += 1
                connections[0]["writer"].write(frame(
                    100, message.to_bytes_packed(), connections[0]["sequence"], time.time_ns()))
                pending.add(order_id)
            await connections[0]["writer"].drain()
            orders_sent = True
            deadline = time.monotonic() + args.timeout
            print(f"Placed {len(pending)} orders using live prices", flush=True)
    finally:
        tasks = [connection["task"] for connection in connections if connection["task"] is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for connection in connections:
            connection["writer"].close()
        await asyncio.gather(*(connection["writer"].wait_closed() for connection in connections),
                             return_exceptions=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8032)
    parser.add_argument("--market-port", type=int, default=8033)
    parser.add_argument("--token", required=True, help="Order-entry token shown in Titan Profile configuration")
    parser.add_argument("--schemas", type=Path, default=Path(__file__).resolve().parent,
                        help="Schema directory (default: the directory containing this script)")
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        pass
    except (OSError, RuntimeError, ValueError, asyncio.IncompleteReadError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
