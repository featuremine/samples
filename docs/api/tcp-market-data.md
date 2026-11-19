# Carnitas market data feed

Use the Carnitas market data feed to receive streamed prices. Retrieve security
definitions and price-channel mappings through the
[Carnitas gateway](tcp-orders.md#reference-data), then associate updates with
those securities. The [Carnitas example](../../tcp-strategy.py) combines both
feeds.

## Connection and authentication

Connect to the running session's market-data port, 8033 by default. Use the
complete 256-byte ASCII **Order-entry token** in the client handshake.
Titan's embedded listener uses plain TCP.

Use the [shared Carnitas protocol](tcp-orders.md#carnitas-protocol) for the
handshake, headers, checksums, message types, and framing. Read the complete
server handshake before receiving data. Stream IDs and recovery counts belong
to each connection separately, including when both connections use the same
token.

## Requests

The token selects the configured market-data streams. The example needs no
additional subscription message after its handshake. Set the recovery count
to zero for a full replay, then continue receiving live updates.

Send transport heartbeats while waiting. Submit orders through an order
gateway rather than this feed.

## Responses

A type-0 announcement maps a stream ID to its raw `peer:channel` name. The
announcement precedes data on that stream and can repeat after reconnection.
Use `riskChannel.referenceId` and `channelName` from reference discovery to
associate the price channel with a security identifier.

Type-108 fmtron payloads contain consecutive MessagePack values: a field
identifier (FID), then its value. There is no enclosing array or map. A FID
selects a value within the update; it is not a security identifier.

| FID | Value |
| ---: | --- |
| 22 | Bid price |
| 25 | Ask price |
| 730 | Bid quantity |
| 735 | Ask quantity |
| 6 | Trade price |
| 178 | Trade quantity |

Update the cached fields for that channel. An update can omit earlier fields;
retain their cached values. Other data encodings are identified by the
[Carnitas message type](tcp-orders.md#message-types-and-stream-announcements).

## Example

Decode an update and merge it into the channel's field cache:

```python
import msgpack


def update_prices(payload, fields):
    decoder = msgpack.Unpacker(raw=False)
    decoder.feed(payload)
    values = []
    consumed = 0
    for value in decoder:
        values.append(value)
        consumed = decoder.tell()
    if consumed != len(payload) or len(values) % 2:
        raise ValueError("Incomplete field/value update")
    fields.update(zip(values[::2], values[1::2]))
```

All three examples require a finite, positive price and quantity for
the chosen side. A buy uses ask fields 25 and 735; a sell uses bid fields 22
and 730. They randomly choose among usable sides and use at most one unit.
Reference data uses [reference.capnp](../../reference.capnp); order messages
use [strategy.capnp](../../strategy.capnp).

## Recovery

Use a separate recovery count for this connection. Count server data records
but exclude stream announcements. Read the
advertised catch-up count before treating initial recovery as complete.
The Carnitas example finishes recovery on both connections before choosing
orders.

Transport sequences count selected records for this connection, modulo 2³².
See [Recovery and sequence numbers](tcp-orders.md#recovery-and-sequence-numbers)
for the shared rules. Continue receiving live data and sending heartbeats
after recovery.

## Errors and close

Malformed headers, invalid checksums, incompatible schema versions, failed
authentication, and invalid recovery offsets close the connection without a
structured error reply. A missing quote can instead mean that its fields have
not arrived; keep reading updates and check the configured securities.

Follow the shared [heartbeat and close](tcp-orders.md#heartbeat-and-close)
procedure, including replying to a logout before closing.
