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

* Python >=3.6

For Debian-based systems use
```bash
apt-get install -y git python3
```

for Redhat-based systems use
```bash
dnf install -y git python3
```

### Set up virtual environment

To set up a virtual environment you may run the following commands from the
repository root, where both strategy scripts and `requirements.txt` are located.

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

1. Create or open a Titan profile and configure its accounts, venues, securities,
   and price feed. Use one execution venue with these samples.
2. In **Accounts**, select the client whose accounts you want to use, then
   reveal and copy that client's **Order-entry token**.
3. Check **Host** and the service ports in **Connections**.
4. Start the session and keep it running while running a sample.

The default **Host** listens on all IPv4 interfaces. When running the sample
on the same machine, use its default `localhost`. When a different **Host**
is configured in the Titan profile, pass the configured address with `--host`.
The profile tooltip shows the connection address and ports for each service.

In **Accounts**, each client has its own identity, order-entry token, and one
or more accounts. A client's token gives access to its accounts and order
channels. Account names are labels and do not determine ownership. Start a
new session after changing client identities or account definitions.

The token routes orders to the first configured venue. The samples select
orders from all visible venue mappings, so use one execution venue.

| Service | Default port | Sample |
| --- | --- | --- |
| TCP orders | `8032` | TCP |
| TCP market data | `8033` | TCP |
| WebSocket orders | `8034` | WebSocket |
| REST prices | `8035` | WebSocket |
| REST reference data | `8036` | WebSocket |

## Run a strategy

Both samples submit one batch of simulated IOC limit buy orders and wait for
the results. Each order uses the current ask price and a quantity of up to one
unit. The strategy guides describe how accounts, securities, and venues are
selected.

With the virtual environment active and the Titan session running, choose a
sample. Replace `<TOKEN>` with the complete order-entry token for your client.

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

`Done` means every submitted order received a terminal fill, cancellation, or
rejection. Both samples wait for eligible reference data and prices without an
overall startup deadline. Press **Ctrl+C** to stop while waiting.

## Documentation

| Interface | Strategy guide | API guide |
| --- | --- | --- |
| Carnitas TCP | [TCP strategy](docs/strategies/tcp.md) | [TCP API](docs/api/tcp-carnitas.md) |
| WebSocket orders | [WebSocket strategy](docs/strategies/websocket.md) | [WebSocket API](docs/api/ws-gateway.md) |

The [old strategy guide](docs/strategies/tcp-old.md) covers
[ws-strategy-old.py](ws-strategy-old.py), its random target positions, and DAY
limit orders.

- [Reference REST API](docs/api/rest-reference.md): account, venue, security,
  position, and limit discovery.
- [Market-data REST API](docs/api/rest-market-data.md): price-query requests,
  field/value responses, and endpoint errors.

The bundled [strategy schema](strategy.capnp), [reference schema](reference.capnp),
and [schema version](schemas_version.capnp) define the messages used by the samples.
