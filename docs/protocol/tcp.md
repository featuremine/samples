# Carnitas TCP Protocol Specification

This specification defines the messages exchanged over a Carnitas TCP
connection. For the connection workflow, see the [TCP API](../api/tcp.md).
For order payloads, see the [strategy schema](../../strategy.capnp). Setup and run
commands are in the [TCP strategy guide](../strategies/tcp.md) and
[main README](../../README.md).

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

## TCP Connection Stages

1. Establish a TCP connection to the configured listener.
2. Send the complete client handshake and read the complete server handshake.
3. Process stream announcements and the advertised recovery records.
4. Exchange live application messages and transport heartbeats.
5. Exchange logout frames and close the connection.

Handle partial reads and writes. A socket read may contain part of a header or
several messages. Use the declared message lengths to read each complete message.

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

Include the profile's complete 256-byte ASCII order-entry token. Set the
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
is **65,535 bytes**.

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

Read Elektron payloads as consecutive MessagePack field/value pairs, with no
enclosing map or array. For example, ask FID 25 and quantity FID 735 each precede
their value. Apply updates to the channel identified by the stream announcement,
retaining earlier values for fields omitted from an update.

### Recovery and Sequence Numbers

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

### Transport Heartbeat

Send messages within the configured socket timeout, which defaults to
**90 seconds**. The TCP sample sends an empty type-1 heartbeat every
**10 seconds** on both connections, including while waiting for prices or order
responses. This transport heartbeat is separate from OMS and session heartbeats
inside `ManagerMessage`.

### Logout and Errors

A logout frame is **24 zero bytes**, with no payload. To initiate logout, send
this frame and wait for the peer's identical reply before closing. When you
receive a logout frame, send the reply and close. Check all 24 bytes when
identifying a logout frame.

Authentication failures, incompatible schema versions, malformed frames,
invalid checksums, and invalid recovery offsets close the TCP connection.
There is no structured TCP error reply for these failures.

