# Reference REST API

Use the reference API to retrieve the accounts, securities, venues, positions,
and limits available to your token. The responses include the relationships
needed to select an account and venue for an order.

See the [WebSocket integration guide](websocket.md) for the connection workflow
and the [WebSocket strategy guide](../strategies/websocket.md) to run the sample.

## Endpoint and Authentication

Send GET requests to Titan's reference port, **8036** by default. Put the
complete profile token in the `Authorization` header:

```http
GET /accounts HTTP/1.1
Host: <HOST>:<REFERENCE_PORT>
Authorization: <TOKEN>
```

Send the token without a `Bearer ` prefix. A missing or unknown token returns
HTTP 400.

The first account's **Account name** identifies your strategy in Titan. The
token exposes accounts with matching names. Use the identifiers returned by
reference discovery in the running session. After renaming an account, start
a new session before requesting reference data.

Use HTTP for Titan's embedded listener. Use HTTPS when connecting through an
endpoint that provides TLS.

## Routes

Successful responses have `Content-Type: application/json`. Each response is
an array of [reference-schema](../../reference.capnp) messages, including their
wrappers. For an account entry, read `record["message"]["account"]`.

| GET path | Schema member | Returned records and identity |
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
reference data. Check for the definitions your client needs and repeat the
request until they are available. If records remain missing, check the token's
account scope and the account, venue, and security relationships.

Use HEAD on the same paths to obtain the selected response's content length
without receiving its body.

## JSON Representation

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

## Status Codes and Limits

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
the [market-data REST API](market-data.md).
