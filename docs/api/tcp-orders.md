# TCP order gateway

Use the TCP order gateway to retrieve reference data, submit orders, and
receive order updates. Prices arrive through the separate
[TCP market data feed](tcp-market-data.md). Both services use the TCP transport
defined in this guide.

For a local run, see [Getting started](../../README.md). The documented
[TCP example](../../tcp-strategy.py) combines both connections.

## Connection and authentication

Connect to the running session's order port, 8032 by default. Use the address
and port shown in Titan's profile tooltip. Authenticate with the complete
256-byte ASCII **Order-entry token** in the client handshake.

The token identifies a client and gives access to its accounts and order
channels. Use account, security, and venue identifiers from the running
session's reference data. In Titan, the token routes orders to the first
configured venue; use one venue with the bundled examples.

Titan's embedded listener uses plain TCP. The TCP example has no TLS option.

## TCP transport

The handshake, data headers, recovery counts, transport heartbeats, and logout
procedure below also apply to the TCP market data feed. Handle partial socket
reads and writes on both connections.

### Versions and encoding

Use the eight-byte magic `tcn v031` for transport version v031. The application
schema version is separate and is defined in
[schemas_version.capnp](../../schemas_version.capnp). The bundled version is
1.0.11.

All TCP header and handshake integers are little-endian. Cap'n Proto payloads
use packed encoding. Other payloads use the encoding selected by their message
type.

The client and server schema major versions must match. The client minor
version must be at least the server minor version; the server ignores the
patch version for this check. The TCP example requires an exact match for all
three schema-version fields and the server's returned magic.

### Common handshake header

Both handshake directions begin with this 16-byte header:

| Field | Offset | Size | Encoding |
| --- | ---: | ---: | --- |
| Magic | 0 | 8 | Exact ASCII bytes `tcn v031` |
| Schema major | 8 | 2 | UInt16 |
| Schema minor | 10 | 2 | UInt16 |
| Schema patch | 12 | 2 | UInt16 |
| Following payload size | 14 | 2 | UInt16 |

The header corresponds to Python `struct.Struct("<8sHHHH")`.

### Client handshake

Send a 280-byte client handshake immediately after connecting. Set its
common-header payload size to 264:

| Field | Offset | Size | Meaning |
| --- | ---: | ---: | --- |
| Common header | 0 | 16 | Magic and client schema version |
| Token | 16 | 256 | Token bytes, with no delimiter or terminator |
| Recovery count | 272 | 8 | UInt64 count of previously received selected server records |

Set the recovery count to zero for a full replay. A recovery count greater
than the available selected-record count closes the connection.

### Server handshake

Read and validate the complete server handshake before exchanging data
messages. It totals 32 bytes and has a common-header payload size of 16:

| Field | Offset | Size | Meaning |
| --- | ---: | ---: | --- |
| Common header | 0 | 16 | Magic and server schema version |
| Received request count | 16 | 8 | UInt64 count of requests already persisted on the route selected by your token |
| Catch-up count | 24 | 8 | UInt64 count of selected server records left to replay after your recovery offset |

Use the received request count with a retained request history to decide which
requests need retransmission. It confirms receipt, not execution.

### Data header

A data message has this 24-byte header followed immediately by its payload:

| Field | Offset | Size | Encoding |
| --- | ---: | ---: | --- |
| Checksum | 0 | 1 | UInt8 |
| Message type | 1 | 1 | UInt8 |
| Payload size | 2 | 2 | UInt16 |
| Sequence number | 4 | 4 | UInt32 |
| Timestamp | 8 | 8 | Int64 nanoseconds since Unix epoch |
| Stream ID | 16 | 8 | UInt64 |
| Payload | 24 | Payload size | Encoding selected by message type |

The header corresponds to Python `struct.Struct("<BBHIqQ")`. Read the declared
payload length, up to 65,535 bytes. One socket read can contain part of a
message or several messages; use the lengths to assemble complete messages.

