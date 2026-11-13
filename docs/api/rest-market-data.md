# REST market data feed

Use the REST market data feed to query the latest price fields for security
identifiers obtained from the [REST reference data feed](rest-reference.md).
For a local run, see [Getting started](../../README.md). The documented
[asynchronous](../../ws-strategy.py) and
[synchronous](../../ws-strategy-sync.py) examples use this feed.

## Connection and authentication

Send requests to the running session's REST market-data port, 8035 by default.
Titan's embedded listener uses HTTP. Use HTTPS when an external endpoint
provides TLS.

This feed requires no authorization token. The asynchronous example includes
its token in price requests, but that header does not restrict which prices
are returned.

## Requests

Send `POST /api/prices` with `Content-Type: text/plain; charset=us-ascii`.
Use an ASCII body with field identifiers (FIDs) on its first line, separated by
spaces, followed by numeric security identifiers separated by whitespace.
Include at least one field and one security.

A FID selects a value for a security; it is not a security identifier. The
local Kraken feed uses these fields:

| FID | Value |
| ---: | --- |
| 22 | Bid price |
| 25 | Ask price |
| 730 | Bid quantity |
| 735 | Ask quantity |
| 6 | Trade price |
| 178 | Trade quantity |

For example, request both sides of the quote:

```text
22 25 730 735
<SECURITY_ID>
```

Replace `<SECURITY_ID>` with an identifier from reference discovery. Include
several security identifiers to query them together.

## Responses

A successful response has `Content-Type: text/plain; charset=us-ascii`. Each
row starts with the security identifier, then the requested field/value pairs
in request order:

```text
<SECURITY_ID> 22 <BID_PRICE> 25 <ASK_PRICE> 730 <BID_QUANTITY> 735 <ASK_QUANTITY>
```

`<FIELD_ID> N/A` means that field is missing. A row containing only
`<SECURITY_ID> N/A` means no mapped price stream is available for that security.

The asynchronous examples require a finite, positive price and quantity for
the chosen side. A buy uses ask fields 25 and 735; a sell uses bid fields 22
and 730. They randomly choose among usable sides and submit at most one unit.
Order fields are defined in [strategy.capnp](../../strategy.capnp).

## Example

Make one price query with the standard Python HTTP library:

```python
import urllib.request


def query_prices(host, port, security_ids, timeout=30, tls=False):
    scheme = "https" if tls else "http"
    body = "22 25 730 735\n" + " ".join(map(str, security_ids)) + "\n"
    request = urllib.request.Request(
        f"{scheme}://{host}:{port}/api/prices",
        data=body.encode("ascii"),
        headers={"Content-Type": "text/plain; charset=us-ascii"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("ascii")
```

The [asynchronous example](../../ws-strategy.py) also parses missing fields
and retries startup responses. The synchronous example sends a GET request
with an ASCII body; check support for that form when using it with another
server.

## Recovery and updates

Retry HTTP 503 while startup data loads. A successful response can still
contain only part of the initial data; repeat the query if required fields
are missing. Each request reads the current cache, so query again for updates.

## Errors and limits

| HTTP status | Meaning |
| ---: | --- |
| 200 | Price rows returned; individual values can be `N/A` |
| 400 | Invalid ASCII body, field/security list, or response construction |
| 404 | Unsupported path; use `/api/prices` |
| 413 | Request body exceeds 16 MiB or cannot be buffered |
| 415 | Send `Content-Type: text/plain; charset=us-ascii` |
| 503 | Startup data is loading; retry |

Requests are limited to 16 MiB, responses to 32 MiB, and individual rows to
383 bytes. If a response cannot be constructed, reduce the number of
securities or fields in the query.
