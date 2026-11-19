# Getting started

This repository contains sample strategies you can run with Featuremine's local
development environment (Titan) or our hosted services. Start with Titan and use real
Kraken market data and simulated trading venue on your computer.

Request Titan access through the
[local trading development environment page](https://www.featuremine.com/learn#titan).

## Run a strategy

These sample strategies may be used and modified only for use with local
Featuremine Titan or Featuremine-owned hosted services, under the
[proprietary license](LICENSE-RESTRICTED).

### Prepare the sample

Download and unpack the Samples repository, then open a terminal in its main
folder—the one containing `requirements.txt`.

Install [Python 3.9 or later](https://www.python.org/downloads/); we recommend
using a [virtual environment](https://docs.python.org/3/library/venv.html).
From this folder, install the requirements:

```sh
python -m pip install -r requirements.txt
```

Install Titan using the instructions provided with your access.

### Start Titan

If the **Default** session is already running, leave it open and continue with
[Run the sample](#run-the-sample).

Otherwise, open Titan. In **Sessions**, select **Default** and click **Start**.
On a new installation, it includes XBT/USD, XBT/EUR, ETH/USD, and ETH/EUR, one
client with one account, and one venue with simulated execution.

On its first start, the session loads initial position prices before opening
the trading workspace. Wait for live market data before running the sample.

### Run the sample

All three examples submit one order for each eligible account/security/venue
combination. Each randomly chooses a buy or sell side whose quote price and
size are finite and positive. Buys use the ask; sells use the bid.

The limit price is the selected quote, and the quantity is the smaller of its
available size and one unit. All examples use immediate-or-cancel (IOC)
orders.

Hover the **Default** profile name in the running workspace to view its
connection details. In the popup, click **Copy order-entry token** for the
default client.

Run the synchronous WebSocket sample from the repository root. Replace
`<TOKEN>` with the complete token you copied:

```sh
python ws-strategy-sync.py --token "<TOKEN>"
```

### Check the result

Inspect the orders and execution responses in Titan under **Orders/Manager**.
The script prints `Placed N orders using live prices`, followed by
`Order update: <event>` messages. It prints `Done` after every order receives
`filled`, `canceled`, or `rejected`. An acknowledgement that a request was
forwarded does not complete an order.

### Troubleshooting

- **Titan does not start:** read its error dialog. If initial prices cannot
  load, check your internet connection and try again.
- **Reference data, quotes, or authentication are unavailable:** confirm that
  the intended session is running and receiving market data. Use the
  order-entry token from its running profile and check the
  [connection settings](#connection-settings). Allow startup data to load,
  then retry. See the [reference](docs/api/rest-reference.md#errors-and-limits)
  and [price](docs/api/rest-market-data.md#errors-and-limits) error guides if
  requests keep failing.
- **An order fails or a service reports an error:** inspect the response's
  reason under **Orders/Manager**. Check **Orders/Status** for service
  diagnostics. The [response guide](docs/api/ws-gateway.md#responses) explains
  the message types.

## Modify a sample

Copy `ws-strategy-sync.py` to `my-strategy.py` in the repository root, keeping
its license header. The copy will load the same bundled schemas. Make both
changes below in the copy, leaving the original script unchanged.

Change `timeInForce` from `ioc` to `day`:

```python
"timeInForce": "day",
```

Change the limit price to move it away from the selected quote:

```python
"orderType": {"limit": price * (0.99 if side == "buy" else 1.01)},
```

Titan cancels marketable DAY orders, so changing only the time-in-force does
not demonstrate a resting order. The adjusted buy limit is below the selected
ask; the adjusted sell limit is above the selected bid. The order can rest if
its limit does not cross the market when Titan processes it.

Keep the other fields unchanged. With Titan still running, use the same
order-entry token:

```sh
python my-strategy.py --token "<TOKEN>"
```

Under **Orders/Manager**, compare the working DAY orders with the IOC
execution responses from the first run. The script waits for working orders
to finish, so it may keep running until they terminate or the response wait
times out. Stopping it with **Ctrl+C** disconnects without canceling working
orders, including those from earlier runs.

The simulator uses the best bid or ask and available quoted quantity; it does
not model order-book depth or queue position. For further changes, see the
[order schema](strategy.capnp) and
[WebSocket gateway guide](docs/api/ws-gateway.md).

## Strategies

The *ws-strategy.py* strategy uses our REST based API for reference and market data and websocket based API for order entry. These APIs are best for rapid prototyping and quickly deploying your strategies to market.
We also have low latency APIs that suit a stategy that require higher performance. You can refer to *tcp-strategy.py*
for the example of their usage.

The following table lists examples, how to run them and underlying technologies used. Each file documents individual strategy's behavior and command-line options; use `--help` to view them.



| Strategy | Orders | Reference data | Market data | Command |
| --- | --- | --- | --- | --- |
| [Asynchronous WebSocket](ws-strategy.py) | [WebSocket](docs/api/ws-gateway.md) | [REST](docs/api/rest-reference.md) | [REST](docs/api/rest-market-data.md) | `python ws-strategy.py --token "<TOKEN>"` |
| [Synchronous WebSocket](ws-strategy-sync.py) | [WebSocket](docs/api/ws-gateway.md) | [REST](docs/api/rest-reference.md) | [REST](docs/api/rest-market-data.md) | `python ws-strategy-sync.py --token "<TOKEN>"` |
| [Carnitas](tcp-strategy.py) | [Carnitas](docs/api/tcp-orders.md) | [Carnitas](docs/api/tcp-orders.md#reference-data) | [Carnitas](docs/api/tcp-market-data.md) | `python tcp-strategy.py --token "<TOKEN>"` |

## Services

The strategies use the following services. Each guide
describes the requests and responses, with examples.

| Service | Default port | Purpose |
| --- | ---: | --- |
| [WebSocket order gateway](docs/api/ws-gateway.md) | 8034 | Submit orders and receive responses |
| [REST reference data feed](docs/api/rest-reference.md) | 8036 | Retrieve accounts, securities, venues, positions, and limits |
| [REST market data feed](docs/api/rest-market-data.md) | 8035 | Query the latest requested price fields |
| [Carnitas order gateway](docs/api/tcp-orders.md) | 8032 | Submit orders and receive reference data and order responses |
| [Carnitas market data feed](docs/api/tcp-market-data.md) | 8033 | Receive streamed price updates |

We use Cap'n Proto schemas for [orders](strategy.capnp) and
[reference data](reference.capnp). Each service guide documents their usage with example.

## Connection settings

Use the hostname, ports, and order-entry token supplied for your connection.
The same sample code connects to Titan and hosted services; retrieve reference
data from the deployment you are using. For hosted services, use the
connection details provided by Featuremine.

| Option | Purpose |
| --- | --- |
| `--host`, `--port` | Order-service hostname and port |
| `--market-port` | REST price port for WebSocket examples; streaming market-data port for Carnitas |
| `--reference-port` | REST reference-data port for WebSocket examples |
| `--tls` | Use WSS/HTTPS in WebSocket examples when the supplied endpoint provides TLS; unavailable in the Carnitas example |
| `--schemas` | Directory containing compatible schemas; defaults to the script's directory |

## License

This repository is licensed under the [MIT License](LICENSE),
except for files that explicitly specify a different license in their headers.

Files marked as Featuremine Proprietary are covered by the
[Featuremine Proprietary License](LICENSE-RESTRICTED). It permits use, copying,
and modification solely for use with local Featuremine Titan or
Featuremine-owned hosted services. Original and modified copies must retain
this license and all original notices. Sharing and redistribution require
prior written authorization from Featuremine.
