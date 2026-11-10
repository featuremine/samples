# WebSocket strategy

The [WebSocket sample](../../ws-strategy.py) uses the WebSocket syncer for
orders, the reference REST service for discovery, and the market-data REST
service for prices. Follow the shared setup in the
[main README](../../README.md) before running it.

It submits one IOC limit-buy batch using ask field `25` and the smaller of ask
quantity field `735` and one unit, with the DMA algorithm. Eligible
security/venue pairs are processed in sorted order, followed by ascending
account identifier within each pair. Positions are loaded but do not affect
order selection.

Run these commands from the repository root, with the virtual environment
active and the Titan session running:

```sh
python ws-strategy.py --token "<TOKEN>"
```

The sample uses the same host and profile order-entry token across its three
service connections. For different endpoint settings:

```sh
python ws-strategy.py --host "<HOST>" --port <WS_PORT> --market-port <PRICES_PORT> --reference-port <REFERENCE_PORT> --token "<TOKEN>"
```

| Service | Default port | Documentation |
| --- | --- | --- |
| WebSocket orders | `8034` | [WebSocket API](../api/websocket.md) and [protocol](../protocol/websocket.md) |
| REST prices | `8035` | [Market-data API](../api/market-data.md) |
| REST reference data | `8036` | [Reference API](../api/reference.md) |

The [order API](../api/orders.md) defines the application messages carried by
the WebSocket connection.

## Options

| Option | Default | Purpose |
| --- | --- | --- |
| `--host` | `localhost` | Host shared by all three service connections |
| `--port` | `8034` | WebSocket order-entry port |
| `--market-port` | `8035` | REST price port |
| `--reference-port` | `8036` | REST reference-data port |
| `--token` | Required | Profile order-entry token |
| `--schemas` | Script directory | Compatible Cap'n Proto schema directory |
| `--timeout` | `30` seconds | Connection, HTTP, and order-response timeout |
| `--tls` | Disabled | Use WSS and HTTPS for all three service connections |

Titan's embedded endpoints use plain WS/HTTP. Add `--tls` when connecting
through an endpoint providing WSS/HTTPS; it changes all three connections
together.

To list all command-line options:

```sh
python ws-strategy.py --help
```

## Schemas and discovery

The sample loads [strategy.capnp](../../strategy.capnp) for packed
`strategy/ManagerMessage` orders and responses. Keep its imported schema files
alongside it. The default schema directory is the directory containing the
script, including when the script is invoked from another working directory.

To use another compatible schema set:

```sh
python ws-strategy.py --token "<TOKEN>" --schemas "<SCHEMA_DIRECTORY>"
```

A relative `--schemas` path is resolved from the terminal's working directory.
The WebSocket protocol has no schema-version handshake, so the selected order
schema must be compatible with the running service.

Reference discovery reads `/securities`, `/accounts`, `/venueAccountMappings`,
`/venueSecurityAttributes`, and `/positions` as JSON. Price queries use
`POST /api/prices` for ask field `25` and ask-quantity field `735`. The sample
accepts numeric or decimal-string identifiers from the reference API.

The first configured account's **Account name** supplies the connection's client and
strategy identity. Each seeded account's `Account.client` comes from that
account's own name.
Only accounts whose names match the first account are visible through the
profile token. New profiles start with a first account named `client`; saved
names are used as entered. An account rename requires a new session.

## Recovery and timeouts

The sample validates the syncer's initial recovery announcement and consumes
the advertised pending historical replies before submitting its new batch.
Historical replies do not complete the new batch. A receive worker remains
active during REST requests so WebSocket Ping frames continue to receive Pong
responses.

HTTP 503 responses are retried while the services finish recovery. There is no
overall deadline for waiting for eligible reference data and positive, finite
ask prices and quantities. A connection failure is reported as an error.

`--timeout` must be positive and finite. It applies to connection setup, the
first WebSocket recovery announcement, HTTP operations, and the batch's
order-response deadline. Pending historical replay has no timeout after the
initial announcement. The order-response deadline starts after the batch is
submitted. Press **Ctrl+C** to stop the sample while waiting.

Each invocation creates new order identifiers and submits its own single batch.
The shared order-selection rules and expected output are in the
[main README](../../README.md).

## Troubleshooting

- For connection errors, check the running session, all three ports, the connect
  host, and whether the endpoints expect plain WS/HTTP or WSS/HTTPS.
- For authentication errors, copy the complete 256-character ASCII order-entry
  token from the running session. Reference and WebSocket authentication status
  codes are documented in their respective APIs.
- If reference discovery is empty, check that the accounts' `client` assignment
  matches the first account's **Account name**, then check account-to-venue mappings and
  security-to-venue attributes. Differently named accounts are outside the
  profile token's scope.
- If no orders are placed, check that the price service returns positive,
  finite ask prices and ask quantities for eligible securities.
- For REST errors other than the retried 503 status, see the
  [reference API](../api/reference.md) or [market-data API](../api/market-data.md).
- If the WebSocket closes, check the [protocol's close codes](../protocol/websocket.md#pingpong-and-close).
  Only the newest connection accepted for a token remains active.
- If order responses time out, inspect the session's fill-model and order-flow
  diagnostics. For decoding errors, use a compatible order schema.
