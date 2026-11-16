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

"""Check the randomized tester's invariants without opening sockets."""

import asyncio
import importlib.util
from pathlib import Path
import random
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import capnp


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("titan_test", ROOT / "titan-test.py")
tester = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tester)
schema = capnp.load(str(ROOT / "strategy.capnp"))


def reply(sequence, data, **changes):
    execution = {"strgOrdID": 1, "accountID": 1, "securityId": 1, "venueID": 1,
                 "orderSide": "buy", "data": data}
    execution.update(changes)
    message = schema.ManagerMessage.new_message()
    message.from_dict({"seqnum": sequence, "message": {"sess": {"exec": execution}}})
    return message.to_bytes_packed()


class TrackerTests(unittest.TestCase):
    def tracker(self):
        tracker = tester.OrderTracker(schema)
        tracker.add(1, {"accountID": 1, "securityId": 1, "venueID": 1,
                        "orderSide": "buy", "price": 100, "quantity": 1})
        return tracker

    def test_sequence_numbers_are_independent_per_output_channel(self):
        tracker = self.tracker()
        tracker.observe(reply(1, {"pendingNew": None}), "first", historical=True)
        tracker.observe(reply(1, {"pendingNew": None}), "second", historical=True)
        tracker.observe(reply(2, {"pendingNew": None}), "first", historical=True)
        with self.assertRaisesRegex(tester.TestFailure, "Nonconsecutive"):
            tracker.observe(reply(4, {"pendingNew": None}), "first", historical=True)

    def test_partial_fill_then_cancel_balances_original_quantity(self):
        tracker = self.tracker()
        tracker.observe(reply(1, {"placed": {"orderQuantity": 1}}), "orders")
        tracker.observe(reply(2, {"partiallyFilled": {
            "lastQuantity": 0.3, "lastPrice": 99, "cumQty": 0.3, "leaves": 0.7}}), "orders")
        self.assertEqual(tracker.completed, 0)
        tracker.observe(reply(3, {"canceled": {"quantity": 0.7, "leaves": 0}}), "orders")
        self.assertEqual(tracker.completed, 1)
        with self.assertRaisesRegex(tester.TestFailure, "after terminal"):
            tracker.observe(reply(4, {"placed": {"orderQuantity": 1}}), "orders")

    def test_bad_fill_values_and_identity_are_rejected(self):
        variants = (
            {"lastQuantity": 2, "lastPrice": 99, "cumQty": 2, "leaves": 0},
            {"lastQuantity": 0.5, "lastPrice": 99, "cumQty": 0.5, "leaves": 0.6},
            {"lastQuantity": 0.5, "lastPrice": 101, "cumQty": 0.5, "leaves": 0.5},
            {"lastQuantity": float("nan"), "lastPrice": 99, "cumQty": 0.5, "leaves": 0.5},
        )
        for fill in variants:
            with self.subTest(fill=fill), self.assertRaises(tester.TestFailure):
                self.tracker().observe(reply(1, {"filled": fill}), "orders")
        with self.assertRaisesRegex(tester.TestFailure, "identity mismatch"):
            self.tracker().observe(reply(1, {"placed": {"orderQuantity": 1}}, accountID=2), "orders")
        with self.assertRaisesRegex(tester.TestFailure, "side mismatch"):
            self.tracker().observe(reply(1, {"placed": {"orderQuantity": 1}}, orderSide="sell"), "orders")

    def test_both_float_and_text_execution_numbers_are_supported(self):
        message = schema.ManagerMessage.new_message()
        message.from_dict({"seqnum": 1, "message": {"sess": {"exec2": {
            "strgOrdID": 1, "accountID": 1, "securityId": 1, "venueID": 1,
            "orderSide": "buy", "data": {"filled": {"lastQuantity": "1", "lastPrice": "99",
                                                         "cumQty": "1", "leaves": "0"}},
        }}}})
        tracker = self.tracker()
        tracker.observe(message.to_bytes_packed(), "orders")
        self.assertEqual(tracker.completed, 1)


class GeneratorTests(unittest.TestCase):
    def test_seed_repeats_orders_and_exercises_both_sides(self):
        choices = [(1, 1, 1, [("buy", 100, 0.5), ("sell", 99, 1)])]
        batches = []
        for _ in range(2):
            tracker = tester.OrderTracker(schema)
            with patch.object(tester.time, "time_ns", return_value=100):
                batches.append(tester.make_orders(schema, choices, 32, random.Random(7), tracker))
            self.assertEqual({order["orderSide"] for order in tracker.orders.values()}, {"buy", "sell"})
            self.assertTrue(all(0 < order["quantity"] <= (0.5 if order["orderSide"] == "buy" else 1)
                                for order in tracker.orders.values()))
            self.assertEqual(tracker.completed, 0)
        self.assertEqual(batches[0], batches[1])

    def test_nonlocal_host_is_rejected_before_any_connection(self):
        args = SimpleNamespace(transport="websocket", seed=7, orders=1, timeout=1, verbose=False)
        with patch.object(tester, "websocket_check") as connect:
            with self.assertRaisesRegex(tester.TestFailure, "loopback"):
                asyncio.run(tester.run(args, {"host": "nonlocal.invalid"}))
        connect.assert_not_called()

    def test_overall_deadline_bounds_a_stalled_transport(self):
        async def stalled(*unused):
            await asyncio.Event().wait()
        args = SimpleNamespace(transport="websocket", seed=7, orders=1, timeout=0.01, verbose=False)
        with patch.object(tester, "websocket_check", side_effect=stalled):
            with self.assertRaises(asyncio.TimeoutError):
                asyncio.run(tester.run(args, {"host": "localhost", "token": "t" * 256,
                                             "websocket_port": 1, "rest_market_port": 2,
                                             "rest_reference_port": 3}))

    def test_successive_rest_calls_cannot_refresh_the_overall_deadline(self):
        settings = tester.FixtureSettings(host="localhost", token="t" * 256, tls=False,
                                          deadline=20, reference_port=1)
        with patch.object(tester.time, "monotonic", side_effect=[10, 12, 14, 16, 20]), \
                patch.object(tester.ws.urllib.request, "urlopen") as request:
            request.return_value.__enter__.return_value.read.return_value = b"[]"
            with self.assertRaisesRegex(tester.TestFailure, "deadline expired"):
                tester.ws.reference_data(settings)
        self.assertEqual([call.kwargs["timeout"] for call in request.call_args_list], [10, 8, 6, 4])


if __name__ == "__main__":
    unittest.main()
