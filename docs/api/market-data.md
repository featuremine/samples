# Market-Data REST API

The price service exposes cached market-data fields for numeric security
identifiers. The WebSocket strategy uses it after
[reference discovery](reference.md). See the
[WebSocket integration guide](websocket.md) for the full workflow and the
[repository README](../../README.md) for run commands.

Detailed sample behavior is documented in the [WebSocket strategy guide](../strategies/websocket.md).

## Endpoint and Access

The default Titan price port is **8035**. Query it using
`POST /api/prices` with `Content-Type: text/plain; charset=us-ascii`.

The current price service does not validate an authorization token. The
WebSocket sample sends its token on price requests as well as reference
requests, but this does not restrict access to prices.

Titan serves plain HTTP. Use HTTPS through a TLS endpoint when configured.

## Request Body

The first body line lists field IDs. The remaining whitespace-separated tokens
are numeric security identifiers obtained from reference data. The samples
request ask price FID **25** and ask quantity FID **735**:

```text
25 735
<SECURITY_ID>
```

Replace `<SECURITY_ID>` with an identifier returned by the session. Multiple
security identifiers may appear on the remaining lines.

## Response Body

A successful response uses `text/plain; charset=us-ascii`. Each row begins with
the requested security identifier, followed by field/value pairs in request
order:

```text
<SECURITY_ID> 25 <ASK_PRICE> 735 <ASK_QUANTITY>
```

An unavailable field is represented by `<FIELD_ID> N/A`. A security without an
available mapped price stream is represented by `<SECURITY_ID> N/A`.

These are cached field values. Clients must check for missing fields and
validate that a price and quantity are finite and positive before submitting
an order. The samples use those checks and cap each IOC order at one unit;
the request fields are described in the [order API](orders.md).

## Startup Recovery

The service returns HTTP 503 until its initial market and symbology snapshots
have been consumed. Retry before selecting the order batch. Once ready, the
service follows updates and replaces the affected cached fields.

## Status Codes and Limits

| Status | Meaning |
| ---: | --- |
| 200 | Price rows returned; individual values may be `N/A` |
| 400 | Invalid ASCII body, field/security list, or response construction |
| 404 | Unsupported path |
| 413 | Request body exceeds 16 MiB |
| 415 | Missing or unsupported content type |
| 503 | Initial market or symbology snapshot is still being recovered |

The response buffer is bounded to 32 MiB and individual output rows are
bounded. Request only the securities and fields needed by the client.

The request and response parsers used by the sample are in
[ws-strategy.py](../../ws-strategy.py).
