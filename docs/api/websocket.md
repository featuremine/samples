# WebSocket API — Integration Guide

This guide describes how to submit orders and receive responses over WebSocket,
using REST for reference data and prices. Order messages use the same Cap'n
Proto schema as the TCP API.

For setup and run commands, see the [repository README](../../README.md) and
[WebSocket strategy guide](../strategies/websocket.md).

## Services and Authentication

Start a Titan session and use its connect address, service ports, and
**order-entry token**. The profile's **Connections** settings configure these
services:

| Service | Default port | Contract |
| --- | ---: | --- |
| WebSocket orders | 8034 | Packed `strategy/ManagerMessage` requests and replies |
| REST market prices | 8035 | [ASCII field/value queries](market-data.md) |
| REST reference data | 8036 | [Authenticated reference JSON](reference.md) |

Titan's embedded endpoints use plain WS/HTTP. Use WSS/HTTPS when connecting
through a TLS endpoint. In the bundled sample, `--tls` switches all three
services to WSS/HTTPS.

Pass the complete token as the `Authorization` header value for the WebSocket
upgrade and reference REST requests, without a `Bearer ` prefix. The price
service does not authenticate requests; an `Authorization` header on a price
query does not restrict access to prices.

A WebSocket subprotocol header is not required. The upgrade can return these
status codes:

| Upgrade result | Meaning |
| ---: | --- |
| HTTP 101 | WebSocket connection established |
| HTTP 400 | Invalid `x-wssyncer-skipmessages` value |
| HTTP 401 | Missing or unknown authorization token |
| HTTP 500 | Internal server error |

The first account's **Account name** identifies your strategy in Titan. The
token exposes accounts with matching names. Use the identifiers returned by
reference discovery in the running session.

The order-entry token routes orders to the first configured venue.
Submit orders for that venue; changing `venueID` does not select another route.

## Versions and Encoding

Binary application messages contain packed Cap'n Proto
`strategy/ManagerMessage` payloads from [strategy.capnp](../../strategy.capnp).
There is no schema-version handshake. Clients and the service must use
compatible application schemas. The bundled
[schema version](../../schemas_version.capnp) is **1.0.11**.

The first application message from the server is a JSON text recovery
announcement. Subsequent responses are binary messages. WebSocket supplies the
framing; application messages contain no Carnitas TCP envelope.

## Integration Stages

**1. Connect and authenticate.** Open a WebSocket connection to
`ws://<HOST>:<WS_PORT>/` using the complete token header.

**2. Recover.** Read the initial text message containing `received` and
`pending`. Then read `pending` binary replies to complete recovery before
submitting new orders. These counts cover the streams selected by the token;
the [recovery announcement](#recovery-announcement) defines their scope,
replay offsets, and use for retransmission.

**3. Discover reference data.** Request accounts, security definitions,
account/venue mappings, venue/security attributes, and positions from the
[reference REST API](reference.md). Match these records to find eligible
account/security/venue combinations for the configured route.

**4. Obtain prices.** Request FIDs 25 and 735 for the eligible numeric security
identifiers from the [price REST API](market-data.md). Retry HTTP 503
while the price service loads its initial data. Check that prices
and quantities are finite and positive before using them in an order.

**5. Send and receive application messages.** Send one packed `ManagerMessage`
per binary WebSocket message. Keep receiving while sending a batch, and retain
responses that arrive before the last order is sent. Correlate replies with
their `strgOrdID` and process them until the orders are complete. The
[strategy schema](../../strategy.capnp) defines requests, acknowledgements,
executions, and failures.

**6. Close.** Finish the WebSocket close handshake and release the connection.

## Connection Example

Open an order connection using the running session's settings:

```python
import websocket


def connect_orders(host, port, token, timeout=30, tls=False):
    scheme = "wss" if tls else "ws"
    return websocket.create_connection(
        f"{scheme}://{host}:{port}/",
        header={"Authorization": token},
        timeout=timeout,
        enable_multithread=True,
    )
```

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
that channel are absent from WebSocket replies. Titan's main-session broadcast
status is available through TCP.

The bundled WebSocket sample validates the announcement and consumes the
pending replies before submitting its new batch. It discards those historical
replies and applies no timeout to the pending replay after the announcement.

## Order Payloads and Responses

Use the bundled [strategy schema](../../strategy.capnp) and
[common types](../../common.capnp) to construct and decode payloads. Send one
packed `strategy/ManagerMessage` in each nonempty binary application message.
Each binary response uses the same message format and contains one response
record. Payloads contain no TCP magic, handshake header, data header, checksum,
or stream announcement.

A binary message may span multiple WebSocket fragments. The fragments form one
application message. Empty client binary messages are ignored; client text
application messages are rejected.

The 64-bit service accepts assembled binary payloads of up to
**8,388,496 bytes**. This limit covers all fragments of a message. An oversized
message closes that connection with code 1009; partial fragments are not
submitted as separate requests.

Set `message.strg` to `new`, `cancel`, or `replace`, or use `new2`/`replace2`
for text prices and quantities. Support depends on the OMS or execution service.
The TCP guide's [order encoder](tcp.md#sending-orders) constructs the same
packed payload; send the returned bytes as a binary WebSocket message.

Use a distinct `strgOrdID` for each new order and retain it to match replies.
Cancel and replace requests use the existing order's identifier; see
[cancel and replace](tcp.md#cancel-and-replace) for the shared request fields.

Decode replies with `strategy.ManagerMessage.from_bytes_packed(payload)` and
inspect the `message` union. A `ctrl.placeForwarded`, `cancelForwarded`, or
`replaceForwarded` acknowledgement confirms forwarding. Treat `ctrl.failed`
and `sess.failed` as request failures and read their identifier, type, and
reason. Execution events arrive in `sess.exec` or `sess.exec2`; inspect their
`data` union. `Exec` uses floating-point numeric fields, while `Exec2` represents
prices and quantities as text. Use `strgOrdID` to correlate replies;
`ManagerMessage.seqnum` is a separate sequence for each output channel.

The [bundled sample](../../ws-strategy.py) submits the same IOC limit-buy batch
as the TCP sample. It retains replies during sends and finishes when every order receives
`filled`, `canceled`, or `rejected`. A forwarding acknowledgement does not
complete an order. A `message.sess.failed` response ends the sample with an error.
The sample ignores `ctrl.failed`, which can leave it waiting until its
order-response timeout.

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
