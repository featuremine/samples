# TCP strategy

This guide explains how to run [tcp-strategy.py](../../tcp-strategy.py) with
Titan. The sample retrieves reference data and prices and sends orders through
the TCP API.

Follow the setup instructions in the [main README](../../README.md) before
running the sample.

The sample submits one batch of IOC limit buy orders. Each order uses the
current ask price and a quantity of up to one unit.

Run the sample from the repository root with your virtual environment active
and the Titan session running:

```sh
python tcp-strategy.py --token "<TOKEN>"
```

Both connections use the same host and client order-entry token. For different
endpoint settings:

```sh
python tcp-strategy.py --host "<HOST>" --port <ORDER_PORT> --market-port <MARKET_PORT> --token "<TOKEN>"
```

For connection, recovery, and message formats, see the [TCP API](../api/tcp-carnitas.md).
The [strategy schema](../../strategy.capnp) defines order requests and responses.

## Options

| Option | Default | Purpose |
| --- | --- | --- |
| `--host` | `localhost` | Host for both connections |
| `--port` | `8032` | Carnitas order-entry port |
| `--market-port` | `8033` | Carnitas market-data port |
| `--token` | Required | Client order-entry token |
| `--schemas` | Script directory | Compatible Cap'n Proto schema directory |
| `--timeout` | `30` seconds | Connection, handshake, and order-response timeout |

The connections use plain TCP. To list all command-line options:

```sh
python tcp-strategy.py --help
```

## Schemas and reference data

The sample uses [strategy.capnp](../../strategy.capnp) for orders,
[reference.capnp](../../reference.capnp) for reference data, and
[schemas_version.capnp](../../schemas_version.capnp) to check compatibility.
Keep their imported schema files alongside them. By default, the sample uses
the schemas in the script's directory, even when you run it from another
working directory.

To use another compatible schema set:

```sh
python tcp-strategy.py --token "<TOKEN>" --schemas "<SCHEMA_DIRECTORY>"
```

A relative `--schemas` path is resolved from the terminal's working directory.
The sample checks the server's schema version during each handshake and
requires an exact match with its loaded schema-version triplet.

Before placing orders, the sample receives account, security, venue-mapping,
and position data through the order connection. It receives prices through the
market-data connection and uses risk-channel records to associate prices with
securities.

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

Each run requests a full replay on both connections. The sample waits until
it has received the number of messages advertised by each server before
selecting its order batch. Historical order replies do not complete the new
batch.

The sample sends transport heartbeats every ten seconds on both connections,
including while waiting for reference data and prices.

`--timeout` applies to connection setup, the handshake reply, and waiting for
order responses. The order-response deadline starts after the batch is
submitted. There is no overall timeout for initial recovery or for waiting for
eligible reference data and prices. Press **Ctrl+C** to stop while waiting.

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

- For connection errors, check that the Titan session is running and that both
  TCP ports match **Connections** in the profile. Set `--host` to the configured
  **Host**, or to loopback when **Host** is the default wildcard IPv4 address.
- For authentication errors, copy the complete 256-character ASCII order-entry
  token from the running session.
- For a schema-version mismatch or decoding error, use schemas compatible with
  the running services.
- If no orders are placed, check that the account is visible, that the security
  is mapped to a venue and a price channel, and that positive ask prices and
  quantities are available. At least one eligible combination is required.
- If order responses time out, check the running session for forwarding or
  execution failures, and confirm that only one execution venue is configured.
