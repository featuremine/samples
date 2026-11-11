# TCP API — Integration Guide

This guide explains how to connect to Titan through the Carnitas TCP API,
retrieve reference data and prices, and send orders. For setup and run commands,
see the [TCP strategy guide](../strategies/tcp.md) and
[main README](../../README.md).

The [TCP protocol specification](../protocol/tcp.md) defines message layouts,
version checks, and recovery counts. Orders and responses use the
[strategy schema](../../strategy.capnp); reference messages use the
[reference schema](../../reference.capnp).

## Connections and Authentication

Start a Titan session, then open an orders connection and a market-data
connection. Use the host and ports from the profile's **Connections** settings:

| Service | Default port | Purpose |
| --- | ---: | --- |
| Orders and reference data | 8032 | Reference definitions, account/venue mappings, order requests and responses |
| Market data | 8033 | Stream announcements and Elektron price updates |

Authenticate both connections with the profile's **Order-entry token**. Include
its complete 256 ASCII bytes in the client handshake. The sample uses plain TCP
and has no TLS option.

The first account's **Account name** identifies your strategy in Titan. The
token exposes accounts with matching names. Use the identifiers returned by
reference discovery in the running session.

The token routes orders to the first configured venue. Use one execution venue
when running the bundled samples, since they select orders from all visible
venue mappings.

## Integration Stages

**1. Connect.** Open both TCP connections using the selected host and ports.
Handle partial socket reads and writes.

**2. Handshake.** Send the v031 client handshake with the token, schema version,
and recovery count. Read and validate the complete server handshake on each
connection. The sample requests a full replay and requires an exact match with
its schema version.

**3. Recover.** Read stream announcements and catch-up records until each
connection has received its advertised count. The sample waits for both counts
before choosing orders. See [TCP recovery](../protocol/tcp.md) for the count and
sequence rules.

**4. Discover reference data and prices.** Use the received definitions and
mappings to identify eligible accounts, securities, and venues. Associate price
updates with their announced channels, as described below.

**5. Exchange orders and responses.** Send packed `ManagerMessage` orders in
type-100 frames. Continue receiving acknowledgements, executions, and failures,
and send transport heartbeats while waiting.

**6. Close.** Send a logout frame, wait for the server's reply, and close the
connection. If the server initiates logout, reply before closing. The
[protocol specification](../protocol/tcp.md) defines the logout frame.

## Reference Discovery

Use the TCP message type to select a schema, decode the packed Cap'n Proto
payload, then read its `message` union:

| TCP type | Schema | Members used by the sample |
| ---: | --- | --- |
| 101 | `reference/Symbology` | `securityDefinition`, `riskChannel` |
| 102 | `reference/VenueData` | `venueAccountMapping`, `venueSecurityAttribute` |
| 103 | `reference/RiskData` | `account`, `position` |

Identify a security by `securityDefinition.identifier`. Use
`riskChannel.referenceId` and `channelName` to find its price channel.
`venueAccountMapping.identifier` and `venueID` link an account to a venue;
`venueSecurityAttribute.venueID` and `securityId` link that venue to a security.
Use these relationships and the identifiers from the running session when
selecting orders. The sample also loads positions, but does not use them to
size orders.

For example, read the union member from a type-101 payload:

```python
import capnp

# Run from the repository root, or pass the corresponding schema path.
reference = capnp.load("reference.capnp")


def symbology_member(payload):
    message = reference.Symbology.from_bytes_packed(payload)
    return message.message.which()
```

See [tcp-strategy.py](../../tcp-strategy.py) for a complete example.

## Market Data

A type-0 announcement associates a stream ID with a `peer:channel` name. Keep
stream IDs separate for each connection. For type-108 messages, read consecutive
MessagePack field/value pairs and update that channel's prices. Retain earlier
field values when an update omits them.

The sample uses ask price FID **25** and ask quantity FID **735**. Once both are
finite and positive, it submits one IOC limit-buy batch for eligible account,
security, and venue combinations.

## Sending Orders

Construct a packed `strategy/ManagerMessage` and send it in a type-100 frame.
Set `message.strg` to `new`, `cancel`, or `replace`. Use `new2` or `replace2`
when prices and quantities need to be represented as text. The OMS or execution
service determines which requests are supported. The
[strategy schema](../../strategy.capnp) and [common types](../../common.capnp)
define the full set of fields and variants.

The following encoder constructs the IOC limit buy used by the samples. Pass
account, security, and venue identifiers from discovery, and the ask price and
quantity from market data:

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

Use a distinct `strgOrdID` for each new order and retain it to match replies.
The current samples check for identifier collisions within their pending
batch. The identifiers in `Place` are signed 64-bit integers. Supply a finite,
positive quantity and a finite limit price; the IOC examples also require a
positive ask and use at most one unit per order.

### Cancel and Replace

To cancel an order, send `message.strg.cancel` with its existing `strgOrdID`.
To replace it, send `message.strg.replace` with the same identifier. Set each
`price` or `quantity` union to `unknown` to leave that value unchanged, or to
`price` or `quantity` to supply a new value. See `Cancel`, `Replace`, and their
response types in the [strategy schema](../../strategy.capnp).

The bundled strategies do not send cancel or replace requests.

## Order Responses and Liveness

Decode type-100 replies as packed `strategy/ManagerMessage` values:

```python
message = strategy.ManagerMessage.from_bytes_packed(payload)
kind = message.message.which()
```

Use `strgOrdID` to match a response to its order. Track TCP transport sequence
numbers and `ManagerMessage.seqnum` separately. Each output channel has its own
application sequence; use the TCP stream identifier to distinguish them.

Read `message.ctrl.placeForwarded`, `cancelForwarded`, or `replaceForwarded`
as acknowledgement that the corresponding request was forwarded. Keep waiting
for its execution or rejection response. Treat `message.ctrl.failed` and
`message.sess.failed` as request failures; each carries the request identifier,
type, and reason.

Read execution events from `message.sess.exec` or `message.sess.exec2`, then
inspect the `data` union. `Exec` uses floating-point numeric fields; `Exec2`
represents prices and quantities as text. Fill events include last quantity
and price, cumulative quantity, and remaining quantity.

The sample finishes when every submitted order receives `filled`, `canceled`,
or `rejected`, and reports `message.sess.failed` as an error. A `ctrl.failed`
response can lead to a response timeout in the sample.

Use session `logon`, `heartbeat`, and `logout` messages to track the execution
session. Titan's main-session status is available on a separate broadcast
channel through TCP; it is absent from WebSocket replies.

The sample sends an empty type-1 transport heartbeat every ten seconds on both
connections. These heartbeats are separate from OMS and session heartbeats
inside `ManagerMessage`. For socket timeouts and connection errors, see the
[TCP specification](../protocol/tcp.md).
