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

"""Synchronous WebSocket/REST example placing IOC orders from live quotes."""

import json
from itertools import groupby
import random
from time import monotonic, time_ns
from typing import Any, Dict, List, Set, Tuple

import requests
import websocket as ws
import capnp # type: ignore[import-untyped]
import math
import argparse
from pathlib import Path


def remaining_time(deadline):
    """Return the time left in the current startup or response phase."""
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise RuntimeError("Operation timed out")
    return remaining


def receive(connection, deadline):
    """Receive an application message without letting Ping/Pong reset the deadline."""
    while True:
        connection.settimeout(remaining_time(deadline))
        opcode, payload = connection.recv_data(control_frame=True)
        if opcode in (ws.ABNF.OPCODE_PING, ws.ABNF.OPCODE_PONG):
            continue
        if opcode == ws.ABNF.OPCODE_CLOSE:
            raise RuntimeError("WebSocket connection closed")
        return opcode, payload


def update_position(execution, positions, order_fills):
    """Apply the change in an order's cumulative fill during replay or live use."""
    event = execution.data.which()
    if event not in ("partiallyFilled", "filled", "correction", "bust", "status", "restated"):
        return
    try:
        quantity = float(getattr(execution.data, event).cumQty)
    except (TypeError, ValueError, OverflowError) as error:
        raise RuntimeError("Invalid cumulative execution quantity") from error
    if not math.isfinite(quantity) or quantity < 0:
        raise RuntimeError("Invalid cumulative execution quantity")
    side = str(execution.orderSide)
    if side not in ("buy", "sell", "sellShort"):
        raise RuntimeError("Invalid execution side")
    signed = quantity if side == "buy" else -quantity
    key = (execution.accountID, execution.securityId, execution.strgOrdID)
    delta = signed - order_fills.get(key, 0)
    positions[key[:2]] = positions.get(key[:2], 0) + delta
    order_fills[key] = signed


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8034)
    parser.add_argument("--market-port", type=int, default=8035)
    parser.add_argument("--reference-port", type=int, default=8036)
    parser.add_argument("--token", required=True, help="Order-entry token shown in Titan Profile configuration")
    parser.add_argument("--schemas", type=Path, default=Path(__file__).resolve().parent,
                        help="Schema directory (default: the directory containing this script)")
    parser.add_argument("--timeout", type=float, default=30,
                        help="Seconds allowed for startup and, separately, order responses (default: 30)")
    parser.add_argument("--tls", action="store_true", help="Use WSS and HTTPS through a TLS endpoint")
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError("Timeout must be positive and finite")
    deadline = monotonic() + args.timeout

    # strategy.capnp defines the packed order and response messages.
    spec: Any = capnp.load(str(args.schemas / 'strategy.capnp'))

    # Retrieve token-visible accounts and venue/security mappings synchronously.
    # Each request uses the remaining startup time, rather than restarting it.
    scheme = "https" if args.tls else "http"
    response: requests.Response = requests.get(
        f"{scheme}://{args.host}:{args.reference_port}/accounts", headers={"authorization": args.token},
        timeout=remaining_time(deadline),
    )
    response.raise_for_status()
    accounts: List[int] = [entry["message"]["account"]["identifier"] for entry in response.json()]
    if not accounts:
        raise RuntimeError("Unable to find account definitions. Please reach out to FM team.")

    response = requests.get(
        f"{scheme}://{args.host}:{args.reference_port}/venues", headers={"authorization": args.token},
        timeout=remaining_time(deadline),
    )
    response.raise_for_status()
    venues: List[int] = [entry["message"]["venue"]["identifier"] for entry in response.json()]
    if not venues:
        raise RuntimeError("Unable to find venue definitions. Please reach out to FM team.")

    response = requests.get(
        f"{scheme}://{args.host}:{args.reference_port}/securities", headers={"authorization": args.token},
        timeout=remaining_time(deadline),
    )
    response.raise_for_status()
    securityDefinitions: Dict[int, Dict[str, Any]] = {
        entry["message"]["securityDefinition"]["identifier"] : entry["message"]["securityDefinition"]
        for entry in response.json()
    }
    if not securityDefinitions:
        raise RuntimeError("Unable to find security definitions. Please reach out to FM team.")

    response = requests.get(
        f"{scheme}://{args.host}:{args.reference_port}/venueSecurityAttributes", headers={"authorization": args.token},
        timeout=remaining_time(deadline),
    )
    response.raise_for_status()
    venueSecurityAttributes: Dict[int, List[int]] = {
        security: list(set(venue for _, venue in group))
        for security, group in groupby(
            sorted(
                (entry["message"]["venueSecurityAttribute"]["securityId"], entry["message"]["venueSecurityAttribute"]["venueID"])
                for entry in response.json()
            ),
            key=lambda val: val[0]
        )
    }
    if not venueSecurityAttributes:
        raise RuntimeError("Unable to find venueSecurityAttributes. Please reach out to FM team.")

    response = requests.get(
        f"{scheme}://{args.host}:{args.reference_port}/venueAccountMappings", headers={"authorization": args.token},
        timeout=remaining_time(deadline),
    )
    response.raise_for_status()
    venueAccountMappings: Dict[int, List[int]] = {
        venue: list(set(account for _, account in group))
        for venue, group in groupby(
            sorted(
                (entry["message"]["venueAccountMapping"]["venueID"], entry["message"]["venueAccountMapping"]["identifier"])
                for entry in response.json()
            ),
            key=lambda val: val[0]
        )
    }
    if not venueAccountMappings:
        raise RuntimeError("Unable to find venueAccountMappings. Please reach out to FM team.")

    response = requests.get(
        f"{scheme}://{args.host}:{args.reference_port}/positions", headers={"authorization": args.token},
        timeout=remaining_time(deadline),
    )
    response.raise_for_status()
    # Reference positions are initial seeds; replay and live fills update them.
    initial_positions = {
        (int(entry["message"]["position"]["accountId"]),
         int(entry["message"]["position"]["securityId"])):
        int(entry["message"]["position"]["quantity"])
        for entry in response.json()
    }
    positions = dict(initial_positions)
    order_fills = {}

    supported: List[Tuple[int, int, int, str, float, float]] = []

    # Read the same bid/ask prices and quantities as the other examples.
    response = requests.get(
        f"{scheme}://{args.host}:{args.market_port}/api/prices",
        headers={"Content-Type": "text/plain; charset=us-ascii"},
        data="22 25 730 735\n" + "\n".join(str(secid) for secid in venueSecurityAttributes.keys()) + "\n",
        timeout=remaining_time(deadline),
    )
    response.raise_for_status()
    prices: Dict[int, Dict[int, float]] = {}
    for entry in response.text.splitlines():
        values = entry.split()
        if not values or values[1:] == ["N/A"]:
            continue
        if len(values) % 2 != 1:
            raise RuntimeError("Incomplete REST field/value response")
        fields = prices.setdefault(int(values[0]), {})
        for index in range(1, len(values), 2):
            if values[index + 1] != "N/A":
                fields[int(values[index])] = float(values[index + 1])

    # Choose a random usable side for each mapped account/security/venue.
    # Use one execution venue: Titan routes this token to its first venue.
    for security, securityVenues in sorted(venueSecurityAttributes.items()):
        if security not in securityDefinitions:
            continue
        fields = prices.get(security, {})
        quotes = []
        # Buys use ask price/quantity (25/735); sells use bid (22/730).
        for side, price_field, quantity_field in (("buy", 25, 735), ("sell", 22, 730)):
            price = fields.get(price_field)
            quantity = fields.get(quantity_field, 0)
            if (isinstance(price, (int, float)) and math.isfinite(price) and price > 0
                    and isinstance(quantity, (int, float)) and math.isfinite(quantity) and quantity > 0):
                quotes.append((side, price, min(quantity, 1.0)))
        if not quotes:
            continue
        for venue in sorted(securityVenues):
            for account in sorted(venueAccountMappings.get(venue, [])):
                if account in accounts:
                    side, price, quantity = random.choice(quotes)
                    supported.append((account, venue, security, side, price, quantity))

    if not supported:
        raise RuntimeError("Unable to find valid combinations for order placement. Please reach out to FM team.")

    # Connection setup and recovery share the remaining startup time.
    scheme = "wss" if args.tls else "ws"
    wsc: ws.WebSocket = ws.create_connection(
        url=f"{scheme}://{args.host}:{args.port}",
        header={"authorization": args.token},
        timeout=remaining_time(deadline),
    )

    try:
        # Read the recovery announcement for the number of pending replies.
        opcode, payload = receive(wsc, deadline)
        if opcode != ws.ABNF.OPCODE_TEXT:
            raise RuntimeError("Missing WebSocket recovery information")
        recovery: Dict[str, Any] = json.loads(payload)
        for field in ("received", "pending"):
            if type(recovery.get(field)) is not int or recovery[field] < 0:
                raise RuntimeError("Invalid WebSocket recovery information")
        # Recover positions without treating historical orders as this run's batch.
        for _ in range(recovery["pending"]):
            opcode, payload = receive(wsc, deadline)
            if opcode != ws.ABNF.OPCODE_BINARY:
                raise RuntimeError("Invalid WebSocket recovery message")
            msg = spec.ManagerMessage.from_bytes_packed(payload)
            if msg.message.which() == "sess":
                session = msg.message.sess
                if session.which() in ("exec", "exec2"):
                    update_position(getattr(session, session.which()), positions, order_fills)

        orders: List[bytes] = []
        pending: Set[int] = set()

        # Prepare the same IOC/DMA limit orders as the asynchronous examples.
        for account, venue, security, side, price, quantity in supported:
            msg = spec.ManagerMessage.new_message()
            strgordid: int = time_ns()
            msg.from_dict(
                {
                    "message": {
                        "strg": {
                            "new": {
                                "strgOrdID": strgordid,
                                "accountID": account,
                                "securityId": security,
                                "venueID": venue,
                                "orderSide": side,
                                "orderType": {"limit": price},
                                "quantity": quantity,
                                "maxFloor": {"none": None},
                                "timeInForce": "ioc",
                                "algorithm": {"dma": None},
                            }
                        }
                    }
                }
            )
            orders.append(msg.to_bytes_packed())
            pending.add(strgordid)

        # Send the prepared orders as binary WebSocket messages.
        for order in orders:
            wsc.settimeout(remaining_time(deadline))
            wsc.send(order, opcode=ws.ABNF.OPCODE_BINARY)
        # Start a fresh response budget once the complete batch has been sent.
        deadline = monotonic() + args.timeout
        print(f"Placed {len(pending)} orders using live prices", flush=True)

        # Forwarding alone does not complete an order; await terminal executions.
        while pending:
            opcode, payload = receive(wsc, deadline)
            if opcode != ws.ABNF.OPCODE_BINARY:
                raise RuntimeError("Unexpected WebSocket text message")
            msg = spec.ManagerMessage.from_bytes_packed(payload)
            if msg.message.which() != "sess":
                continue
            session = msg.message.sess
            if session.which() in ("exec", "exec2"):
                execution = getattr(session, session.which())
                event = execution.data.which()
                update_position(execution, positions, order_fills)
                print(f"Order update: {event}", flush=True)
                if event in ("filled", "canceled", "rejected"):
                    pending.discard(execution.strgOrdID)
            elif session.which() == "failed":
                raise RuntimeError("Fill model rejected an order request")
        print("Done", flush=True)

    finally:
        wsc.close()
