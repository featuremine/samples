# Getting started

This repository contains sample strategies you can run with Featuremine's local
development environment or hosted services. Start with Titan to use real
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

## Strategies

In the previous section, you placed orders using the asynchronous WebSocket
strategy. The other available strategies demonstrate different programming
models and API combinations.

Each file documents its behavior and command-line options; use `--help` to
view the available options.

| Strategy | Orders | Reference data | Market data | Command |
| --- | --- | --- | --- | --- |
| [Asynchronous WebSocket](ws-strategy.py) | [WebSocket](docs/api/ws-gateway.md) | [REST](docs/api/rest-reference.md) | [REST](docs/api/rest-market-data.md) | `python ws-strategy.py --token "<TOKEN>"` |
| [Synchronous WebSocket](ws-strategy-sync.py) | [WebSocket](docs/api/ws-gateway.md) | [REST](docs/api/rest-reference.md) | [REST](docs/api/rest-market-data.md) | `python ws-strategy-sync.py --token "<TOKEN>"` |
| [TCP](tcp-strategy.py) | [TCP](docs/api/tcp-orders.md) | [TCP](docs/api/tcp-orders.md#reference-data) | [TCP](docs/api/tcp-market-data.md) | `python tcp-strategy.py --token "<TOKEN>"` |

The samples use Cap'n Proto schemas for [orders](strategy.capnp) and
[reference data](reference.capnp), with [shared types](common.capnp).

## APIs

The strategies use the following order gateways and data feeds. Each guide
describes the requests and responses, with examples.

| Service | Default port | Purpose |
| --- | ---: | --- |
| [WebSocket order gateway](docs/api/ws-gateway.md) | 8034 | Submit orders and receive responses |
| [REST reference data feed](docs/api/rest-reference.md) | 8036 | Retrieve accounts, securities, venues, positions, and limits |
| [REST market data feed](docs/api/rest-market-data.md) | 8035 | Query the latest requested price fields |
| [TCP order gateway](docs/api/tcp-orders.md) | 8032 | Submit orders and receive reference data and order responses |
| [TCP market data feed](docs/api/tcp-market-data.md) | 8033 | Receive streamed price updates |
