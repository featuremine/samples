# Getting started

This repository contains Python samples you can run with Featuremine's local,
development, and hosted trading environments. Start with Titan to use real
Kraken market data and simulated execution on your computer.

Request Titan access through the
[local trading development environment page](https://www.featuremine.com/learn#titan).

## Run a strategy

Install [Python 3.9 or later](https://www.python.org/downloads/); we recommend
using a [virtual environment](https://docs.python.org/3/library/venv.html).
From the repository root, install the requirements:

```sh
python -m pip install -r requirements.txt
```

Install and open Titan. In **Sessions**, select the **Default** session and
click **Start**.

Hover the **Default** profile name in the running workspace to view its
connection details. In the popup, click **Copy order-entry token** for the
default client.

Run the WebSocket sample from the repository root. Replace `<TOKEN>` with the
complete token you copied:

```sh
python ws-strategy.py --token "<TOKEN>"
```

Inspect the orders and execution updates in Titan. The script prints `Done`
when it finishes. Keep the Titan session running while the strategy is
connected.

## Running and configuring a local testing environment

Titan provides a **Default** profile and a **Default** session that uses it.
The supplied setup has one client, one account, and one Kraken venue with
simulated execution. Titan restores either default entry at startup if it is
missing and preserves existing profiles and sessions.

A profile stores your venues, securities, accounts, and connection settings.
A session runs the services with those settings and records its data. Profile
changes apply to new sessions; an existing session keeps its original settings.

### Venues and securities

The supplied **Default** profile includes `XBT/USD`, `XBT/EUR`, `ETH/USD`, and
`ETH/EUR`.

Use one Kraken venue with these samples. In **Venues**, use **Search pairs**
to choose the securities you want to test.

### Accounts and tokens

A new profile includes one client and one account. In **Accounts**, set the
account name and numeric ID, or use **Add account** to add accounts under the
same client. Account IDs must be unique across the profile; account names must
be unique within their client.

Each client has its own order-entry token, which gives access to its accounts
and order channels. Use **Copy token** beside **Order-entry token** to copy it.
After the session starts, you can also copy tokens from the profile-details
popup. Start a new session after changing clients, tokens, or account definitions.

### Connections

**Connections** sets one listening **Host** and five service ports. The default
host listens on all IPv4 interfaces; the samples use `localhost` to connect on
the same computer. If you configure a specific **Host**, pass that address
with `--host` when running a strategy.

| Service | Default port | Purpose |
| --- | ---: | --- |
| [TCP order gateway](docs/api/tcp-orders.md) | 8032 | Submit orders and receive reference data and order responses |
| [TCP market data feed](docs/api/tcp-market-data.md) | 8033 | Receive streamed price updates |
| [WebSocket gateway](docs/api/ws-gateway.md) | 8034 | Submit orders and receive responses |
| [REST market data feed](docs/api/rest-market-data.md) | 8035 | Query the latest requested price fields |
| [REST reference data feed](docs/api/rest-reference.md) | 8036 | Retrieve accounts, securities, venues, positions, and limits |

The running profile's tooltip shows the connection address and ports. Both
TCP connections, the WebSocket gateway, and the REST reference data feed use
the client's order-entry token. The REST market data feed requires no token.

Titan's embedded listeners use plain TCP, WS, and HTTP. Leave `--tls` off for
the local setup.

## Strategies

With a Titan session running, choose a sample below. Run its command from the
repository root, replacing `<TOKEN>` with the client's complete order-entry
token. Each file documents how the strategy works.

| Strategy | Orders | Reference data | Market data | Command |
| --- | --- | --- | --- | --- |
| [Asynchronous WebSocket](ws-strategy.py) | [WebSocket](docs/api/ws-gateway.md) | [REST](docs/api/rest-reference.md) | [REST](docs/api/rest-market-data.md) | `python ws-strategy.py --token "<TOKEN>"` |
| [Synchronous WebSocket](ws-strategy-sync.py) | [WebSocket](docs/api/ws-gateway.md) | [REST](docs/api/rest-reference.md) | [REST](docs/api/rest-market-data.md) | `python ws-strategy-sync.py --token "<TOKEN>"` |
| [TCP](tcp-strategy.py) | [TCP](docs/api/tcp-orders.md) | [TCP](docs/api/tcp-orders.md#reference-data) | [TCP](docs/api/tcp-market-data.md) | `python tcp-strategy.py --token "<TOKEN>"` |

The samples use Cap'n Proto schemas for [orders](strategy.capnp) and
[reference data](reference.capnp), with [shared types](common.capnp).

### Connection options

Use each script's `--help` for its complete options. If you changed the local
configuration, pass the matching host and ports:

| Option | Purpose |
| --- | --- |
| `--host` | Host for every connection; defaults to `localhost` |
| `--port` | Order port: 8034 for WebSocket, 8032 for TCP |
| `--market-port` | Market-data port: 8035 for REST, 8033 for TCP |
| `--reference-port` | REST reference-data port, 8036; WebSocket examples only |
| `--token` | Required order-entry token |
| `--schemas` | Compatible schema directory; defaults to the script's directory |
| `--timeout` | Connection and response timeout; the synchronous example ignores this option |
| `--tls` | WSS and HTTPS through a TLS endpoint; WebSocket examples only |
