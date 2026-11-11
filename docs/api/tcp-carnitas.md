# TCP API — Integration Guide

This guide explains how to connect to Titan through the Carnitas TCP API,
retrieve reference data and prices, and send orders. For setup and run commands,
see the [TCP strategy guide](../strategies/tcp.md) and
[main README](../../README.md).

Orders and responses use the [strategy schema](../../strategy.capnp).
Reference messages use the [reference schema](../../reference.capnp).

## Connections and Authentication

Start a Titan session, then open an orders connection and a market-data
connection. Use the host and ports from the profile's **Connections** settings:

| Service | Default port | Purpose |
| --- | ---: | --- |
| Orders and reference data | 8032 | Reference definitions, account/venue mappings, order requests and responses |
| Market data | 8033 | Stream announcements and Elektron price updates |

Authenticate both connections with your client's **Order-entry token**. Include
its complete 256 ASCII bytes in the client handshake. The sample uses plain TCP
and has no TLS option.

Each client in Titan's **Accounts** section has its own name, order-entry token,
and accounts. The token identifies that client and exposes only its accounts.
Use the identifiers returned by reference discovery in the running session.

The token routes orders to the first configured venue. Use one execution venue
when running the bundled samples, since they select orders from all visible
venue mappings.

## Versions and Encoding

Use the eight-byte magic `tcn v031` for transport version **v031**. The
application schema version is separate and is defined in
[schemas_version.capnp](../../schemas_version.capnp). The bundled schema version
is **1.0.11**.

All TCP header and handshake integers are little-endian. Cap'n Proto payloads
use packed encoding. Price streams use the encoding indicated by their TCP
message type.

The client and server schema major versions must match. The client minor
version must be at least the server minor version; the server ignores the patch
version for this check. The TCP sample requires an exact match for all three
schema-version fields and for the server's returned magic.

## Integration Stages

**1. Connect.** Open both TCP connections using the selected host and ports.
Handle partial socket reads and writes.

**2. Handshake.** Send the v031 client handshake with the token, schema version,
and recovery count. Read and validate the complete server handshake on each
connection. The sample requests a full replay.

