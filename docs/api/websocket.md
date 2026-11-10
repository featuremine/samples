# WebSocket API — Integration Guide

The WebSocket order syncer carries the same packed application messages as the
TCP order service. [ws-strategy.py](../../ws-strategy.py) combines it with HTTP
reference discovery and price queries. For framing, recovery fields, Ping/Pong,
and close codes, see the [WebSocket protocol specification](../protocol/websocket.md).
For setup and commands, see the [repository README](../../README.md).

Detailed sample behavior is documented in the [WebSocket strategy guide](../strategies/websocket.md).

## Services and Authentication

Start a Titan session and use the profile's **Connections** settings and
**order-entry token**:

| Service | Default port | Contract |
| --- | ---: | --- |
| WebSocket orders | 8034 | Packed `strategy/ManagerMessage` requests and replies |
| REST market prices | 8035 | [ASCII field/value queries](market-data.md) |
| REST reference data | 8036 | [Authenticated reference JSON](reference.md) |

Titan's embedded endpoints use plain WS/HTTP. The sample's `--tls` option
selects WSS/HTTPS for all three services when they are provided through a TLS
endpoint.

The WebSocket upgrade and reference REST requests use the token as the entire
`Authorization` header value, without a `Bearer ` prefix. The price service
currently does not authenticate requests. The sample sends its token on price
requests too, but this does not restrict access to prices.

Titan's **Client name** defaults to `client`. It is used for both the accounts'
`client` field and the first venue's strategy name in the order route. Titan
maps the token to that account scope and route; clients must use identifiers
discovered from the running session.

## Integration Stages

**1. Connect and authenticate.** Establish the WebSocket connection at
`ws://<HOST>:<WS_PORT>/` using the complete token header. Missing or unknown
authorization is rejected with HTTP 401.

**2. Recover.** Read the initial text announcement containing `received` and
`pending`, then consume its pending historical binary replies. The sample does
this before submitting its new batch. The
[protocol specification](../protocol/websocket.md) defines replay offsets and
retransmission counters.

**3. Discover reference data.** Request accounts, security definitions,
account/venue mappings, venue/security attributes, and positions from the
[reference REST API](reference.md). Join those relationships to find
eligible account/security/venue combinations.

**4. Obtain prices.** Request FIDs 25 and 735 for the eligible numeric security
identifiers from the [price REST API](market-data.md). Retry HTTP 503
while its initial snapshots are recovering. Use finite, positive prices and
quantities.

**5. Send and receive application messages.** Send one packed `ManagerMessage`
per binary WebSocket message. Queue responses while writing a batch so fast
fills are retained, then process executions until its pending orders are
complete. The common [order API](orders.md) defines payloads and responses.

**6. Close.** Finish the WebSocket close handshake and release the connection.

## Connection Example

This function opens an order connection when called with the session's
settings:

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

Continue receiving while performing REST requests: the server sends periodic
Ping frames, and `websocket-client` handles them when its receive loop runs.
The sample keeps a receive worker active during discovery and price polling.
The first text application message is recovery metadata; subsequent application
replies are binary packed Cap'n Proto.

## Order Payloads and Responses

Use the bundled [strategy schema](../../strategy.capnp) and the
[shared order API](orders.md) to construct and decode payloads. There is no
TCP header, checksum, or stream announcement inside a WebSocket application
message. Schema compatibility is established through the selected schema files;
WebSocket does not negotiate a schema-version triplet.

The sample submits the same IOC limit-buy batch as the TCP sample. It ignores
historical responses before its batch, retains fast replies during sends, and
finishes after every submitted order receives `filled`, `canceled`, or
`rejected`. A forwarding acknowledgement does not complete an order.
`message.sess.failed` terminates the sample with an error.

The full receive and cleanup implementation is in
[ws-strategy.py](../../ws-strategy.py). Protocol limits, invalid-message handling,
and replacement of an older connection using the same token are documented in
the [WebSocket specification](../protocol/websocket.md).
