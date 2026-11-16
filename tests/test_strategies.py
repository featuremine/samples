"""Exercise sample behavior with synthetic records and in-memory transports."""

import asyncio
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import queue
import random
import runpy
import struct
import sys
import threading
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import capnp
import msgpack
import websocket


ROOT = Path(__file__).resolve().parents[1]


def load(filename):
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_"), ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tcp = load("tcp-strategy.py")
ws = load("ws-strategy.py")
strategy = capnp.load(str(ROOT / "strategy.capnp"))
reference = capnp.load(str(ROOT / "reference.capnp"))

def packed(schema, fields):
    message = schema.new_message()
    message.from_dict(fields)
    return message.to_bytes_packed()


def execution(order, event="filled", sequence=1):
    data = {"filled": {"lastQuantity": order["quantity"], "lastPrice": 100,
                       "cumQty": order["quantity"], "leaves": 0}}
    if event != "filled":
        data = {event: {"reason": "synthetic rejection"}}
    return packed(strategy.ManagerMessage, {"seqnum": sequence, "message": {"sess": {"exec": {
        "strgOrdID": order["strgOrdID"], "accountID": order["accountID"],
        "securityId": order["securityId"], "venueID": order["venueID"],
        "orderSide": order["orderSide"], "data": data,
    }}}})


def args():
    return SimpleNamespace(schemas=ROOT, token="t" * 256, host="localhost", port=1,
                           market_port=2, reference_port=3, timeout=2, tls=False)


def records():
    """Include both rich equity metadata and an instrument without those fields."""
    return {
        "accounts": [{"message": {"account": {"identifier": 1}}}],
        "venues": [{"message": {"venue": {"identifier": 1}}}],
        "securities": [
            {"message": {"securityDefinition": {"identifier": 1, "symbol": "TEST-A",
                "assetClass": {"equity": {"isin": "TEST-ISIN", "sedol": "TEST-SEDOL"}},
                "bloombergId": "TEST-BBG", "compositeFigi": "TEST-FIGI"}}},
            {"message": {"securityDefinition": {"identifier": 2, "symbol": "TEST-B",
                "assetClass": {"cryptoPair": {}}}}},
            {"message": {"securityDefinition": {"identifier": 3, "symbol": "TEST-C",
                "assetClass": {"cryptoPair": {}}}}},
        ],
        "venueSecurityAttributes": [{"message": {"venueSecurityAttribute": {
            "securityId": security, "venueID": 1}}} for security in (1, 2, 3)],
        "venueAccountMappings": [{"message": {"venueAccountMapping": {"identifier": 1, "venueID": 1}}}],
        "positions": [{"message": {"position": {"accountId": 1, "securityId": 1, "quantity": 1}}}],
    }


class QuoteTests(unittest.TestCase):
    def test_both_sides_use_the_opposite_quote_and_matching_size(self):
        for module in (tcp, ws):
            self.assertEqual(module.usable_quotes({22: 99, 730: 4, 25: 100, 735: 0.4}),
                             [("buy", 100, 0.4), ("sell", 99, 1.0)])

    def test_unusable_side_does_not_hide_a_usable_side(self):
        for module in (tcp, ws):
            for bad in (None, "bad", float("nan"), float("inf"), 0, -1):
                self.assertEqual(module.usable_quotes({22: 99, 730: 0.5, 25: bad, 735: 1}),
                                 [("sell", 99, 0.5)])
                self.assertEqual(module.usable_quotes({22: bad, 730: 1, 25: 100, 735: 0.5}),
                                 [("buy", 100, 0.5)])
                self.assertEqual(module.usable_quotes({25: 100, 735: bad}), [])
            self.assertEqual(module.usable_quotes({}), [])
            self.assertEqual(module.usable_quotes({25: 100}), [])

    def test_rest_requests_all_four_fields_and_preserves_missing_values(self):
        with patch.object(ws, "request", return_value=b"1 22 99 25 100 730 1 735 N/A\n2 N/A\n") as request:
            prices = ws.price_data(args(), {2, 1})
        self.assertEqual(request.call_args.args[3], b"22 25 730 735\n1 2\n")
        self.assertEqual(prices, {1: {22: 99, 25: 100, 730: 1}})

    def test_reference_reader_accepts_rich_and_minimal_metadata(self):
        fixture = records()
        with patch.object(ws, "request", side_effect=lambda _, port, path:
                          json.dumps(fixture[path.lstrip("/")]).encode()):
            securities, accounts, mappings, attributes, positions = ws.reference_data(args())
        self.assertEqual(set(securities), {1, 2, 3})
        self.assertEqual(accounts, {1})
        self.assertEqual(mappings, {(1, 1)})
        self.assertEqual(attributes, {(1, 1), (2, 1), (3, 1)})
        self.assertEqual(positions, {(1, 1): 1})


