# Titan samples

Welcome to the introductory samples for portfolio managers. These examples
show how to connect your strategy to order management services, retrieve
reference data and prices, and submit orders.

By accessing or using this software, you agree to be bound by the terms of the
[End User License Agreement](EULA) included in this repository.

The examples cover two ways to connect:

- [TCP strategy](tcp-strategy.py): uses the TCP API for reference data, prices,
  and orders.
- [WebSocket strategy](ws-strategy.py): uses the WebSocket API for orders and
  the REST APIs for reference data and prices.

## Requirements

### Install dependencies

- Python 3.9 or later

On Debian-based systems, install Python:

```bash
apt-get install -y python3 python3-venv
```

On Red Hat-based systems, install Python:

```bash
dnf install -y python3
```

### Set up a virtual environment

Run the following commands from the repository root, where both strategy
scripts and `requirements.txt` are located.

Create and activate a virtual environment on macOS or Linux:

```sh
python3 -m venv fm-venv
source fm-venv/bin/activate
```

On Windows, using PowerShell:

```powershell
py -3 -m venv fm-venv
fm-venv\Scripts\Activate.ps1
```

Install the shared requirements:

```sh
python -m pip install -r requirements.txt
```

## Start Titan

Titan provides the local test environment used in this guide. It runs the
TCP, WebSocket, and REST services and simulates order execution. Your profile
defines the accounts, venues, securities, and price feed used by the samples.

### Create a new session

Open Titan. In **Sessions**, enter a new name in **Search or name a session**,
then click **Create** to begin setting up a new session. Next, create or
choose a profile.

### Select and configure a profile

Use one of your existing profiles or click **Add profile** and enter a **Profile name** to create a new one.
Use the following setup for these samples:

- In **Venues**, add **Kraken** if it is not already configured: select it
  from the **Venue** list and click **+**. Use **Search pairs** to find and
  select the pairs you would like to test, such as `XBT/USD` and `XBT/EUR`.
  Use one venue for these samples.
- In **Accounts**, configure the accounts you want to use under the existing
  client. You can rename the client or its accounts if desired. Then click
  **Copy token** next to **Order-entry token**. Use this token to connect your
  strategy to Titan.
- In **Connections**, keep the default **Host** and ports when running the
  strategy on the same computer as Titan. If you change them, use those
  settings when running the strategy.

### Start the session and connect a strategy

Click **Create** in the profile header to save the profile and start the
session. Then follow the steps in the [Run a strategy](#run-a-strategy)
section using the token you copied. Keep the Titan session running while your
strategy is connected.

For a custom **Host**, pass that address with `--host`. The profile tooltip
shows the connection address and ports for each service. The default ports are:

| Service | Default port | Sample |
| --- | --- | --- |
| TCP orders | 8032 | TCP |
| TCP market data | 8033 | TCP |
| WebSocket orders | 8034 | WebSocket |
| REST market data | 8035 | WebSocket |
| REST reference data | 8036 | WebSocket |

## Run a strategy

Both samples submit one batch of simulated immediate-or-cancel (IOC) limit buy
orders and wait for the results. Each order uses the current ask price and a
quantity of up to one unit. The strategy guides describe how accounts,
securities, and venues are selected.

With the virtual environment active and the Titan session running, choose a
sample. Replace `<TOKEN>` with your complete order-entry token.

### TCP

```sh
python tcp-strategy.py --token "<TOKEN>"
```

See the [TCP strategy guide](docs/strategies/tcp.md) for connection settings,
order selection, timeouts, and troubleshooting.

### WebSocket

```sh
python ws-strategy.py --token "<TOKEN>"
```

See the [WebSocket strategy guide](docs/strategies/websocket.md) for connection
settings, order selection, timeouts, TLS, and troubleshooting.

### Expected output

Once reference data and valid prices are available, the sample prints:

```text
Placed <COUNT> orders using live prices
Order update: <EVENT>
...
Done
```

`Done` means every submitted order has been filled, canceled, or rejected. Both
samples wait for eligible reference data and prices without an overall startup
deadline. Press **Ctrl+C** to stop while waiting.

## Documentation

| Interface | Strategy guide | API guide |
| --- | --- | --- |
| Carnitas TCP | [TCP strategy](docs/strategies/tcp.md) | [TCP API](docs/api/tcp-carnitas.md) |
| WebSocket orders | [WebSocket strategy](docs/strategies/websocket.md) | [WebSocket API](docs/api/ws-gateway.md) |

The [old strategy guide](docs/strategies/tcp-old.md) covers
[ws-strategy-old.py](ws-strategy-old.py), its random target positions, and DAY
limit orders.

- [Reference REST API](docs/api/rest-reference.md): account, venue, security,
  position, and limit data.
- [Market data REST API](docs/api/rest-market-data.md): price queries,
  field/value responses, and endpoint errors.

The bundled [strategy schema](strategy.capnp), [reference schema](reference.capnp),
and [schema version](schemas_version.capnp) define the messages used by the samples.
