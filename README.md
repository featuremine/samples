# Titan samples

This repository contains samples for working with Titan. The TCP strategy is in
the repository's main directory, alongside its requirements and Cap'n Proto
schemas.

## TCP strategy

The sample connects to a running Titan session through its Carnitas TCP services.
It reads reference data and live prices, then submits one batch of simulated
immediate-or-cancel (IOC) limit buy orders. Each order uses the current ask price
and a quantity of up to one unit for an eligible account, security, and venue.
The script exits when it receives a fill, cancellation, or rejection for every
order.

### Install requirements

You need Python 3 with `pip` and `venv`, and the Titan desktop application.
Open a terminal in this repository's main directory and create a virtual
environment.

On macOS or Linux:

```sh
python3 -m venv fm-venv
source fm-venv/bin/activate
```

On Windows, using PowerShell:

```powershell
py -3 -m venv fm-venv
fm-venv\Scripts\Activate.ps1
```

With the virtual environment active, install the dependencies:

```sh
python -m pip install -r requirements.txt
```

This installs `pycapnp` for Cap'n Proto messages and `msgpack` for price updates.

### Prepare Titan

1. Open Titan and create or open the profile you want to use.
2. Configure the session's reference data and price feed. The strategy needs
   securities, accounts, account-to-venue mappings, security-to-venue attributes,
   and risk channels linking securities to price streams.
3. In **Profile configuration**, use **Show tokens** beside **Order-entry token**
   to obtain the token for the profile.
4. Check the host and order-entry and market-data TCP ports in the profile's
   **Connections** section.
5. Start the session and keep it running while you run the sample.

### Run the strategy

In a terminal with the virtual environment active, run:

```sh
python tcp-strategy.py --token "<TOKEN>"
```

Replace `<TOKEN>` with the order-entry token from Titan. By default, the script
connects to `localhost`, using port `8032` for order entry and `8033` for market
data. If your profile uses different settings, supply them explicitly:

```sh
python tcp-strategy.py --host "<HOST>" --port <ORDER_PORT> --market-port <MARKET_PORT> --token "<TOKEN>"
```

Replace the host, ports, and token placeholders with your profile's settings.
Both connections use the same token.

The script loads `strategy.capnp`, `reference.capnp`, and
`schemas_version.capnp` from the directory containing `tcp-strategy.py`.
Keep the accompanying `common.capnp`, `go.capnp`, `c.capnp`, and `c++.capnp`
files in that directory too. The default schema location works even when you
invoke the script from another working directory. To use a different,
compatible schema set, pass `--schemas`:

```sh
python tcp-strategy.py --token "<TOKEN>" --schemas "<SCHEMA_DIRECTORY>"
```

A relative `--schemas` path is resolved from your terminal's working directory.
The schema version must match the running service.

To see all options:

```sh
python tcp-strategy.py --help
```

### Expected output

Once reference data and valid prices are available, the script prints:

```text
Placed <COUNT> orders using live prices
Order update: <EVENT>
...
Done
```

A cancellation or rejection is also a terminal response; `Done` means every
submitted order received a terminal response, rather than that every order filled.
If the script is waiting without placing orders, check that the session is
publishing reference data and a positive ask price and ask quantity for at least
one eligible account, security, and venue combination.

The default `--timeout` is 30 seconds for each connection and handshake, and for
the batch's order responses. It does not limit the initial wait for suitable
reference data and prices. Press **Ctrl+C** to stop the script.

If authentication fails, check that the token is exactly 256 ASCII characters
and belongs to the running session. After changing a profile's token, save the
profile and start a new session; existing sessions retain their original token.
If the script reports a schema-version mismatch, use schemas matching the
running Titan release.
