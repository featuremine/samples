# WebSocket Syncer Protocol Specification

This specification defines the WebSocket order service's authentication,
recovery, application messages, and connection behavior. See the
[WebSocket API](../api/websocket.md) for integration, the [order API](../api/orders.md)
for shared order fields, the [WebSocket strategy guide](../strategies/websocket.md)
for commands, and the [repository README](../../README.md) for shared setup.

Reference discovery and price queries use separate services, described in the
[reference REST API](../api/reference.md) and
[market-data REST API](../api/market-data.md).

## Versions and Encoding

Binary application messages contain packed Cap'n Proto
`strategy/ManagerMessage` payloads from [strategy.capnp](../../strategy.capnp).
There is no schema-version handshake. Clients and the service must use
compatible application schemas. The bundled
[schema version](../../schemas_version.capnp) is **1.0.11**.

The first application message from the server is a JSON text recovery
announcement. Subsequent responses are binary messages. WebSocket supplies the
framing; application messages contain no Carnitas TCP envelope.

## Connection and Authentication

Connect to the service URL, normally
`ws://<HOST>:<WS_PORT>/`, with the complete token as the `Authorization` header
value. A WebSocket subprotocol header is not required. Titan's default port is
8034. Use WSS when connecting through a TLS endpoint.

| Upgrade result | Meaning |
| ---: | --- |
| HTTP 101 | WebSocket connection established |
| HTTP 400 | Invalid `x-wssyncer-skipmessages` value |
| HTTP 401 | Missing or unknown authorization token |
| HTTP 500 | Internal server error |

## Recovery Announcement

The first application message from the server is a WebSocket **text** message:

```json
{"received": 0, "pending": 0}
```

Both fields are nonnegative integer counts; the zero values above are an
example:

| Field | Meaning |
| --- | --- |
| `received` | Records on the mapped request stream before the recovery snapshot boundary |
| `pending` | Records on the mapped response stream remaining after the requested skip offset at that boundary |

The token selects the request and response streams covered by these counts.
They are not limited to the current WebSocket connection. Titan's TCP and
WebSocket order-entry routes share the request stream, so TCP submissions also
contribute to `received`.

The optional `x-wssyncer-skipmessages` header supplies the number of historical
responses to skip. A nonempty value must contain only decimal digits, have at
most 31 characters, and fit UInt64. An omitted or empty value skips no
responses. If the skip exceeds the available history, recovery completes with
no pending replies and the connection follows live responses.

Read `pending` binary application messages to finish the advertised replay,
then continue reading live replies. The snapshot boundary is fixed: replies
added afterward do not increase `pending`. Use `received` with a retained
history of the request stream to decide which requests need retransmission.
Neither count confirms execution of an order.

Recovery and live replies cover the token's response stream. The separate
OMS control/status channel is not included, so status messages sent only on
that channel are absent from WebSocket replies.

The bundled WebSocket sample validates the announcement and consumes the
pending replies before submitting its new batch. It discards those historical
replies and applies no timeout to the pending replay after the announcement.

## Application Messages

Send one packed `strategy/ManagerMessage` in each nonempty binary application
message. Each binary response uses the same message format and contains one
response record. Payloads contain no TCP magic, handshake header, data header,
checksum, or stream announcement.

A binary message may span multiple WebSocket fragments. The fragments form one
application message. Empty client binary messages are ignored; client text
application messages are rejected.

The 64-bit service accepts assembled binary payloads of up to
**8,388,496 bytes**. This limit covers all fragments of a message. An oversized
message closes that connection with code 1009; partial fragments are not
submitted as separate requests.

## Ping/Pong and Close

The server schedules a Ping every **five seconds**. Delivery may be delayed
while the connection is not writable. Clients must process control frames and
answer Ping with Pong. Keep receiving during REST discovery and price polling;
`websocket-client` handles Ping while its receive loop runs.

| Close code | Meaning |
| ---: | --- |
| 1008 | Client sent a text application message |
| 1009 | Assembled binary payload exceeded the server limit |
| 1011 | A newer connection using the same token replaced this connection |

Only the newest accepted connection for a token remains active. Transport
errors and server failures can also close the connection.