class TcpWriter:
    def __init__(self, reader):
        self.reader = reader
        self.orders = []

    def write(self, data):
        if len(data) == 280:
            return
        _, kind, _, _, _, _ = tcp.HEADER.unpack(data[:tcp.HEADER.size])
        if kind == tcp.MANAGER_MESSAGE:
            order = strategy.ManagerMessage.from_bytes_packed(data[tcp.HEADER.size:]).message.strg.new.to_dict()
            self.orders.append(order)
            # Reply immediately, before drain or the rest of the batch.
            self.reader.feed_data(tcp.frame(tcp.MANAGER_MESSAGE, execution(order), len(self.orders), 0, 9))

    async def drain(self):
        await asyncio.sleep(0)

    def close(self):
        pass

    async def wait_closed(self):
        pass


class TcpStrategyTests(unittest.TestCase):
    def test_batch_uses_both_sides_and_processes_immediate_replies(self):
        async def exercise():
            orders_reader, market_reader = asyncio.StreamReader(), asyncio.StreamReader()
            orders_writer, market_writer = TcpWriter(orders_reader), TcpWriter(market_reader)
            snapshots = []
            def add(kind, schema, field):
                snapshots.append(tcp.frame(kind, packed(schema, {"message": field}), len(snapshots) + 1, 0))
            add(tcp.SYMBOLOGY, reference.Symbology, {"securityDefinition": {"identifier": 1, "symbol": "TEST"}})
            add(tcp.SYMBOLOGY, reference.Symbology, {"riskChannel": {"referenceId": 1, "channelName": "quotes/test"}})
            add(tcp.VENUE_DATA, reference.VenueData, {"venueSecurityAttribute": {"securityId": 1, "venueID": 1}})
            for account in (1, 2):
                add(tcp.RISK_DATA, reference.RiskData, {"account": {"identifier": account}})
                add(tcp.VENUE_DATA, reference.VenueData, {"venueAccountMapping": {"identifier": account, "venueID": 1}})
            hello = tcp.HANDSHAKE.pack(tcp.MAGIC, 1, 0, 11, 16)
            orders_reader.feed_data(hello + struct.pack("<QQ", 0, len(snapshots)) + b"".join(snapshots))
            fields = {22: 99, 730: 4, 25: 100, 735: 0.4}
            payload = b"".join(msgpack.packb(value) for pair in fields.items() for value in pair)
            market_reader.feed_data(hello + struct.pack("<QQ", 0, 1)
                + tcp.frame(tcp.STREAM_ANNOUNCEMENT, b"fixture:quotes/test", 0, 0, 1)
                + tcp.frame(tcp.FMTRON, payload, 1, 0, 1))
            choices = iter((0, 1))
            with patch.object(tcp.asyncio, "open_connection", side_effect=[
                    (orders_reader, orders_writer), (market_reader, market_writer)]), \
                    patch.object(random, "choice", side_effect=lambda values: values[next(choices)]), \
                    patch.object(tcp.time, "time_ns", return_value=100):
                await asyncio.wait_for(tcp.main(args()), 3)
            return orders_writer.orders
        with redirect_stdout(io.StringIO()) as output:
            orders = asyncio.run(exercise())
        self.assertEqual([order["orderSide"] for order in orders], ["buy", "sell"])
        self.assertEqual([order["orderType"]["limit"] for order in orders], [100, 99])
        self.assertEqual([order["quantity"] for order in orders], [0.4, 1])
        self.assertEqual(len({order["strgOrdID"] for order in orders}), 2)
        self.assertTrue(all(order["timeInForce"] == "ioc" for order in orders))
        self.assertIn("Done", output.getvalue())


class WebSocketFixture:
    def __init__(self):
        self.messages = queue.Queue()
        self.orders = []
        self.messages.put((websocket.ABNF.OPCODE_TEXT, json.dumps({"received": 0, "pending": 0}), None))

    def recv_data(self, control_frame=True):
        item = self.messages.get(timeout=3)
        if isinstance(item, Exception):
            raise item
        opcode, payload, consumed = item
        if consumed is not None:
            consumed.set()
        return opcode, payload

    def settimeout(self, timeout):
        pass

    def send(self, payload, opcode):
        order = strategy.ManagerMessage.from_bytes_packed(payload).message.strg.new.to_dict()
        self.orders.append(order)
        consumed = threading.Event()
        self.messages.put((websocket.ABNF.OPCODE_BINARY, execution(order), consumed))
        if not consumed.wait(2):
            raise RuntimeError("Fixture reply was not received during batch sending")

    def abort(self):
        self.messages.put(RuntimeError("Fixture closed"))

    def close(self):
        pass


