# WebSocket Syncer Protocol Specification

This specification defines the order syncer's WebSocket authentication,
recovery, application messages, and connection behavior. See the
[WebSocket API](../api/websocket.md) for integration, the [order API](../api/orders.md)
for shared order fields, the [WebSocket strategy guide](../strategies/websocket.md)
for commands, and the [repository README](../../README.md) for shared setup.

Reference discovery and price queries use separate services, described in the
[reference REST API](../api/reference.md) and
[market-data REST API](../api/market-data.md).

## Versions and Encoding

Application binary messages contain packed Cap'n Proto
`strategy/ManagerMessage` payloads from [strategy.capnp](../../strategy.capnp).
WebSocket has no schema-version handshake. Use compatible application schemas
for the server and client; the bundled [schema version](../../schemas_version.capnp)
is **1.0.11**.

The server's initial recovery announcement is a JSON text message. Subsequent
application responses use binary messages. WebSocket supplies its own framing;
these payloads contain no Carnitas TCP envelope.

## Connection and Authentication

Connect to the order syncer's configured URL, normally
`ws://<HOST>:<WS_PORT>/`, with the complete token as the `Authorization` header
value. A WebSocket subprotocol header is not required. Titan's default port is
8034. Use WSS when a TLS endpoint is configured in front of the embedded service.

| Upgrade result | Meaning |
| ---: | --- |
| HTTP 101 | WebSocket connection established |
| HTTP 400 | Invalid `x-wssyncer-skipmessages` value |
| HTTP 401 | Missing or unknown authorization token |
| HTTP 500 | Server could not initialize the authorized route |

## Recovery Announcement

The first application message from the server is a WebSocket **text** message:

```json
{"received": 0, "pending": 0}
```

The example counts are illustrative. Both fields are nonnegative integer
counts:

| Field | Meaning |
| --- | --- |
| `received` | Historical client-request records received before the recovery snapshot boundary |
| `pending` | Historical response records remaining after the requested skip offset at that boundary |

The optional `x-wssyncer-skipmessages` header supplies the number of historical
responses to skip. Its value must contain decimal digits only and fit UInt64.
Omitting the header requests all historical responses. A skip beyond available
history follows live responses after recovery; it does not terminate the
connection.

Read `pending` binary application messages to consume the advertised replay,
then continue reading live replies. The snapshot boundary is fixed, so live
appends do not increase its `pending` count. Use `received` and retained request
history when deciding which requests require retransmission. Neither count is
an execution acknowledgement.

The bundled WebSocket sample validates the initial announcement, consumes the
pending replay, and discards historical replies before submitting its new
batch. It does not impose a timeout on that pending replay after the initial
announcement.

## Application Messages

Each nonempty client binary message contains one packed
`strategy/ManagerMessage`. The server preserves the packed bytes. Server binary
messages contain one packed response record each. There is no TCP magic,
handshake header, data header, checksum, or stream announcement inside these
WebSocket payloads.

WebSocket fragmentation is supported: a fragmented binary message is assembled
as one application message. Empty client binary messages are ignored. Client
text application messages are rejected.

The assembled-payload cap is the server's YTP record payload limit. With the
current 64-bit layout it is **8,388,496 bytes**; oversized messages close that
session rather than being committed as partial requests.

## Ping/Pong and Close

The server sends a Ping every **five seconds**. Clients must process control
frames and reply with Pong as required by WebSocket. Continue receiving while
performing REST discovery or price polling; `websocket-client` handles Ping
when its receive loop runs. The supplied WebSocket sample keeps a receive
worker active during those requests.

| Close code | Meaning |
| ---: | --- |
| 1008 | Client sent a text application message |
| 1009 | Assembled binary payload exceeded the server limit |
| 1011 | A newer connection using the same token replaced this connection |

Only the newest accepted connection for a token remains active. WebSocket
transport errors and server-side failures can also terminate a connection.

