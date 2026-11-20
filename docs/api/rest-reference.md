# REST reference data feed

Use the REST reference data feed to retrieve the securities available at each
venue, the accounts configured to trade there, and account positions and
limits. For a local run, see [Getting started](../../README.md). The
[WebSocket gateway](ws-gateway.md) guide explains the order workflow.

## Connection and authentication

Send requests to the running session's reference port, 8036 by default. Put
the complete order-entry token in the `Authorization` header, without a
`Bearer ` prefix. A missing or unknown token returns HTTP 400.

Titan's embedded listener uses HTTP. Use HTTPS when an external endpoint
provides TLS.

Each client in Titan's **Accounts** section has its own name, token, and
accounts. The token identifies that client and gives access only to its
accounts. `Account.client` contains the owning client's name. New sessions
publish the configured account name as `VenueAccountMapping.venueAccount`,
the broker account field. Use identifiers from the running session rather
than assuming values from a different profile or recording.

Start a new session after changing client identities or account definitions;
existing recordings keep their original definitions.

## Requests

Send GET requests to these routes. The token selects the accounts and related
records you can retrieve. `/limitMaster` returns the latest definition of each
limit after authentication.

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

Use HEAD on the same paths to obtain the selected response's content length
without receiving its body.

## Responses

Successful responses have `Content-Type: application/json`. Each is an array
of [reference schema](../../reference.capnp) messages, including their wrappers.
For an account, read `record["message"]["account"]`.

Each response contains at most one record per key. Use these keys when
matching updates:

- Accounts, securities, and venues: `identifier`. Global limit definitions:
  `limitId`.
- Account-to-venue mappings: account `identifier` and `venueID`.
  Venue-to-security attributes: `venueID` and `securityId`.
- Positions: `accountId` and `securityId`.
- Risk and marking limits: account ID, `limitId`, and `symbolAggregation`.

### JSON representation

- Enums are JSON numbers.
- Inactive union members are omitted. A selected void member is `null`.
- Unset text, struct, and list fields are omitted. An explicitly set empty
  text value is `""`.
- Nonfinite floating-point values are `null`.
- A 64-bit integer is a JSON number when JavaScript's shortest decimal form
  of that number matches the original integer's decimal text. Otherwise, it
  is a decimal string.

Use `int(value)` for identifiers in Python to accept both numeric forms.
Access fields through their message wrappers.

## Example

Retrieve accounts and convert their identifiers to Python integers:

```python
import json
import urllib.request


def read_accounts(host, port, token, timeout=30, tls=False):
    scheme = "https" if tls else "http"
    request = urllib.request.Request(
        f"{scheme}://{host}:{port}/accounts",
        headers={"Authorization": token},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        records = json.load(response)
    return [int(record["message"]["account"]["identifier"])
            for record in records]
```

Use returned security identifiers to query the
[REST market data feed](rest-market-data.md). The documented
[synchronous](../../ws-strategy-sync.py) and
[asynchronous](../../ws-strategy.py) examples combine reference discovery
with price queries and orders.

## Recovery and updates

Account-to-venue mappings determine which venues you can retrieve.
Venue-to-security attributes determine which securities you can retrieve.
A venue or security is omitted from its definition route until its definition
is available. A valid token with no assigned accounts receives empty scoped
arrays but can still read `/limitMaster`.

Repeat a GET request to refresh the data. An update replaces the record with
the same key. Account reassignments can change the records visible to a token.
Risk and marking limits remain separate for different symbol aggregations.
Use identifiers rather than relying on array order.

Titan's `/positions` records provide initial position seeds. The examples
combine these seeds with replayed executions and keep updating positions
from live execution reports; see
[position recovery](ws-gateway.md#recovery-announcement).

During startup, a successful response can contain only part of the initial
data. Repeat requests until the definitions you need are available. If records
remain missing, check the token's account scope, account-to-venue mappings,
venue-to-security attributes, and definitions.

## Errors and limits

| HTTP status | Meaning |
| ---: | --- |
| 200 | Reference array returned, possibly empty |
| 400 | Missing or unknown token; check `Authorization` |
| 404 | Unsupported path or method; use GET or HEAD on a route above |
| 413 | Selected JSON response exceeds 32 MiB |
| 500 | Response could not be assembled |
