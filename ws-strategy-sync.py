#!/usr/bin/env python3
"""Synchronous WebSocket/REST example targeting random account positions."""

import json
from itertools import groupby
import random
from time import time_ns
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
import websocket as ws
import capnp # type: ignore[import-untyped]
import math
import argparse
from pathlib import Path

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

    # strategy.capnp defines the packed order and response messages.
    spec: Any = capnp.load(str(args.schemas / 'strategy.capnp'))

    # Retrieve token-visible accounts and venue/security mappings synchronously.
    # These REST calls have no timeout or retries; --timeout is not applied.
    scheme = "https" if args.tls else "http"
    response: requests.Response = requests.get(
        f"{scheme}://{args.host}:{args.reference_port}/accounts", headers={"authorization": args.token}
    )
    response.raise_for_status()
    accounts: List[int] = [entry["message"]["account"]["identifier"] for entry in response.json()]
    if not accounts:
        raise RuntimeError("Unable to find account definitions. Please reach out to FM team.")

    response = requests.get(
        f"{scheme}://{args.host}:{args.reference_port}/venues", headers={"authorization": args.token}
    )
    response.raise_for_status()
    venues: List[int] = [entry["message"]["venue"]["identifier"] for entry in response.json()]
    if not venues:
        raise RuntimeError("Unable to find venue definitions. Please reach out to FM team.")

    response = requests.get(
        f"{scheme}://{args.host}:{args.reference_port}/securities", headers={"authorization": args.token}
    )
    response.raise_for_status()
    securityDefinitions: Dict[int, Dict[str, Any]] = {
        entry["message"]["securityDefinition"]["identifier"] : entry["message"]["securityDefinition"]
        for entry in response.json()
    }
    if not securityDefinitions:
        raise RuntimeError("Unable to find security definitions. Please reach out to FM team.")

    response = requests.get(
        f"{scheme}://{args.host}:{args.reference_port}/venueSecurityAttributes", headers={"authorization": args.token}
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
        f"{scheme}://{args.host}:{args.reference_port}/venueAccountMappings", headers={"authorization": args.token}
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
        f"{scheme}://{args.host}:{args.reference_port}/positions", headers={"authorization": args.token}
    )
    response.raise_for_status()
    positions: Dict[Tuple[int, int], int] = {(entry["message"]["position"]["accountId"], entry["message"]["position"]["securityId"]): entry["message"]["position"]["quantity"] for entry in response.json()}

    supported: List[Tuple[int, int, int]] = []
    found: Set[int] = set()

    # This example sends GET with a body; returned quotes gate eligibility,
    # while order prices remain fixed at 10 rather than using bid/ask values.
    response = requests.get(
        f"{scheme}://{args.host}:{args.market_port}/api/prices",
        headers={"Content-Type": "text/plain; charset=us-ascii"},
        data="22 25\n" + "\n".join(str(secid) for secid in venueSecurityAttributes.keys()) + "\n"
    )
    response.raise_for_status()
    prices: Set[int] = set()
    for entry in response.text.split("\n"):
        secid, *rest = entry.split(" ")
        valid = False
        if rest:
            while len(rest) >= 2:
                pxid = rest.pop(0)
                pxval = rest.pop(0)
                if pxid == "22":
                    try:
                        px = float(pxval)
                        if not math.isnan(px):
                            valid = True
                    except ValueError:
                        pass
                elif pxid == "25":
                    try:
                        px = float(pxval)
                        if not math.isnan(px):
                            valid = True
                    except ValueError:
                        pass
        if valid:
            prices.add(int(secid))

    # Choose one venue and account for each security with an available quote.
    # Use one execution venue: Titan routes this token to its first venue.
    for security, securityVenues in venueSecurityAttributes.items():
        if security not in prices:
            continue
        venue: int = random.choice(securityVenues)
        venueAccounts: List[int] = venueAccountMappings.get(venue, [])
        if not venueAccounts:
            continue
        account: int = random.choice(venueAccounts)
        supported.append((account, venue, security))
        found.add(security)

    if not supported:
        raise RuntimeError("Unable to find valid combinations for order placement. Please reach out to FM team.")

    # Use one to 1,000 random combinations, bounded by the available mappings.
    chosen: List[Tuple[int, int, int]] = random.sample(supported, random.randint(1, min(1000, len(supported))))

    # Targets range from -999 to 1001 inclusive. A target may already equal the
    # recovered position, producing no order; sizing rounds target minus current.
    desired: Dict[Tuple[int, int], Tuple[int, int]] = {
        (account, security): ((1 + random.randint(-1000, 1000)), venue)
        for account, venue, security in chosen
    }
    filled: Dict[Tuple[int, int], float] = {}

    # WebSocket calls use the fixed ten-second timeout rather than --timeout.
    scheme = "wss" if args.tls else "ws"
    wsc: ws.WebSocket = ws.create_connection(
        url=f"{scheme}://{args.host}:{args.port}",
        header={"authorization": args.token},
        timeout=10.0,
    )

    try:
        # Read the recovery announcement before decoding its pending history.
        recovery: Dict[str, Any] = json.loads(wsc.recv())
        print(f"Recovering {recovery['pending']} messages")

        # Signed historical exec fills supplement the REST position snapshot.
        # This example does not include exec2 fills in position recovery.
        for _ in range(recovery["pending"]):
            msg: Any = spec.ManagerMessage.from_bytes_packed(wsc.recv())
            accountPosition: Any = None
            accountID: Optional[int] = None
            msgtype: str = msg.message.which()
            if msgtype == "sess" and msg.message.sess.which() == "exec":
                execmsg: Any = msg.message.sess.exec
                if not execmsg.accountID in accounts:
                    continue
                accountID = execmsg.accountID
                if not execmsg.securityId in found:
                    continue
                accountPosition = execmsg.accountPosition
                filltype: str = execmsg.data.which()
                if filltype in ("filled", "partiallyFilled"):
                    fill: Any = getattr(execmsg.data, filltype)
                    sign: int = 1 if execmsg.orderSide == "buy" else -1
                    key = (execmsg.accountID, execmsg.securityId)
                    filled[key] = filled.get(key, 0) + (sign * fill.lastQuantity)
            elif msgtype == "ctrl" and msg.message.ctrl.which() == "placeForwarded":
                placemsg: Any = msg.message.ctrl.placeForwarded
                if not placemsg.accountID in accounts:
                    continue
                accountID = placemsg.accountID
                accountPosition = placemsg.accountPosition

        orders: List[Tuple[bytes, float, float, int, int]] = []
        responses: Dict[str, Set[int]] = {
            "pending": set(),
            "failed": set(),
            "placeForwarded": set(),
        }

        # Combine the REST position snapshot with replayed fills before sizing.
        for key, val in desired.items():
            account, security = key
            target, venue = val
            current: float = positions.get(key, 0) + filled.get(key, 0)
            quantity: float = round(target - current)
            if quantity == 0:
                continue
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
                                "orderSide": "buy" if quantity > 0 else "sell",
                                # This example deliberately uses a fixed DAY limit.
                                "orderType": {"limit": 10},
                                "quantity": abs(quantity),
                                "maxFloor": {"none": None},
                                "timeInForce": "day",
                                "algorithm": {"dma": None},
                            }
                        }
                    }
                }
            )
            orders.append((msg.to_bytes_packed(), quantity, current, target, security))
            responses["pending"].add(strgordid)

        # Send the prepared orders as binary WebSocket messages.
        for order, quantity, current, target, security in orders:
            wsc.send(order, opcode=ws.ABNF.OPCODE_BINARY)
            secdef: Dict[str, Any] = securityDefinitions[security]
            symbology: str = ""
            if "equity" in secdef["assetClass"]:
                if 'isin' in secdef['assetClass']['equity']:
                    symbology += f" isin={secdef['assetClass']['equity']['isin']}"
                if 'sedol' in secdef['assetClass']['equity']:
                    symbology += f" sedol={secdef['assetClass']['equity']['sedol']}"
            if "bloombergId" in secdef:
                symbology += f" bloombergId={secdef['bloombergId']}"
            if "compositeFigi" in secdef:
                symbology += f" compositeFigi={secdef['compositeFigi']}"
            if symbology:
                symbology = f" ({symbology[1:]})"
            print(
                f"Placing {'buy' if quantity > 0 else 'sell'} {abs(quantity)} pos {current} target {target} for security {security}" + symbology
            )

        # Done means ctrl.placeForwarded or ctrl.failed (before forwarding).
        # Execution replies do not determine completion; DAY orders may remain.
        while len(responses["pending"]) > 0:
            msg = spec.ManagerMessage.from_bytes_packed(wsc.recv())
            msgtype = msg.message.which()
            if msgtype != "ctrl":
                continue
            ctrltype: str = msg.message.ctrl.which()
            if not ctrltype in ("placeForwarded", "failed"):
                continue
            strgordid = getattr(msg.message.ctrl, ctrltype).strgOrdID
            if not strgordid in responses["pending"]:
                continue
            responses["pending"].remove(strgordid)
            responses[ctrltype].add(strgordid)

        print("Order state:")
        print("Pending:", len(responses["pending"]))
        print("PlaceForwarded:", len(responses["placeForwarded"]))
        print("Failed:", len(responses["failed"]))
        print("Done")

    finally:
        wsc.close()
