# Reference REST API

The reference service exposes the latest reference data available to an
authenticated client. The WebSocket strategy uses it to discover the same
account/security/venue relationships that the TCP strategy receives as streams.
See the [WebSocket integration guide](websocket.md) for its place in the
order workflow and the [repository README](../../README.md) for run commands.

Detailed sample behavior is documented in the [WebSocket strategy guide](../strategies/websocket.md).

## Endpoint and Authentication

The default Titan reference port is **8036**. Send a GET request with the
profile's token as the complete `Authorization` header value:

```http
GET /accounts HTTP/1.1
Host: <HOST>:<REFERENCE_PORT>
Authorization: <TOKEN>
```

No `Bearer ` prefix is added. Missing or unknown tokens return HTTP 400.
Titan maps the profile tokens to the first configured account's **Account name**. Each
account's `Account.client` is seeded from its own name, so only accounts whose
names match the first account are in that token's scope. The first account's
name is also the strategy identity used for order routing and all fill models.
New profiles start with a first account named `client`; saved names are used as entered.
Renaming an account changes its ownership and requires a new Titan session.

Titan serves plain HTTP. Use HTTPS through a TLS endpoint when configured.

## Routes

Successful responses have `Content-Type: application/json` and contain arrays
of complete [reference-schema](../../reference.capnp) wrapper objects. For example,
read an account from `record["message"]["account"]`.

| GET path | Wrapper member | Selection and latest-record key |
| --- | --- | --- |
| `/accounts` | `RiskData.message.account` | Accounts whose `client` matches the authenticated client; keyed by `identifier` |
| `/venueAccountMappings` | `VenueData.message.venueAccountMapping` | Mappings for accessible accounts; keyed by account `identifier` and `venueID` |
| `/venueSecurityAttributes` | `VenueData.message.venueSecurityAttribute` | Attributes for accessible venues; keyed by `venueID` and `securityId` |
| `/securities` | `Symbology.message.securityDefinition` | Defined securities attributed to accessible venues; deduplicated by `identifier` |
| `/venues` | `VenueData.message.venue` | Defined venues mapped to accessible accounts; keyed by `identifier` |
| `/positions` | `RiskData.message.position` | Positions for accessible accounts; keyed by `accountId` and `securityId` |
| `/limitMaster` | `RiskData.message.limitMaster` | All latest limit definitions after authentication; keyed by `limitId` |
| `/riskLimits` | `RiskData.message.riskLimit` | Account-scoped limits for accessible accounts; keyed by account, `limitId`, and `symbolAggregation` |
| `/markingLimits` | `RiskData.message.markingLimit` | Account-scoped limits for accessible accounts; keyed by account, `limitId`, and `symbolAggregation` |

## Visibility and Updates

Account-to-venue mappings determine the accessible venues. Venue-to-security
attributes determine the accessible securities. A missing venue or security
definition is omitted from its definition endpoint. A valid token without
assigned accounts receives empty scoped arrays and can still read
`/limitMaster`.

Updates replace the corresponding cached record, including changes to an
account's client assignment. Risk and marking limits retain separate entries
for distinct symbol aggregations. Treat response array order as unspecified.

The server completes its initial reference snapshot before accepting requests.
HEAD uses the same selection as GET and advertises its content length without
a response body.

## JSON Representation

- Enums are JSON numbers.
- Active void union members are `null`; inactive members are omitted.
- Absent pointer fields are omitted; explicitly present empty text is `""`.
- Nonfinite floating values are `null`.
- A 64-bit integer is a JSON number when its JavaScript decimal number
  representation preserves the original decimal text, and a decimal string
  otherwise.

Normalize identifiers with `int(value)` in Python rather than assuming one
JSON representation. Preserve the wrapper nesting when accessing fields; the
API does not flatten the reference messages.

## Status Codes and Limits

| Status | Meaning |
| ---: | --- |
| 200 | Reference array returned, possibly empty |
| 400 | Missing or unknown authorization token |
| 404 | Unsupported path or method |
| 413 | Selected JSON response exceeds 32 MiB |
| 500 | Response could not be assembled |

The [WebSocket sample](../../ws-strategy.py) requests `/securities`, `/accounts`,
`/venueAccountMappings`, `/venueSecurityAttributes`, and `/positions`. It then
obtains quotes for eligible security identifiers from the
[market-data REST API](market-data.md).