### Checksum

Calculate the checksum over the header only. Set its first byte to zero, then
calculate:

```python
checksum = (-sum(header)) & 0xff
```

Put the result in byte zero. The sum of all 24 header bytes must be zero modulo
256. Reject a received header if `sum(header) & 0xff` is nonzero.

### Message types and stream announcements

| Value | Payload encoding | Meaning |
| ---: | --- | --- |
| 0 | Raw `peer:channel` name bytes | Stream announcement; no trailing NUL |
| 1 | Empty payload is valid | Transport heartbeat |
| 100 | Packed Cap'n Proto | `strategy/ManagerMessage` |
| 101 | Packed Cap'n Proto | `reference/Symbology` |
| 102 | Packed Cap'n Proto | `reference/VenueData` |
| 103 | Packed Cap'n Proto | `reference/RiskData` |
| 104 | Packed Cap'n Proto | `session/SessionMessage` |
| 105 | Packed Cap'n Proto | `status/StatusMessage` |
| 106 | Raw IEEE754 stream encoding | Floating-value stream data |
| 107 | Text | Text stream data |
| 108 | fmtron MessagePack | Alternating field IDs and field values |

Use type-0 announcements to associate each stream ID with its `peer:channel`
name. The example reads names as UTF-8. Announcements precede data on their
stream and can repeat after reconnection. Keep stream IDs separate for each
connection: equal numeric IDs on the order and market-data connections do not
identify a shared stream.

The example uses types 100–103 and 108. Its application schemas are
[strategy.capnp](../../strategy.capnp) and
[reference.capnp](../../reference.capnp). Schemas for types 104 and 105 are not
bundled here.

## Reference data

Select the schema from the TCP message type, decode the packed payload, and
read its `message` union:

| TCP type | Schema | Reference data |
| ---: | --- | --- |
| 101 | `reference/Symbology` | `securityDefinition`, `riskChannel` |
| 102 | `reference/VenueData` | `venueAccountMapping`, `venueSecurityAttribute` |
| 103 | `reference/RiskData` | `account`, `position` |

Identify a security by `securityDefinition.identifier`. Its
`riskChannel.referenceId` and `channelName` identify the price channel.
`venueAccountMapping.identifier` and `venueID` associate an account with a
venue; `venueSecurityAttribute.venueID` and `securityId` associate a venue with
a security. Use these relationships to select an account, security, and venue
for an order.

For example, inspect a type-101 payload:

```python
import capnp

# Run from the repository root, or pass the corresponding schema path.
reference = capnp.load("reference.capnp")


def reference_member(payload):
    message = reference.Symbology.from_bytes_packed(payload)
    return message.message.which()
```

## Requests

Construct a packed `strategy/ManagerMessage` and send it in a type-100 frame.
Set `message.strg` to `new`, `cancel`, or `replace`. Use `new2` or `replace2`
for prices and quantities represented as text. The order management system
(OMS) or execution service determines which requests are supported. The
[strategy schema](../../strategy.capnp) and [common types](../../common.capnp)
define the fields and variants.

Use a distinct `strgOrdID` for each new order under the same client identity,
across all connections. Retain it to match replies. The identifiers in `Place`
are signed 64-bit integers. Supply a finite, positive quantity and a finite
limit price.

### Cancel and replace

Send `message.strg.cancel` with the existing order's `strgOrdID` to cancel it.
For `message.strg.replace`, use the same identifier. Set each `price` or
`quantity` union to `unknown` to leave that value unchanged, or to `price` or
`quantity` to supply a new value. See `Cancel`, `Replace`, and their responses
in [strategy.capnp](../../strategy.capnp).

## Example

The following encoder builds an immediate-or-cancel (IOC), direct market access
(DMA) limit order. For a buy, pass ask price FID 25 and ask quantity FID 735.
For a sell, pass bid price FID 22 and bid quantity FID 730. The order uses at
most one unit of the quoted quantity. A FID is a field identifier within a
price update, distinct from the security identifier.

