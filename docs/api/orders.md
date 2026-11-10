# Order API — Application Messages

TCP and WebSocket orders use the same packed
`strategy/ManagerMessage` application payload. This guide describes the request
and response members used by the samples. The bundled
[strategy schema](../../strategy.capnp) and [common types](../../common.capnp) define
the complete fields, unions, and enumerations.

For connection and discovery steps, see the [TCP API](tcp.md) or
[WebSocket API](websocket.md). For setup and run commands, see the
[repository README](../../README.md).

Detailed sample behavior is documented in the [TCP strategy guide](../strategies/tcp.md)
and [WebSocket strategy guide](../strategies/websocket.md).

## Transport Encoding

| Transport | Application payload |
| --- | --- |
| TCP | Packed `ManagerMessage` inside a type-100 frame |
| WebSocket | Packed `ManagerMessage` as one binary message, without a TCP envelope |

Use matching application schemas for both ends. Transport framing and schema
compatibility checks are described in the [TCP specification](../protocol/tcp.md)
and [WebSocket specification](../protocol/websocket.md).

## Order Requests

The `message.strg` request union includes `new`, `cancel`, `replace`, and the
text-numeric `new2`/`replace2` variants. Supported behavior depends on the OMS
or execution service behind the route; the samples submit `new` IOC orders to
Titan's fill model.

### New IOC Limit Order

The following function encodes the same request as the samples. Its identifiers
and prices are arguments populated from discovery and market data; calling it
only constructs bytes.

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

Use a distinct `strgOrdID` for each request and retain it while awaiting the
corresponding result. The scripts handle collisions within their pending batch.
`Place` identifiers use signed 64-bit fields; quantity must be finite and
positive, and a limit price must be finite. The samples additionally require a
positive ask and cap each order at one unit.

### Cancel and Replace

`message.strg.cancel` identifies an existing order by `strgOrdID`.
`message.strg.replace` identifies it by `strgOrdID` and uses the `price` and
`quantity` unions to distinguish unchanged (`unknown`) values from supplied
values. See `Cancel`, `Replace`, and their response types in the
[strategy schema](../../strategy.capnp). The bundled strategies do not send these
requests.

## Order Responses

Decode a nonempty binary application payload using:

```python
message = strategy.ManagerMessage.from_bytes_packed(payload)
kind = message.message.which()
```

The outer union distinguishes `ctrl`, `sess`, and `strg`. TCP transport sequence
numbers, `ManagerMessage.seqnum`, and `strgOrdID` serve different purposes;
correlate orders using `strgOrdID`.

### Control Acknowledgements and Failures

`message.ctrl.placeForwarded`, `cancelForwarded`, and `replaceForwarded`
describe forwarding of the corresponding request. A forwarding acknowledgement
does not complete an order. `message.ctrl.failed` carries a `Failed` value with
the request identifier, request type, and failure reason. Other control members
are defined in the schema.

### Session Executions

`message.sess.exec` and `message.sess.exec2` carry order execution events. Read
their `strgOrdID`, then inspect the `data` union. `Exec` uses binary floating
numeric fields; `Exec2` represents quantities and prices as text. For example,
fills include last quantity/price, cumulative quantity, and remaining quantity.

The samples remove an order from their pending set on `filled`, `canceled`, or
`rejected`, print each execution event, and finish once every submitted order
has one of those terminal responses. Other schema events remain available to
clients that need them. A forwarding control message does not substitute for a
terminal execution event.

### Session Failures and Liveness

`message.sess.failed` also carries `ManagerMessage.Failed`; both samples treat
it as a failed order request and terminate with an error. Session `logon`,
`heartbeat`, and `logout` messages describe the execution session. They are
application messages and are distinct from TCP type-1 heartbeats and WebSocket
Ping/Pong frames.

For complete receive loops, recovery handling, and pending-order tracking, see
[tcp-strategy.py](../../tcp-strategy.py) and [ws-strategy.py](../../ws-strategy.py).
