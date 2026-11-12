# Reference REST API

Use the reference API to retrieve the securities available at each venue,
the accounts configured to trade there, and account positions and limits.

See the [WebSocket API guide](ws-gateway.md) for the connection workflow
and the [WebSocket strategy guide](../strategies/websocket.md) to run the sample.

## Endpoint and authentication

Send GET requests to Titan's reference port, 8036 by default. Put the
complete client order-entry token in the `Authorization` header:

```http
GET /accounts HTTP/1.1
Host: <HOST>:<REFERENCE_PORT>
Authorization: <TOKEN>
```

Send the token without a `Bearer ` prefix. A missing or unknown token returns
HTTP 400.

Each client in Titan's **Accounts** section has its own name, order-entry token,
and accounts. The token identifies that client and exposes only its accounts.
An account's `Account.client` is its owning client's name. New sessions publish
the configured account name as `VenueAccountMapping.venueAccount`, the broker
account field. Use the identifiers returned by reference discovery in the
running session. Start a new session after changing client identities or
account definitions; existing recordings remain unchanged.

Use HTTP for Titan's embedded listener. Use HTTPS when connecting through an
endpoint that provides TLS.

## Routes

Successful responses have `Content-Type: application/json`. Each response is
an array of [reference schema](../../reference.capnp) messages, including their
wrappers. For an account entry, read `record["message"]["account"]`.

The token determines which accounts and related records you can retrieve.
`/limitMaster` returns the latest definition of each limit after authentication.

| GET path | Records returned | Schema member |
| --- | --- | --- |
| `/accounts` | Accounts available to you | `RiskData.message.account` |
| `/venueAccountMappings` | Account-to-venue mappings | `VenueData.message.venueAccountMapping` |
| `/venueSecurityAttributes` | Venue-to-security attributes | `VenueData.message.venueSecurityAttribute` |
| `/securities` | Security definitions | `Symbology.message.securityDefinition` |
| `/venues` | Venue definitions | `VenueData.message.venue` |
| `/positions` | Account positions | `RiskData.message.position` |
| `/limitMaster` | Global limit definitions | `RiskData.message.limitMaster` |
| `/riskLimits` | Account risk limits | `RiskData.message.riskLimit` |
| `/markingLimits` | Account marking limits | `RiskData.message.markingLimit` |

Each response contains at most one record per key. Use these keys to match
updates:

- Accounts, securities, and venues: `identifier`. Global limit definitions:
  `limitId`.
- Account-to-venue mappings: account `identifier` and `venueID`.
  Venue-to-security attributes: `venueID` and `securityId`.
- Positions: `accountId` and `securityId`.
- Risk and marking limits: account ID, `limitId`, and `symbolAggregation`.

## Visibility and updates

Your account-to-venue mappings determine which venues you can see.
Venue-to-security attributes determine which securities you can see. A venue
or security is omitted from its definition endpoint until its definition is
available. A valid token with no assigned accounts receives empty scoped
arrays, but can still read `/limitMaster`.

Repeat a GET request to refresh your data. An update replaces the previous
record with the same key. Account reassignments can change the records visible
to your token. Risk and marking limits remain separate for different symbol
aggregations. Use record identifiers rather than relying on array order.

During startup, a successful response can contain only part of the initial
reference data. Check for the definitions you need and repeat the
request until they are available. If records remain missing, check the token's
account scope and the account, venue, and security relationships.

Use HEAD on the same paths to obtain the selected response's content length
without receiving its body.

## JSON representation

- Enums are returned as JSON numbers.
- Inactive union members are omitted. A selected void member has the value
  `null`.
- Unset text, struct, and list fields are omitted. An explicitly set empty
  text value is `""`.
- Nonfinite floating-point values are `null`.
- A 64-bit integer is returned as a JSON number when JavaScript's shortest
  decimal form of that number matches the original integer's decimal text.
  Otherwise, it is returned as a decimal string.

In Python, use `int(value)` for identifiers to accept both numeric forms.
Access fields through their message wrappers, as shown in the account example
above.

## Status codes and limits

| Status | Meaning |
| ---: | --- |
| 200 | Reference array returned, possibly empty |
| 400 | Missing or unknown token; check the `Authorization` header |
| 404 | Unsupported path or method; use GET or HEAD on a route above |
| 413 | Selected JSON response exceeds 32 MiB |
| 500 | Response could not be assembled |

The [WebSocket sample](../../ws-strategy.py) demonstrates discovery using
`/securities`, `/accounts`, `/venueAccountMappings`, `/venueSecurityAttributes`,
and `/positions`. Use the returned security identifiers to request quotes from
the [Market data REST API](rest-market-data.md).