```python
import math
import time

import capnp

# Run from the repository root, or pass the corresponding schema path.
strategy = capnp.load("strategy.capnp")


def encode_ioc(account_id, security_id, venue_id, side, price, quoted_quantity):
    if side not in ("buy", "sell"):
        raise ValueError("Side must be buy or sell")
    if not math.isfinite(price) or price <= 0:
        raise ValueError("Price must be finite and positive")
    if not math.isfinite(quoted_quantity) or quoted_quantity <= 0:
        raise ValueError("Quoted quantity must be finite and positive")
    order_id = time.time_ns()
    message = strategy.ManagerMessage.new_message()
    message.from_dict({"message": {"strg": {"new": {
        "strgOrdID": order_id,
        "accountID": int(account_id),
        "securityId": int(security_id),
        "venueID": int(venue_id),
        "orderSide": side,
        "orderType": {"limit": price},
        "quantity": min(quoted_quantity, 1.0),
        "maxFloor": {"none": None},
        "timeInForce": "ioc",
        "algorithm": {"dma": None},
    }}}})
    return order_id, message.to_bytes_packed()
```

The asynchronous examples randomly choose among usable sides for each
account/security/venue combination. They check for identifier collisions in
their pending batch. They do not submit cancel or replace requests; see the
[code](../../tcp-strategy.py) for selection and response handling.

## Responses

Decode type-100 replies as packed `strategy/ManagerMessage` values:

```python
message = strategy.ManagerMessage.from_bytes_packed(payload)
kind = message.message.which()
```

Use `strgOrdID` to match replies to orders. Track TCP transport sequence numbers
separately from `ManagerMessage.seqnum`. Each output channel has its own
application sequence; use the TCP stream identifier to distinguish channels.

`message.ctrl.placeForwarded`, `cancelForwarded`, and `replaceForwarded`
acknowledge forwarding. Keep reading execution or rejection responses after
these acknowledgements. Treat `message.ctrl.failed` and `message.sess.failed`
as request failures; each carries the request identifier, type, and reason.

Execution events arrive in `message.sess.exec` or `message.sess.exec2`.
Inspect the `data` union. `Exec` uses floating-point numeric fields; `Exec2`
uses text for prices and quantities. Fills include last quantity and price,
cumulative quantity, and remaining quantity.

Session `logon`, `heartbeat`, and `logout` messages track the execution session.
Titan also publishes its main-session status on a separate broadcast channel
through TCP; that broadcast is absent from WebSocket replies.

## Recovery and sequence numbers

Set the handshake recovery count to the number of server data records already
received for that connection's token and service. Do not count stream
announcements. Read the advertised catch-up records, then continue with live
data. The TCP example requests full replay on both connections before choosing
its new batch; historical order replies do not complete that batch.

A server data record's transport sequence is one plus the number of selected
data records preceding it, modulo 2³². Announcement sequence and timestamp
fields are zero. These numbers are separate from `ManagerMessage.seqnum` and
order identifiers.

The token selects the order route. Client header sequence, timestamp, and
stream ID fields do not change that route or prevent duplicate requests.
Retain application order identifiers separately.

## Heartbeat and close

Send messages within the configured socket timeout, 90 seconds by default.
An empty type-1 transport heartbeat keeps an idle connection active. It is
separate from OMS and session heartbeats inside `ManagerMessage`. The TCP
example sends it every 10 seconds on both connections while waiting for data
or order responses.

A logout frame is 24 zero bytes with no payload. Send it and wait for the
peer's identical reply before closing. If you receive it first, reply and
close. Check all 24 bytes when identifying a logout frame.

## Errors

Authentication failures, incompatible schema versions, malformed frames,
invalid checksums, and invalid recovery offsets close the TCP connection.
These failures have no structured TCP error reply. Handle application request
failures separately using the response messages above.
