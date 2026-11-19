# Getting started

This repository contains sample strategies you can run with Titan, Featuremine's local development environment, and our hosted services.

Start with Titan which provides access to real Kraken market data and a simulated trading venue on your computer.

You can request the latest Titan package from the Featuremine team at [www.featuremine.com](https://www.featuremine.com).

## Run a strategy

The sample strategies in this repository may be used and modified only for use with local Featuremine Titan or Featuremine-owned hosted services, under the [proprietary license](LICENSE-RESTRICTED).

### Prepare the sample

Download and unpack the Samples repository, then open a terminal in its main
folder—the one containing `requirements.txt`.

Install [Python 3.9 or later](https://www.python.org/downloads/); we recommend
using a [virtual environment](https://docs.python.org/3/library/venv.html).
The `python` commands below assume an activated virtual environment.
From the repository root, install the requirements:

```sh
python -m pip install -r requirements.txt
```

Install Titan using the instructions provided with your access.

### Start Titan

Start up your titan application, once it has opened, you will be able to see the **Sessions** screen in which you can select the **Default** session and click **Start**. Wait for all timeout indicators to show up as green before running the sample.

On a new installation, the **Default** session includes four preconfigured securities (XBT/USD, XBT/EUR, ETH/USD and ETH/EUR), one client with one account, and one simulated execution venue.

### Run the sample

Hover your mouse over the **Default** profile name in the running workspace to find its
connection details. In the popup, click **Copy order-entry token** for the default client which you will need to run your strategy.

Run the synchronous WebSocket sample from the repository root. Replace
`<TOKEN>` with the complete token you copied:

```sh
python ws-strategy-sync.py --token "<TOKEN>"
```

The example submits one immediate-or-cancel (IOC) order for each eligible account/security/venue combination. A side is randomly chosen after ensuring the quote price and size are finite and positive. Buys use the ask; sells use the bid.

The orders are sent after recovering positions by using the position obtained from the reference data and the replayed execution reports. In the example, position tracking does not change how the side or size of the order is chosen.

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
its license header. The copy will load the same bundled schemas.

Make the following changes in the copy, leaving the original script unchanged.

Change `timeInForce` from `ioc` to `day`:

```python
"timeInForce": "day",
```

Change the limit price to move it away from the selected quote:

```python
"orderType": {"limit": price * (0.99 if side == "buy" else 1.01)},
```

Since the order can rest when its limit price does not cross the market once it is placed, you will now be able to see how your order gradually filled once the market moves towards the order.

Keep the other fields unchanged. With Titan still running, use the same
order-entry token:

```sh
python my-strategy.py --token "<TOKEN>"
```

Under **Orders/Manager**, compare the working DAY orders with the IOC
execution responses from the first run. The script will output placement acknowledgements for the orders placed and time out if the orders are not done before the script timeout.

You will be able to find the incoming fills and updates relevant to your order by using the **Orders/Manager** tab.

Once you are ready to make additional changes, please refer to the
[order schema](strategy.capnp) and [WebSocket gateway guide](docs/api/ws-gateway.md) for additional reference regarding the content of the messages you can send to Featuremine and how send them.

## Strategies

The *ws-strategy-sync.py* and *ws-strategy.py* strategies use our REST API for
reference and market data and WebSocket API for order entry. These APIs are
best for rapid prototyping and quickly deploying your strategies to market.
We also have low latency APIs that suit strategies that require higher
performance. You can refer to *tcp-strategy.py* for an example of their usage.

The following table lists the examples, their run commands, and the services
they use. Each script documents its behavior and command-line options; use
`--help` to view them.

| Strategy | Orders | Reference data | Market data | Command |
| --- | --- | --- | --- | --- |
| [Synchronous WebSocket](ws-strategy-sync.py) | [WebSocket](docs/api/ws-gateway.md) | [REST](docs/api/rest-reference.md) | [REST](docs/api/rest-market-data.md) | `python ws-strategy-sync.py --token "<TOKEN>"` |
| [Asynchronous WebSocket](ws-strategy.py) | [WebSocket](docs/api/ws-gateway.md) | [REST](docs/api/rest-reference.md) | [REST](docs/api/rest-market-data.md) | `python ws-strategy.py --token "<TOKEN>"` |
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
[reference data](reference.capnp). The service guides include examples using
these schemas.

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
| `--timeout` | Startup and order-response budgets in seconds; positive and finite, 30 by default |

The startup budget runs from connection setup through discovery, recovery,
and sending the complete batch. A fresh budget then bounds the wait for
terminal order responses. Intermediate messages and retries do not reset
either deadline.

## License

This repository is licensed under the [MIT License](LICENSE),
except for files that explicitly specify a different license in their headers.

Files marked as Featuremine Proprietary are covered by the
[Featuremine Proprietary License](LICENSE-RESTRICTED). It permits use, copying,
and modification solely for use with local Featuremine Titan or
Featuremine-owned hosted services. Original and modified copies must retain
this license and all original notices. Sharing and redistribution require
prior written authorization from Featuremine.
