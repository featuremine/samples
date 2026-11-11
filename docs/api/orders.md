# Order API — Application Messages

Send orders and read their responses as packed `strategy/ManagerMessage`
payloads over either TCP or WebSocket. This guide covers the messages used by
the current IOC examples. The [strategy schema](../../strategy.capnp) and
[common types](../../common.capnp) define the full set of fields and variants.

Follow the [TCP API](tcp.md) or [WebSocket API](websocket.md) to connect and
discover reference data before placing orders. To run an example, see the
[TCP strategy guide](../strategies/tcp.md) or
[WebSocket strategy guide](../strategies/websocket.md).

## Transport Encoding

| Transport | Application payload |
| --- | --- |
| TCP | Packed `ManagerMessage` inside a type-100 frame |
| WebSocket | Packed `ManagerMessage` as one binary message, without a TCP envelope |

Use compatible application schemas at both ends. Follow the
[TCP specification](../protocol/tcp.md) or
[WebSocket specification](../protocol/websocket.md) for framing and schema
compatibility checks.

## Order Requests

Set `message.strg` to `new`, `cancel`, or `replace`. Use `new2` or `replace2`
when prices and quantities need to be represented as text. The OMS or execution
service determines which requests are supported.

The current TCP and WebSocket samples send `new` IOC orders to Titan.
The profile's order-entry token routes requests to the first
configured venue; use that venue's identifier when placing an order.

### New IOC Limit Order

Pass account, security, and venue identifiers from discovery, and the ask price
and quantity from market data, to the following encoder:

```python
import math
import time

import capnp

# Run from the repository root, or pass the corresponding schema path.
strategy = capnp.load("strategy.capnp")


def encode_ioc(account_id, security_id, venue_id, ask, ask_quantity):
    if not math.isfinite(ask) or ask <= 0:
        raise ValueError("Ask must be finite and positive")
    if not math.isfinite(ask_quantity) or ask_quantity <= 0:
        raise ValueError("Ask quantity must be finite and positive")
    order_id = time.time_ns()
    message = strategy.ManagerMessage.new_message()
    message.from_dict({"message": {"strg": {"new": {
        "strgOrdID": order_id,
        "accountID": int(account_id),
        "securityId": int(security_id),
        "venueID": int(venue_id),
        "orderSide": "buy",
        "orderType": {"limit": ask},
        "quantity": min(ask_quantity, 1.0),
        "maxFloor": {"none": None},
        "timeInForce": "ioc",
        "algorithm": {"dma": None},
    }}}})
    return order_id, message.to_bytes_packed()
```

Send the returned packed payload through your order connection and retain
`order_id` to match replies to this request. Use a distinct `strgOrdID` for each
new order. The current TCP and WebSocket scripts check for identifier collisions
within their pending batch. Cancel and replace requests use the existing
order's identifier.

The identifiers in `Place` are signed 64-bit integers. Supply a finite,
positive quantity and a finite limit price. The IOC examples also require a
positive ask and use at most one unit per order.

### Cancel and Replace

To cancel an order, send `message.strg.cancel` with its existing `strgOrdID`.
To replace it, send `message.strg.replace` with the same identifier. Set each
`price` or `quantity` union to `unknown` to leave that value unchanged, or to
`price` or `quantity` to supply a new value. See `Cancel`, `Replace`, and their
response types in the [strategy schema](../../strategy.capnp).

The bundled strategies do not send cancel or replace requests.

## Order Responses

Decode each nonempty binary application payload, then inspect `message`:

```python
message = strategy.ManagerMessage.from_bytes_packed(payload)
kind = message.message.which()
```

Use `strgOrdID` to match a response to its order. Track TCP transport sequence
numbers and `ManagerMessage.seqnum` separately. Each output channel has its own
application sequence; on TCP, use the stream identifier to distinguish them.

### Control Acknowledgements and Failures

Read `message.ctrl.placeForwarded`, `cancelForwarded`, or `replaceForwarded`
as acknowledgement that the corresponding request was forwarded. Keep waiting
for its execution or rejection response. `message.ctrl.failed` reports a
forwarding failure; read its request identifier, request type, and reason.

Handle `ctrl.failed` if your client needs to report forwarding failures
immediately. The current TCP and WebSocket IOC samples ignore this message,
which can leave them waiting until their order-response timeout.

### Session Executions

Read order execution events from `message.sess.exec` or `message.sess.exec2`.
Match `strgOrdID` to the pending order, then inspect the `data` union. `Exec`
uses floating-point numeric fields; `Exec2` represents prices and quantities as
text. Fill events include last quantity and price, cumulative quantity, and
remaining quantity.

The current IOC samples print each execution event and remove an order from
the pending set on `filled`, `canceled`, or `rejected`. They finish after every
submitted order has one of these terminal responses. For other workflows,
handle the additional events defined in the schema.

### Session Failures and Liveness

Read `message.sess.failed` as a request failure. It carries
`ManagerMessage.Failed`, including the identifier, type, and reason. The
current TCP and WebSocket IOC samples terminate with an error on this message.

Use session `logon`, `heartbeat`, and `logout` messages to track the execution
session. Continue handling TCP type-1 heartbeats or WebSocket Ping/Pong for the
transport connection separately.

Titan sends its main-session status on a separate broadcast channel. Read
those records from the Carnitas TCP connection. The WebSocket syncer forwards
only its mapped response channel, so it does not provide that broadcast status.

For examples of receiving responses, replay handling, and pending-order
tracking, see
[tcp-strategy.py](../../tcp-strategy.py) and [ws-strategy.py](../../ws-strategy.py).
