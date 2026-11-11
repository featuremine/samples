# Old strategy: WebSocket and REST

The [old strategy](../../ws-strategy-old.py) uses a WebSocket connection for
orders and REST services for reference data and prices. Follow the Python and
Titan setup in the [main README](../../README.md) before running it.

This example chooses random target positions and sends a single batch of buy
or sell DAY limit orders using the DMA algorithm. Every order uses the fixed
limit price `10`. Completion means each submitted order has received a
forwarding acknowledgement or a forwarding failure.

Run these commands from the repository root, with the virtual environment
active and the Titan session running. The old script also imports `requests`,
which is additional to the shared [requirements](../../requirements.txt):

```sh
python -m pip install requests
python ws-strategy-old.py --token "<TOKEN>"
```

Use the complete profile order-entry token. The script passes it directly in
the reference requests' and WebSocket upgrade's `Authorization` header.

The [WebSocket API](../api/websocket.md) describes integration, the
[WebSocket protocol](../protocol/websocket.md) defines recovery and framing,
and the [order API](../api/orders.md) defines requests and responses.

## Options and endpoints

| Option | Default | Purpose |
| --- | --- | --- |
| `--token` | Required | Profile order-entry token |

To list the command-line options:

```sh
python ws-strategy-old.py --help
```

The host and ports are module constants at the top of the script:

| Constant | Default | Purpose |
| --- | --- | --- |
| `HOST` | IPv4 loopback | Host shared by all three services |
| `WS_PORT` | `8034` | WebSocket order-entry port |
| `PRICES_PORT` | `8035` | REST price port |
| `REST_PORT` | `8036` | REST reference-data port |

For different endpoints, edit these constants to match the running session.
For Titan's default wildcard **Host**, the script's loopback setting is
appropriate. For another **Host**, use that configured address. Endpoints use
plain WS and HTTP; endpoint overrides and TLS are not command-line options.

## Schemas and discovery

The script loads [strategy.capnp](../../strategy.capnp) from its own directory,
including when invoked from another working directory. Keep the imported
schema files alongside it. There is no schema-directory option or WebSocket
schema-version handshake, so the bundled schema must match the running service.

Reference discovery uses authenticated GET requests to `/accounts`, `/venues`,
`/securities`, `/venueSecurityAttributes`, `/venueAccountMappings`, and
`/positions`. These return the schema-wrapper JSON described by the
[reference API](../api/reference.md). Empty account, venue, security, or mapping
results cause an error.

The initial price query sends **GET `/api/prices` with a request body**, using
`Content-Type: text/plain; charset=us-ascii`. It requests bid field `22` and ask
field `25` for securities in the venue-security attributes. The current
[market-data API guide](../api/market-data.md) documents POST for price queries;
check that the server accepts the old script's GET-with-body form.

The script parses the price response, but its price-availability filter is
commented out. Those prices do not determine eligibility, limit price, or order
quantity.

## Order selection and sizing

1. For each security in the venue-security attributes, choose one venue at
   random and one of that venue's mapped accounts. Skip a venue without mapped
   accounts. An empty set of supported combinations causes an error.
2. Choose a random subset containing between one and `min(1000, supported
   combinations)` entries.
3. Assign each selected account/security pair an integer target position from
   `-999` through `1001`, inclusive.
4. Calculate the current position as the REST position plus signed fills
   consumed during WebSocket recovery. Round `target - current` to obtain the
   order quantity, and skip zero quantities.
5. Send a buy for a positive quantity or a sell for a negative quantity. Use its
   absolute quantity, limit price `10`, DAY time in force, DMA, and no maximum
   floor. Each order identifier comes from `time_ns()`.

In Titan, the first account's **Account name** supplies the connection's client
identity and reference scope. Accounts with different names are outside the
profile token's scope. Use the account, venue, and security identifiers returned
by the running session.

## Recovery and timeouts

After REST discovery, the script opens its WebSocket connection, reads the
initial recovery announcement, and consumes the advertised `pending` messages
before sizing new orders. For known accounts and supported securities, it adds
numeric `sess.exec` filled and partially-filled quantities to its recovered
position totals, applying the order side's sign. It does not process `exec2`
fills for this calculation.

WebSocket operations use a ten-second socket timeout. REST calls specify no
timeout and perform no retries; HTTP errors, including startup recovery errors,
are raised immediately. There is no overall batch-completion deadline.

Each invocation chooses new targets and creates new order identifiers. It does
not cancel or track outstanding orders from earlier invocations.

## Completion and output

The script prints its recovery count, each order's side, quantity, current and
target positions, and a final acknowledgement summary:

```text
Recovering <COUNT> messages
Placing <SIDE> <QUANTITY> pos <CURRENT> target <TARGET> for security <SECURITY_ID>
...
Order state:
Pending: 0
PlaceForwarded: <COUNT>
Failed: <COUNT>
Done
```

Only `ctrl.placeForwarded` and `ctrl.failed` clear newly submitted orders from
the pending set. The script does not wait for terminal execution, cancellation,
or rejection responses. DAY orders can remain active in the running session
after `Done` and after the WebSocket connection closes.

## Troubleshooting

- For an import error, install the shared requirements and the additional
  `requests` dependency in the active virtual environment.
- For connection errors, check `HOST` and the three port constants against the
  running session's endpoints.
- For authentication errors, copy the complete order-entry token from Titan.
- For a price-request error or a stalled initial query, check the server's
  GET-with-body support and its startup recovery status. The script has no
  automatic retry or REST timeout.
- For empty reference data, check account ownership, venue-account mappings,
  security definitions, and venue-security attributes.
- A forwarding acknowledgement confirms forwarding only. Inspect the running
  session for subsequent executions and any remaining active DAY orders.
