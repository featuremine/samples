# WebSocket API — Integration Guide

This guide describes how to submit orders and receive responses over WebSocket,
using REST for reference data and prices. Order messages use the same Cap'n
Proto schema as the TCP order API.

For framing, recovery fields, Ping/Pong, and close codes, see the
[WebSocket protocol specification](../protocol/websocket.md). For setup and run
commands, see the [repository README](../../README.md) and
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

The first account's **Account name** identifies your strategy in Titan. The
token exposes accounts with matching names. Use the identifiers returned by
reference discovery in the running session.

The order-entry token routes orders to the first configured venue.
Submit orders for that venue; changing `venueID` does not select another route.

## Integration Stages

**1. Connect and authenticate.** Open a WebSocket connection to
`ws://<HOST>:<WS_PORT>/` using the complete token header. Missing or unknown
authorization is rejected with HTTP 401.

**2. Recover.** Read the initial text message containing `received` and
`pending`. Then read `pending` binary replies to complete recovery before
submitting new orders. These counts cover the streams selected by the token;
the [protocol specification](../protocol/websocket.md) defines their scope,
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
[order API](orders.md) defines requests, acknowledgements, executions, and
failures.

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

Keep a receive loop running during REST discovery and price polling so Ping
frames are answered. With `websocket-client`, receiving data also handles
Ping/Pong control frames. The first application message is text containing
recovery metadata; subsequent replies are binary packed Cap'n Proto.

## Order Payloads and Responses

Use the bundled [strategy schema](../../strategy.capnp) and the
[shared order API](orders.md) to construct and decode payloads. Each binary
application message carries a packed payload without a TCP header, checksum,
or stream announcement. Use schemas compatible with the service; WebSocket has
no schema-version handshake.

The [bundled sample](../../ws-strategy.py) submits the same IOC limit-buy batch
as the TCP sample. It consumes the advertised historical replies before the
batch, retains replies during sends, and finishes when every order receives
`filled`, `canceled`, or `rejected`. A forwarding acknowledgement does not
complete an order. A `message.sess.failed` response ends the sample with an error.

For message limits, invalid-message handling, and replacement of a connection
using the same token, see the [WebSocket specification](../protocol/websocket.md).
