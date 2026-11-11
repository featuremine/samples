# Market-Data REST API

Use the market-data API to request price fields for security identifiers
obtained from the [reference API](rest-reference.md). See the
[WebSocket integration guide](ws-gateway.md) for the connection workflow and the
[WebSocket strategy guide](../strategies/websocket.md) to run the sample.

## Endpoint and Access

Send `POST /api/prices` to Titan's price port, **8035** by default, with
`Content-Type: text/plain; charset=us-ascii`.

The price endpoint requires no authorization token. The WebSocket sample
includes its token in price requests, but that header does not restrict which
prices the endpoint returns.

Use HTTP for Titan's embedded listener. Use HTTPS when connecting through an
endpoint that provides TLS.

## Request Body

Use an ASCII body. Put the field IDs on the first line, separated by spaces,
then add numeric security identifiers separated by whitespace. Include at
least one field and one security.

For example, the current WebSocket sample requests ask price FID **25** and
ask quantity FID **735**:

```text
25 735
<SECURITY_ID>
```

Replace `<SECURITY_ID>` with an identifier returned by reference discovery.
You can include several security identifiers in one request.

## Response Body

A successful response has `Content-Type: text/plain; charset=us-ascii`. Each
returned row starts with the security identifier, followed by the requested
field/value pairs in request order:

```text
<SECURITY_ID> 25 <ASK_PRICE> 735 <ASK_QUANTITY>
```

Treat `<FIELD_ID> N/A` as a missing field. A row containing only
`<SECURITY_ID> N/A` means no mapped price stream is available for that security.

For the IOC buy shown in these guides, require a present, finite, positive ask
price and ask quantity. The current TCP and WebSocket IOC samples apply those
checks and use the smaller of the ask quantity and one unit. See the
[strategy schema](../../strategy.capnp) for the order fields.

## Startup Recovery

Retry HTTP 503 responses while startup data loads. A successful response can
still contain only part of the initial data, so repeat the query if the fields
you need are missing. Each query reads the current cached values;
repeat queries as needed to obtain market-data updates.

## Status Codes and Limits

| Status | Meaning |
| ---: | --- |
| 200 | Price rows returned; individual values may be `N/A` |
| 400 | Invalid ASCII body, field/security list, or response construction |
| 404 | Unsupported path; use `/api/prices` |
| 413 | Request body exceeds 16 MiB or cannot be buffered |
| 415 | Send `Content-Type: text/plain; charset=us-ascii` |
| 503 | Startup data is still loading; retry the request |

Requests are limited to 16 MiB, responses are limited to 32 MiB, and individual rows also have a size limit of 383 bytes.
If a response cannot be constructed, reduce the number of securities or fields in the query.

For an example request and response parser, see
[ws-strategy.py](../../ws-strategy.py).