**3. Recover.** Read stream announcements and catch-up records. See
[Recovery and Sequence Numbers](#recovery-and-sequence-numbers) for the counts
and completion rules.

**4. Discover reference data and prices.** Use the received definitions and
mappings to identify eligible accounts, securities, and venues. Associate price
updates with their announced channels, as described below.

**5. Exchange orders and responses.** Send packed `ManagerMessage` orders in
type-100 frames. Continue receiving acknowledgements, executions, and failures,
and send transport heartbeats while waiting.

**6. Close.** Send a logout frame, wait for the server's reply, and close the
connection. If the server initiates logout, reply before closing. The
[Logout and Errors](#logout-and-errors) section defines the logout frame.

## TCP Handshake

### Common Header

Both handshake directions begin with this 16-byte header:

| Field | Offset | Size | Encoding |
| --- | ---: | ---: | --- |
| Magic | 0 | 8 | Exact ASCII bytes `tcn v031` |
| Schema major | 8 | 2 | UInt16 |
| Schema minor | 10 | 2 | UInt16 |
| Schema patch | 12 | 2 | UInt16 |
| Following payload size | 14 | 2 | UInt16 |

The common header corresponds to Python `struct.Struct("<8sHHHH")`.

### Client Handshake

Send a **280-byte** client handshake with a common-header payload size of
**264**:

| Field | Offset | Size | Meaning |
| --- | ---: | ---: | --- |
| Common header | 0 | 16 | Magic and client schema version |
| Token | 16 | 256 | Token bytes, with no delimiter or terminator |
| Recovery count | 272 | 8 | UInt64 count of previously received selected server records |

Include your client's complete 256-byte ASCII order-entry token. Set the
recovery count to zero to receive all selected records from the beginning. A
recovery count greater than the available selected-record count closes the
connection.

### Server Handshake

The server handshake totals **32 bytes**. Its common-header payload size is
**16**.

| Field | Offset | Size | Meaning |
| --- | ---: | ---: | --- |
| Common header | 0 | 16 | Magic and server schema version |
| Received request count | 16 | 8 | UInt64 count of persisted requests already received from this client route |
| Catch-up count | 24 | 8 | UInt64 selected server records awaiting replay after the client's recovery offset |

Use the received request count to determine which retained client requests need
retransmission. This count confirms receipt, not execution of those orders.

## TCP Data Messages

A data message consists of the following **24-byte header**, immediately
followed by its payload:

| Field | Offset | Size | Encoding |
| --- | ---: | ---: | --- |
| Checksum | 0 | 1 | UInt8 |
| Message type | 1 | 1 | UInt8 |
| Payload size | 2 | 2 | UInt16 |
| Sequence number | 4 | 4 | UInt32 |
| Timestamp | 8 | 8 | Int64 nanoseconds since Unix epoch |
| Stream ID | 16 | 8 | UInt64 |
| Payload | 24 | Payload size | Encoding selected by message type |

The header corresponds to Python `struct.Struct("<BBHIqQ")`. Read the payload
length from the header and consume that many bytes. The maximum payload length
is **65,535 bytes**. A socket read may contain part of a header or several
messages. Use the declared message lengths to read each complete message.

### Checksum

Calculate the checksum over the header only. Set the checksum byte to zero,
then calculate:

```python
checksum = (-sum(header)) & 0xff
```

Place the result in byte zero. The sum of all 24 header bytes must then be zero
modulo 256. On receipt, reject a header if `sum(header) & 0xff` is nonzero.

### Message Types

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
| 108 | Elektron MessagePack | Alternating field IDs and field values |

The TCP sample uses types 100–103 and 108. Its application schemas are
[strategy.capnp](../../strategy.capnp) and
[reference.capnp](../../reference.capnp). Schemas for types 104 and 105 are not
included in this repository.

Use a type-0 announcement to associate the header's stream ID with its
`peer:channel` name. The sample reads this name as UTF-8. Announcements arrive
before data from that stream and may repeat after reconnection. Keep stream IDs
separate for each connection: the same numeric ID on the orders and market-data
connections does not identify a shared stream.

## Recovery and Sequence Numbers

Set the client recovery count to the number of selected server data records
already received. Do not count announcements. After the handshake, read the
announcements and the remaining recovery records, then continue receiving live
data. The TCP sample waits for the advertised catch-up count on each connection
before selecting orders.

A server data record's sequence number is one plus the number of selected data
records that precede it, modulo 2³². Announcement sequence and timestamp fields
are zero. These transport sequence numbers are separate from
`ManagerMessage.seqnum` and order identifiers.

The authenticated token selects the order route. Client header sequence,
timestamp, and stream ID fields do not change that route or prevent duplicate
requests. Retain application order identifiers separately.

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

For type-108 messages, read consecutive MessagePack field/value pairs with no
enclosing map or array. Each field ID precedes its value. Update prices for the
announced channel, retaining earlier field values when an update omits them.

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

## Order Responses

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

## Transport Heartbeat

Send messages within the configured socket timeout, which defaults to
**90 seconds**. The TCP sample sends an empty type-1 heartbeat every
**10 seconds** on both connections, including while waiting for prices or order
responses. This transport heartbeat is separate from OMS and session heartbeats
inside `ManagerMessage`.

## Logout and Errors

A logout frame is **24 zero bytes**, with no payload. To initiate logout, send
this frame and wait for the peer's identical reply before closing. When you
receive a logout frame, send the reply and close. Check all 24 bytes when
identifying a logout frame.

Authentication failures, incompatible schema versions, malformed frames,
invalid checksums, and invalid recovery offsets close the TCP connection.
There is no structured TCP error reply for these failures.
