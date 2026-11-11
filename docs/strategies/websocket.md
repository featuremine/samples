# WebSocket strategy

This guide explains how to run [ws-strategy.py](../../ws-strategy.py) with
Titan. The sample retrieves reference data and prices through the REST APIs
and sends orders through the WebSocket API.

Follow the setup instructions in the [main README](../../README.md) before
running the sample.

The sample submits one batch of IOC limit buy orders. Each order uses the
current ask price and a quantity of up to one unit.

Run the sample from the repository root with your virtual environment active
and the Titan session running:

```sh
python ws-strategy.py --token "<TOKEN>"
```

The sample uses the same host for all three services. For different endpoint
settings:

```sh
python ws-strategy.py --host "<HOST>" --port <WS_PORT> --market-port <PRICES_PORT> --reference-port <REFERENCE_PORT> --token "<TOKEN>"
```

| Service | Default port | Documentation |
| --- | --- | --- |
| WebSocket orders | `8034` | [WebSocket API](../api/ws-gateway.md) |
| REST prices | `8035` | [Market-data API](../api/rest-market-data.md) |
| REST reference data | `8036` | [Reference API](../api/rest-reference.md) |

The [strategy schema](../../strategy.capnp) defines order requests and responses.

## Options

| Option | Default | Purpose |
| --- | --- | --- |
| `--host` | `localhost` | Host shared by all three service connections |
| `--port` | `8034` | WebSocket order-entry port |
| `--market-port` | `8035` | REST price port |
| `--reference-port` | `8036` | REST reference-data port |
| `--token` | Required | Client order-entry token |
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

## Schemas and reference data

The sample uses [strategy.capnp](../../strategy.capnp) for orders. Keep its
imported schema files alongside it. By default, the sample uses the schemas
in the script's directory, even when you run it from another working directory.

To use another compatible schema set:

```sh
python ws-strategy.py --token "<TOKEN>" --schemas "<SCHEMA_DIRECTORY>"
```

A relative `--schemas` path is resolved from the terminal's working directory.
The WebSocket protocol has no schema-version handshake, so the selected order
schema must be compatible with the running service.

Before placing orders, the sample retrieves accounts, securities, venue-account
mappings, venue-security attributes, and positions from the
[reference REST API](../api/rest-reference.md). It requests ask field `25` and
ask-quantity field `735` from the [market-data REST API](../api/rest-market-data.md)
using `POST /api/prices`.

In Titan's **Accounts** section, copy the token for the client you want to use.
It gives access to that client's accounts and order channels. Account display
names do not determine ownership. Start a new session after changing client
identities or account definitions.

The token routes orders to the first configured venue. Use one execution venue
with this sample, since it selects orders from all visible venue mappings.

## Order selection and sizing

The sample selects securities that have a definition, a venue mapping, a
mapped account, and positive, finite ask prices and quantities. It submits a
buy order for each eligible account, security, and venue combination, using:

- Ask price field `25` as the limit price.
- The smaller of ask quantity field `735` and one unit as the order quantity.
- IOC time in force and the DMA algorithm.

Orders follow sorted security/venue pairs, then ascending account identifier
within each pair. Positions do not affect order selection or sizing.

## Recovery and timeouts

Each run receives the advertised `pending` historical replies before
submitting its order batch. Historical replies do not complete the new batch.
The sample continues to answer WebSocket Ping frames while retrieving
reference data and prices.

HTTP 503 responses are retried while the services finish recovery. There is no
overall deadline for waiting for eligible reference data and positive, finite
ask prices and quantities. A connection failure is reported as an error.

`--timeout` must be positive and finite. It applies to connection setup, the
first WebSocket recovery announcement, HTTP operations, and waiting for order
responses. Historical replay has no timeout after the initial announcement.
The order-response deadline starts after the batch is submitted. Press
**Ctrl+C** to stop while waiting.

Each run creates new order identifiers and submits one batch. It does not
cancel or track outstanding orders from earlier runs.

## Completion and output

The sample prints the number of orders placed and subsequent order updates:

```text
Placed <COUNT> orders using live prices
Order update: <EVENT>
...
Done
```

`Done` means every submitted order received a terminal fill, cancellation, or
rejection. A `sess.failed` response stops the sample with an error. A forwarding
failure can appear as an order-response timeout.

## Troubleshooting

- For connection errors, check the running session, all three ports, the connect
  host, and whether the endpoints expect plain WS/HTTP or WSS/HTTPS.
- For authentication errors, copy the complete 256-character ASCII order-entry
  token from the running session. Reference and WebSocket authentication status
  codes are documented in their respective APIs.
- If reference data is empty, check that you used the owning client's token,
  then check account-to-venue mappings and security-to-venue attributes.
- If no orders are placed, check that the price service returns positive,
  finite ask prices and ask quantities for eligible securities.
- For REST errors other than the retried 503 status, see the
  [reference API](../api/rest-reference.md) or [market-data API](../api/rest-market-data.md).
- If the WebSocket closes, check the [API guide's close codes](../api/ws-gateway.md#pingpong-and-close).
  Only the newest connection accepted for a token remains active.
- If order responses time out, check the running session for forwarding or
  execution failures, and confirm that only one execution venue is configured.
- For decoding errors, use a compatible order schema.
