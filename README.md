# Titan samples

This repository contains Python strategies for a running Titan session:

- [TCP strategy](tcp-strategy.py): reference data, prices, and orders through
  Carnitas TCP connections.
- [WebSocket strategy](ws-strategy.py): orders through the WebSocket syncer,
  with reference data and prices through REST services.

Both samples discover eligible accounts, securities, and venues, submit one
batch of simulated IOC limit buy orders, and wait for terminal responses.
Each order uses the current ask price (field `25`) and the smaller of the ask
quantity (field `735`) and one unit, with the DMA algorithm. Orders follow sorted
security/venue pairs and ascending account identifiers. Positions are loaded
but do not affect order selection.
The scripts, [requirements](requirements.txt), and Cap'n Proto schemas are in
the repository root.

## Set up Python

Use Python 3.9 or newer with `pip` and `venv`. Run these commands from the
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

These provide `pycapnp` for messages, `msgpack` for TCP price updates, and
`websocket-client` for WebSocket orders.

## Start Titan

1. Create or open a Titan profile and configure its accounts, venues, securities,
   and price feed.
2. In **Profile configuration**, use **Show tokens** beside **Order-entry token**
   to copy the token for the profile.
3. Check the connect host and service ports in **Connections**.
4. Start the session and keep it running while running a sample.

The default connect host is `localhost`. The **Client name** defaults to
`client`. The same name identifies the accounts visible to the strategy and
the strategy in the first venue's order route.

| Service | Default port | Sample |
| --- | --- | --- |
| Carnitas orders | `8032` | TCP |
| Carnitas market data | `8033` | TCP |
| WebSocket orders | `8034` | WebSocket |
| REST prices | `8035` | WebSocket |
| REST reference data | `8036` | WebSocket |

## Run a strategy

With the virtual environment active and the Titan session running, choose a
sample. Replace `<TOKEN>` with the complete order-entry token from that session.

### TCP

```sh
python tcp-strategy.py --token "<TOKEN>"
```

See the [TCP strategy guide](docs/strategies/tcp.md) for endpoint overrides,
options, schemas, recovery, and troubleshooting.

### WebSocket

```sh
python ws-strategy.py --token "<TOKEN>"
```

See the [WebSocket strategy guide](docs/strategies/websocket.md) for REST
endpoints, options, schemas, TLS, recovery, and troubleshooting.

### Expected output

Once reference data and valid prices are available, the sample prints:

```text
Placed <COUNT> orders using live prices
Order update: <EVENT>
...
Done
```

`Done` means every submitted order received a terminal fill, cancellation, or
rejection. Each sample submits one batch. Both wait for initial eligible data
without an overall startup deadline; press **Ctrl+C** to stop while waiting.

## Documentation

| Interface | Strategy guide | API guide | Protocol specification |
| --- | --- | --- | --- |
| Carnitas TCP | [TCP strategy](docs/strategies/tcp.md) | [TCP API](docs/api/tcp.md) | [TCP protocol](docs/protocol/tcp.md) |
| WebSocket orders | [WebSocket strategy](docs/strategies/websocket.md) | [WebSocket API](docs/api/websocket.md) | [WebSocket protocol](docs/protocol/websocket.md) |

- [Order API](docs/api/orders.md): application requests, acknowledgements,
  executions, and failures shared by both transports.
- [Reference REST API](docs/api/reference.md): account, venue, security,
  position, and limit discovery.
- [Market-data REST API](docs/api/market-data.md): price-query requests,
  field/value responses, and endpoint errors.

The bundled [strategy schema](strategy.capnp), [reference schema](reference.capnp),
and [schema version](schemas_version.capnp) define the messages used by the samples.
