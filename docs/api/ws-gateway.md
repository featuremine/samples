# WebSocket gateway

Use the WebSocket gateway to submit orders and receive responses. Retrieve
reference data through the [REST reference data feed](rest-reference.md) and
prices through the [REST market data feed](rest-market-data.md). Order messages
use the same Cap'n Proto schema as the [Carnitas gateway](tcp-orders.md).

For a local run, see [Getting started](../../README.md). The documented
[synchronous](../../ws-strategy-sync.py) and
[asynchronous](../../ws-strategy.py) examples use this gateway.

## Connection and authentication

Connect to the running session's WebSocket port, 8034 by default, using its
connect address and your **Order-entry token**. The profile tooltip provides
the address and ports.

Titan's embedded endpoints use plain WS/HTTP. Use WSS/HTTPS when connecting
through a TLS endpoint. In the WebSocket examples, `--tls` switches all three
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

Each client in Titan's **Accounts** section has its own name, order-entry token,
and accounts. The token identifies that client and exposes only its accounts.
Use the identifiers returned by reference discovery in the running session.

The order-entry token routes orders to the first configured venue.
Submit orders for that venue; changing `venueID` does not select another route.

## Versions and encoding

Binary application messages contain packed Cap'n Proto
`strategy/ManagerMessage` payloads from [strategy.capnp](../../strategy.capnp).
There is no schema-version handshake. Use application schemas compatible with
the service. The bundled schemas use version 1.0.11.

The first application message from the server is a JSON text recovery
announcement. Subsequent responses are binary messages. WebSocket supplies the
framing; application messages contain no Carnitas envelope.

## Integration stages

1. Connect and authenticate. Open a WebSocket connection to
   `ws://<HOST>:<WS_PORT>/` using the complete token header.

2. Recover. Read the initial text message containing `received` and
   `pending`. Then read `pending` binary replies to complete recovery before
   submitting new orders. See [Recovery announcement](#recovery-announcement)
   for the counts, skip offset, and retransmission rules.

3. Discover reference data. Request accounts, security definitions,
   account/venue mappings, venue/security attributes, and positions from the
   [REST reference data feed](rest-reference.md). Use these records to find
   accounts and securities configured for the venue on your order route.

4. Obtain prices. Request bid price FID 22, ask price FID 25, bid quantity FID
   730, and ask quantity FID 735 from the
   [REST market data feed](rest-market-data.md). A FID identifies a price field,
   distinct from the security identifier. Retry HTTP 503 while initial data
   loads. Use a finite, positive price and quantity for the chosen side: ask for
   a buy, bid for a sell.

5. Send and receive application messages. Send one packed `ManagerMessage`
   per binary WebSocket message. Keep receiving while sending a batch, and retain
   responses that arrive before the last order is sent. Match replies to orders
   using `strgOrdID` and process them until the orders are complete. The
   [strategy schema](../../strategy.capnp) defines requests, acknowledgements,
   executions, and failures.

6. Close. Finish the WebSocket close handshake and release the connection.

## Connection example

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

## Recovery announcement

The recovery announcement tells you how many requests the server has already
stored and how many historical replies it will send. Read the first application
message from the server as a WebSocket text message:

```json
{"received": 0, "pending": 0}
```

Both fields are nonnegative integer counts; the zero values above are an
example:

| Field | Meaning |
| --- | --- |
| `received` | Requests already persisted on the order route selected by your token |
| `pending` | Historical replies still to send after the requested skip |

The server captures a recovery boundary. `received` counts records on the
request stream selected by your token before that boundary. `pending` counts
records on the selected response stream after the skip and before that boundary.
The counts include other producers writing to those same streams. Titan's
Carnitas and WebSocket order-entry routes share the request stream, so Carnitas
submissions also contribute to `received`.

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

Recovery and live replies come from the response stream selected by your token.
The order management system (OMS) control/status channel is separate. Messages
sent only on that channel are absent from WebSocket replies. Titan's main-session
broadcast status is available through the Carnitas gateway.

Both WebSocket examples validate the announcement and use replayed executions
to recover positions before submitting their new batch. They start with the
initial reference position for each account/security pair and add each
order's latest cumulative filled quantity, positive for buys and negative
for sells. Each update applies only the change from that order's previous
cumulative quantity, so a repeated value does not add another fill.

Replay and live handling cover partial fills, fills, corrections, busts,
status, and restated events in numeric `Exec` and text `Exec2` reports.
Position tracking does not change the examples' quote-based order sizing.
Historical replies do not complete orders in the new batch. See
[connection settings](../../README.md#connection-settings) for the separate
startup and order-response budgets.

## Requests

Use the bundled [strategy schema](../../strategy.capnp) and
[common types](../../common.capnp) to construct and decode payloads. Send one
packed `strategy/ManagerMessage` in each nonempty binary application message.
Each binary response uses the same message format and contains one response
record. Payloads contain no Carnitas magic, handshake header, data header,
checksum, or stream announcement.

A binary message may span multiple WebSocket fragments. The fragments form one
application message. Empty client binary messages are ignored; client text
application messages are rejected.

The 64-bit service accepts assembled binary payloads of up to
8,388,496 bytes. This limit covers all fragments of a message. An oversized
message closes that connection with code 1009; partial fragments are not
submitted as separate requests.

Set `message.strg` to `new`, `cancel`, or `replace`, or use `new2`/`replace2`
for text prices and quantities. Support depends on the OMS or execution service.
The encoder in the [Carnitas gateway guide](tcp-orders.md#example) constructs
the same packed payload. Send the returned bytes as a binary WebSocket message.

The examples set `strgOrdID` with `time.time_ns()`. Retain it to match replies.
Cancel and replace requests use the existing order's identifier; see
[cancel and replace](tcp-orders.md#cancel-and-replace) for the shared request fields.

## Responses

Decode replies with `strategy.ManagerMessage.from_bytes_packed(payload)` and
inspect the `message` union. A `ctrl.placeForwarded`, `cancelForwarded`, or
`replaceForwarded` acknowledgement confirms forwarding. `ctrl.failed` and
`sess.failed` carry the request identifier, type, and reason. The examples
ignore `ctrl.failed`; `sess.failed` aborts the run. Execution events arrive
in `sess.exec` or `sess.exec2`; inspect their
`data` union. `Exec` uses floating-point numeric fields, while `Exec2` represents
prices and quantities as text. Use `strgOrdID` to correlate replies;
`ManagerMessage.seqnum` is a separate sequence for each output channel.

Continue receiving execution and rejection responses after a forwarding
acknowledgement; the acknowledgement alone does not complete an order.

Both WebSocket examples randomly choose usable buy or sell sides and send
immediate-or-cancel (IOC), direct market access (DMA) orders of at most one
unit. Buys use the ask price and quantity; sells use the bid price and quantity.
The asynchronous example collects replies during sends; the synchronous example
reads them after sending its batch. Both finish when every submitted order
receives `filled`, `canceled`, or `rejected`.

## Ping/Pong and close

The server schedules a Ping every 5 seconds. Delivery may be delayed
while the connection is not writable. Process control frames and answer Ping
with Pong. Keep receiving during REST discovery and price polling;
`websocket-client` handles Ping while its receive loop runs.

| Close code | Meaning |
| ---: | --- |
| 1008 | Client sent a text application message |
| 1009 | Assembled binary payload exceeded the server limit |
| 1011 | A newer connection using the same token replaced this connection |

Only the newest accepted connection for a token remains active. Transport
errors and server failures can also close the connection.