class WebSocketStrategyTests(unittest.TestCase):
    def test_both_sides_and_replies_arriving_before_batch_send_finishes(self):
        connection = WebSocketFixture()
        reference_data = ({1: "TEST"}, {1, 2}, {(1, 1), (2, 1)}, {(1, 1)}, {})
        prices = {1: {22: 99, 730: 4, 25: 100, 735: 0.4}}
        choices = iter((0, 1))
        with patch.object(ws.websocket, "create_connection", return_value=connection), \
                patch.object(ws, "reference_data", return_value=reference_data), \
                patch.object(ws, "price_data", return_value=prices), \
                patch.object(random, "choice", side_effect=lambda values: values[next(choices)]), \
                patch.object(ws.time, "time_ns", return_value=100), redirect_stdout(io.StringIO()) as output:
            asyncio.run(asyncio.wait_for(ws.main(args()), 5))
        self.assertEqual([order["orderSide"] for order in connection.orders], ["buy", "sell"])
        self.assertEqual([order["orderType"]["limit"] for order in connection.orders], [100, 99])
        self.assertEqual([order["quantity"] for order in connection.orders], [0.4, 1])
        self.assertEqual(len({order["strgOrdID"] for order in connection.orders}), 2)
        self.assertIn("Done", output.getvalue())


class SynchronousStrategyTests(unittest.TestCase):
    def exercise(self, targets=(3, -3), prices="1 22 99 25 100\n2 22 50\n3 N/A\n"):
        fixture = records()
        sent = []
        history = execution({"strgOrdID": 99, "accountID": 1, "securityId": 1,
                             "venueID": 1, "orderSide": "buy", "quantity": 1})
        incoming = [json.dumps({"received": 1, "pending": 1}), history]
        class Response:
            def __init__(self, body):
                self.body = body
                self.text = body if isinstance(body, str) else json.dumps(body)
            def json(self):
                return self.body
            def raise_for_status(self):
                pass
        def get(url, **kwargs):
            return Response(prices if url.endswith("/api/prices") else fixture[url.rsplit("/", 1)[1]])
        def send(payload, opcode):
            order = strategy.ManagerMessage.from_bytes_packed(payload).message.strg.new.to_dict()
            sent.append(order)
            event = "placeForwarded" if len(sent) == 1 else "failed"
            incoming.append(packed(strategy.ManagerMessage, {"message": {"ctrl": {
                event: {"strgOrdID": order["strgOrdID"]}}}}))
        connection = SimpleNamespace(recv=lambda: incoming.pop(0), send=send, close=lambda: None)
        requests = ModuleType("requests")
        requests.Response = Response
        requests.get = get
        with patch.dict(sys.modules, {"requests": requests}), \
                patch.object(sys, "argv", ["ws-strategy-sync.py", "--token", "t" * 256]), \
                patch.object(websocket, "create_connection", return_value=connection), \
                patch.object(random, "choice", side_effect=lambda values: values[0]), \
                patch.object(random, "sample", side_effect=lambda values, count: values), \
                patch.object(random, "randint", side_effect=[2, *targets]), \
                patch("time.time_ns", side_effect=[100, 101]), redirect_stdout(io.StringIO()) as output:
            runpy.run_path(str(ROOT / "ws-strategy-sync.py"), run_name="__main__")
        return sent, output.getvalue()

    def test_price_filter_recovery_sizing_and_forwarding_completion(self):
        orders, output = self.exercise()
        self.assertEqual([order["securityId"] for order in orders], [1, 2])
        self.assertEqual([order["orderSide"] for order in orders], ["buy", "sell"])
        self.assertEqual([order["quantity"] for order in orders], [2, 2])
        self.assertTrue(all(order["timeInForce"] == "day"
                            and order["orderType"]["limit"] == 10 for order in orders))
        self.assertIn("PlaceForwarded: 1", output)
        self.assertIn("Failed: 1", output)
        self.assertIn("Done", output)

    def test_already_reached_targets_send_no_orders(self):
        orders, output = self.exercise(targets=(1, -1))
        self.assertEqual(orders, [])
        self.assertIn("Done", output)


if __name__ == "__main__":
    unittest.main()
