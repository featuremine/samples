# Old strategy: WebSocket and REST

This guide explains how to run [ws-strategy-old.py](../../ws-strategy-old.py) with
Titan. The sample retrieves reference data and prices through the REST APIs
and sends orders through the WebSocket API.

Follow the setup instructions in the [main README](../../README.md) before
running the sample.

The sample submits one batch of DAY limit orders. It generates random target
positions and uses the difference from current positions to determine each
order's side and quantity, with a fixed limit price of 10.

Install `requests` in your active virtual environment in addition to the
shared [requirements](../../requirements.txt):

```sh
python -m pip install requests
```

Run the sample from the repository root with your virtual environment active
and the Titan session running:

```sh
python ws-strategy-old.py --token "<TOKEN>"
```

The sample uses the same host for all three services. For different endpoint
settings:

```sh
python ws-strategy-old.py --host "<HOST>" --port <WS_PORT> --market-port <PRICES_PORT> --reference-port <REFERENCE_PORT> --token "<TOKEN>"
```

For connection and recovery instructions, see the
[WebSocket API](../api/websocket.md). The
[WebSocket protocol](../protocol/websocket.md) specifies the message format,
and the [order API](../api/orders.md) describes order requests and responses.

## Options

| Option | Default | Purpose |
| --- | --- | --- |
| `--host` | `localhost` | Host shared by all three services |
| `--port` | `8034` | WebSocket order-entry port |
| `--market-port` | `8035` | REST price port |
| `--reference-port` | `8036` | REST reference-data port |
| `--token` | Required | Profile order-entry token |
| `--schemas` | Script directory | Compatible Cap'n Proto schema directory |
| `--timeout` | `30` seconds | Does not change this sample's timeouts; see below |
| `--tls` | Disabled | Use WSS and HTTPS for all three services |

To list all command-line options:

```sh
python ws-strategy-old.py --help
```

For Titan's default wildcard **Host**, the default `localhost` connects through
loopback. For another **Host**, pass that configured address with `--host`.

Titan's embedded endpoints use plain WS and HTTP. When connecting through an
endpoint providing TLS, add `--tls` to select WSS for orders and HTTPS for both
REST services:

```sh
python ws-strategy-old.py --token "<TOKEN>" --tls
```

## Schemas and reference data

The sample uses [strategy.capnp](../../strategy.capnp) for orders. Keep its
imported schema files alongside it. By default, the sample uses the schemas
in the script's directory, even when you run it from another working directory.

To use another compatible schema set:

```sh
python ws-strategy-old.py --token "<TOKEN>" --schemas "<SCHEMA_DIRECTORY>"
```

A relative `--schemas` path is resolved from the terminal's working directory.
There is no WebSocket schema-version handshake, so the selected schema must be
compatible with the running service.

Before placing orders, the sample retrieves accounts, venues, securities,
venue-security attributes, venue-account mappings, and positions from the
[reference REST API](../api/reference.md). It stops with an error if required
account, venue, security, or mapping data is empty.

The initial price query sends **GET `/api/prices` with a request body**, using
`Content-Type: text/plain; charset=us-ascii`. It requests bid field `22` and ask
field `25` for securities in the venue-security attributes. The current
[market-data API guide](../api/market-data.md) documents POST for price queries;
check that the server accepts the old script's GET-with-body form.

The returned prices do not determine which orders are placed, their limit
prices, or their quantities.

In Titan, the first account's **Account name** identifies the strategy to the
services. The order-entry token gives access to accounts with that same name.
If you rename an account, start a new session before running the sample.

The token routes orders to the first configured venue. Use one execution venue
with this sample, since it selects orders from all visible venue mappings.

## Order selection and sizing

1. For each security with venue-security attributes, the sample chooses a venue
   and one of its mapped accounts at random. Venues without mapped accounts are
   skipped. If no supported combinations remain, the sample stops with an error.
2. It selects a random subset of between one and 1,000 of those combinations,
   limited by the number available.
3. It assigns each selected account/security pair an integer target position from
   `-999` through `1001`, inclusive.
4. It adds signed fills received during WebSocket recovery to the REST position,
   then rounds `target - current` to obtain the order quantity. Zero quantities
   are skipped.
5. It sends a buy for a positive quantity or a sell for a negative quantity,
   using the absolute quantity, limit price `10`, DAY time in force, the DMA
   algorithm, and no maximum floor.

If every calculated quantity is zero, no orders are sent.

## Recovery and timeouts

After retrieving reference data and prices, the sample opens its WebSocket
connection and receives the advertised `pending` historical replies before
sizing new orders. Position recovery includes `sess.exec` fills and partial
fills for known accounts and supported securities. It does not include fills
reported as `exec2` messages.

Changing `--timeout` has no effect in this sample. WebSocket operations use a
fixed ten-second socket timeout. REST requests have no timeout and are not
retried; an HTTP error stops the sample. There is no overall deadline for
waiting for order acknowledgements. Press **Ctrl+C** to stop while waiting.

Each run creates new order identifiers and submits one batch. It does not
cancel or track outstanding orders from earlier runs.

## Completion and output

The sample prints its recovery count, each order's side, quantity, current and
target positions, and a final acknowledgement summary:

```text
Recovering <COUNT> messages
Placing <SIDE> <QUANTITY> pos <CURRENT> target <TARGET> for security <SECURITY_ID>
...
Order state:
Pending: 0
PlaceForwarded: <COUNT>
Failed: <COUNT>
Done
```

`Done` means every submitted order received either a forwarding acknowledgement
(`ctrl.placeForwarded`) or a forwarding failure (`ctrl.failed`). Check the
`Failed` count for unsuccessful requests. Execution, cancellation, and rejection
responses do not determine completion. DAY orders can remain active in the
session after the sample exits.

## Troubleshooting

- For an import error, install the shared requirements and the additional
  `requests` dependency in the active virtual environment.
- For connection errors, check `--host`, `--port`, `--market-port`, and
  `--reference-port` against the running session's endpoints. With `--tls`, all
  three endpoints must provide TLS.
- For authentication errors, copy the complete order-entry token from Titan.
- For a price-request error or a stalled initial query, check the server's
  GET-with-body support and its startup recovery status. The script has no
  automatic retry or REST timeout.
- For empty reference data, check account ownership, venue-account mappings,
  security definitions, and venue-security attributes.
- Check the running session for executions and active DAY orders after the
  sample exits, including when it prints `Done`.
