# TCP strategy

The [TCP sample](../../tcp-strategy.py) opens two Carnitas connections: one for
orders and reference data, and one for market data. Follow the shared setup in
the [main README](../../README.md) before running it.

It submits one IOC limit-buy batch using ask field `25` and the smaller of ask
quantity field `735` and one unit, with the DMA algorithm. Eligible
security/venue pairs are processed in sorted order, followed by ascending
account identifier within each pair. Positions are loaded but do not affect
order selection.

Run these commands from the repository root, with the virtual environment
active and the Titan session running:

```sh
python tcp-strategy.py --token "<TOKEN>"
```

Both connections use the same host and profile order-entry token. For different
endpoint settings:

```sh
python tcp-strategy.py --host "<HOST>" --port <ORDER_PORT> --market-port <MARKET_PORT> --token "<TOKEN>"
```

The [TCP API](../api/tcp.md) describes application integration, the
[TCP protocol](../protocol/tcp.md) defines the wire format, and the
[order API](../api/orders.md) defines the shared order messages.

## Options

| Option | Default | Purpose |
| --- | --- | --- |
| `--host` | `localhost` | Host for both connections |
| `--port` | `8032` | Carnitas order-entry port |
| `--market-port` | `8033` | Carnitas market-data port |
| `--token` | Required | Profile order-entry token |
| `--schemas` | Script directory | Compatible Cap'n Proto schema directory |
| `--timeout` | `30` seconds | Connection, handshake, and order-response timeout |

The connections use plain TCP. To list all command-line options:

```sh
python tcp-strategy.py --help
```

## Schemas

The sample loads [strategy.capnp](../../strategy.capnp),
[reference.capnp](../../reference.capnp), and
[schemas_version.capnp](../../schemas_version.capnp). Keep their imported schema
files alongside them. The default directory is the directory containing the
script, including when the script is invoked from another working directory.

To use another compatible schema set:

```sh
python tcp-strategy.py --token "<TOKEN>" --schemas "<SCHEMA_DIRECTORY>"
```

A relative `--schemas` path is resolved from the terminal's working directory.
The sample checks the server's schema version during each handshake and
requires an exact match with its loaded schema-version triplet.

## Recovery and timeouts

Each invocation requests a full replay on both connections. The sample processes
stream announcements and reference records, and accumulates price-field updates
by channel. Risk-channel records link security identifiers to those channels.
It waits for both advertised recovery counts before selecting its order batch.
Historical replies are consumed before new orders are submitted.

The first configured account's **Account name** supplies the connection's client and
strategy identity. Each account's `Account.client` comes from its own name, so
the order-entry token exposes only accounts whose names match the first
account. New profiles start with a first account named `client`; saved names
are used as entered. Renaming an account requires a new session.

The sample sends transport heartbeats every ten seconds on both connections,
including while waiting for reference data and prices.

`--timeout` applies to connection setup, the handshake reply, and the batch's
order-response deadline. The response deadline starts after the batch is
submitted. There is no overall timeout for initial reference recovery or for
waiting for eligible reference data and positive, finite prices and quantities.
Press **Ctrl+C** to stop the sample while waiting.

Each invocation creates new order identifiers and submits its own single batch.
The shared order-selection rules and expected output are in the
[main README](../../README.md).

## Troubleshooting

- For connection errors, check that the Titan session is running and that both
  TCP ports and the connect host match **Connections** in the profile.
- For authentication errors, copy the complete 256-character ASCII order-entry
  token from the running session.
- For a schema-version mismatch or decoding error, use schemas compatible with
  the running services.
- If no orders are placed, check securities, accounts, venue mappings,
  security-to-venue attributes, risk channels, and positive ask price and ask
  quantity updates. The sample needs at least one eligible combination.
- If order responses time out, inspect the session's fill-model and order-flow
  diagnostics. Transport failures and malformed TCP frames close the connection;
  details are in the [TCP protocol](../protocol/tcp.md).
