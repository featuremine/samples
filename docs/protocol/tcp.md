# Carnitas TCP Protocol Specification

This specification defines Carnitas TCP framing, authentication, recovery, and
connection behavior. See the [TCP API](../api/tcp.md) for application integration,
the [order API](../api/orders.md) for shared order messages, the
[TCP strategy guide](../strategies/tcp.md) for commands, and the
[repository README](../../README.md) for shared setup.

## Versions and Encoding

Carnitas identifies this TCP transport as **v031**, using the eight bytes
`tcn v031`. This transport version is separate from the application schema
version in [schemas_version.capnp](../../schemas_version.capnp). The bundled schema
version is **1.0.11**.

All TCP header and handshake integers are little-endian. Cap'n Proto payloads
use packed encoding. Price streams use the encoding indicated by their TCP
message type.

The TCP server accepts matching schema major versions when the client minor
version is at least the server minor version; patch is ignored by that check.
The TCP sample applies a stricter rule: the returned schema triplet must match
its bundled triplet exactly, and the returned magic must be canonical.

## TCP Connection Stages

1. Establish a TCP connection to the configured listener.
2. Send the complete client handshake and read the complete server handshake.
3. Process stream announcements and the advertised recovery records.
4. Exchange live application messages and transport heartbeats.
5. Exchange logout frames and close the connection.

Clients must handle partial reads and writes. A socket read may contain only
part of a header or several consecutive messages; TCP packet boundaries are not
application message boundaries.

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

The client handshake totals **280 bytes**. Its common-header payload size is
**264**.

| Field | Offset | Size | Meaning |
| --- | ---: | ---: | --- |
| Common header | 0 | 16 | Magic and client schema version |
| Token | 16 | 256 | Token bytes, with no delimiter or terminator |
| Recovery count | 272 | 8 | UInt64 count of previously received selected server records |

Use the profile's order-entry token. Set the recovery count to zero for a full
replay. The samples require a 256-byte ASCII token. An excessive recovery count
causes the TCP connection to terminate.

### Server Handshake

The server handshake totals **32 bytes**. Its common-header payload size is
**16**.

| Field | Offset | Size | Meaning |
| --- | ---: | ---: | --- |
| Common header | 0 | 16 | Magic and server schema version |
| Received request count | 16 | 8 | UInt64 count of persisted requests already received from this client route |
| Catch-up count | 24 | 8 | UInt64 selected server records awaiting replay after the client's recovery offset |

Use the received count when deciding which retained client requests need
retransmission. It is a recovery count, rather than an order-execution
acknowledgement.

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

The header corresponds to Python `struct.Struct("<BBHIqQ")`. The payload limit
is **65,535 bytes**. Header and payload must be read separately according to
the declared size.

### Checksum

The sum of all 24 header bytes must be zero modulo 256. The payload is excluded.
When building a header with checksum byte zero, calculate:

```python
checksum = (-sum(header)) & 0xff
```

Place that value in byte zero. When receiving a header, reject it if
`sum(header) & 0xff` is nonzero.

### Message Types

| Value | Payload encoding | Meaning |
| ---: | --- | --- |
| 0 | UTF-8 `peer:channel` | Stream announcement; no trailing NUL |
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

The TCP sample uses types 100–103 and 108. The corresponding application schemas
are [strategy.capnp](../../strategy.capnp) and
[reference.capnp](../../reference.capnp). Types 104 and 105 are listed to identify
the transport values; their schemas are not bundled with this sample repository.

An announcement associates its header's stream ID with its `peer:channel`
payload. Announcements precede data from that stream and can repeat after
reconnection. Scope stream IDs by connection: the same numeric ID on the orders
and market-data connections does not identify one shared stream.

Elektron MessagePack contains consecutive field/value objects, rather than a
surrounding JSON object or MessagePack map. For example, ask FID 25 and quantity
FID 735 each precede their value. The sample accumulates field updates by the
channel identified in the stream announcement.

### Recovery and Sequence Numbers

The client recovery count skips that many selected server data records;
announcements are excluded. After the handshake, the server supplies the
required announcements, replays the remaining records, and follows live data.
The TCP sample waits until both of its connections have received their
advertised catch-up counts before selecting its order batch.

Server data sequence numbers are one plus the low 32 bits of the selected-record
count read. Announcement sequence and timestamp fields are zero. Client header
sequence, timestamp, and stream ID fields do not select the server's order
route or provide request deduplication; the authenticated route determines
where requests are written. Retain application request identifiers separately.

### Transport Heartbeat

The TCP sample sends an empty type-1 message every **10 seconds** on both
connections. The server's socket timeout defaults to **90 seconds**. Continue
sending messages while waiting for prices or order responses. This transport
heartbeat is distinct from `ManagerMessage` execution-session heartbeats.

### Logout and Errors

A logout frame is **24 zero bytes**, with no payload. The peer replies with an
identical frame before closing. Validate the whole frame rather than treating
every empty announcement as a logout.

Invalid authentication, incompatible versions, malformed frames, invalid
checksums, and an invalid recovery offset terminate the TCP connection. There
is no structured TCP error response for those failures.

