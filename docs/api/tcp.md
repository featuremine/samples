# TCP API — Integration Guide

This guide describes the Carnitas TCP services used by
[tcp-strategy.py](../../tcp-strategy.py) to discover reference data, receive market
updates, and submit orders to a Titan session. For byte layouts, version checks,
and recovery counters, see the [TCP protocol specification](../protocol/tcp.md).
For setup and run commands, see the [repository README](../../README.md).

Detailed sample behavior is documented in the [TCP strategy guide](../strategies/tcp.md).

Application orders and responses use the shared
[order API](orders.md). Reference messages use the bundled
[reference schema](../../reference.capnp).

## Connections and Authentication

Start a Titan session, then use its profile's **Connections** settings and
**order-entry token**. The sample opens two connections to the same host:

| Service | Default port | Data used by the sample |
| --- | ---: | --- |
| Orders and reference data | 8032 | Reference definitions, account/venue mappings, order requests and responses |
| Market data | 8033 | Stream announcements and Elektron price updates |

Each connection starts with a binary token-and-version handshake. Use the
profile token as its 256 token bytes; this is not an HTTP `Authorization`
header. The bundled TCP client has no TLS option.

Titan's **Client name** defaults to `client`. It is the first venue's strategy
name and is also written to the accounts' `client` field. Carnitas uses this
same name for account filtering and for the order route together with the OMS
name. Clients select the route through their token, not through a field in each
TCP frame.

## Integration Stages

**1. Connect.** Open both TCP connections using the selected host and their
separate ports. Handle partial socket reads and writes.

**2. Handshake.** Send the v031 client handshake, including the schema version
and recovery count. Read and validate the complete server handshake on each
connection. The sample requests recovery from the beginning and requires an
exact match with the bundled schema version.

**3. Recover.** Process stream announcements and the advertised catch-up records
on both connections. The sample waits for both snapshots before choosing its
order batch. See [TCP recovery](../protocol/tcp.md) for the counters and sequence
rules.

**4. Discover reference data and prices.** Maintain the definitions and mappings
described below, then accumulate prices by their announced channel.

**5. Exchange orders and responses.** Send packed `ManagerMessage` payloads in
TCP type-100 frames. Continue processing execution events and failures while
maintaining transport heartbeats.

**6. Close.** Follow the TCP logout exchange described in the
[protocol specification](../protocol/tcp.md).

## Reference Discovery

Reference frames contain packed Cap'n Proto messages. Dispatch by the TCP
message type, then inspect the decoded schema's `message` union:

| TCP type | Schema | Members used by the sample |
| ---: | --- | --- |
| 101 | `reference/Symbology` | `securityDefinition`, `riskChannel` |
| 102 | `reference/VenueData` | `venueAccountMapping`, `venueSecurityAttribute` |
| 103 | `reference/RiskData` | `account`, `position` |

Use `securityDefinition.identifier` to identify a security and
`riskChannel.referenceId`/`channelName` to associate it with its price channel.
Join account definitions with `venueAccountMapping.identifier`/`venueID`, then
join the venue to `venueSecurityAttribute.venueID`/`securityId`. The strategy
uses these relationships rather than assuming identifiers from another
session. It loads positions as reference state but does not use them to choose
its demonstration orders.

For example, after obtaining a type-101 payload:

```python
import capnp

# Run from the repository root, or pass the corresponding schema path.
reference = capnp.load("reference.capnp")


def symbology_member(payload):
    message = reference.Symbology.from_bytes_packed(payload)
    return message.message.which()
```

The complete receive loop and dictionary updates are in
[tcp-strategy.py](../../tcp-strategy.py).

## Market Data

A type-0 announcement associates the frame's stream ID with its `peer:channel`
payload. Scope stream IDs by connection. For type 108, decode the payload as
consecutive MessagePack field/value objects and merge the update into the
corresponding channel's cached fields.

The sample reads ask price FID **25** and ask quantity FID **735**, validates
that both are finite and positive, and submits one IOC limit-buy batch for the
eligible account/security/venue combinations. The shared
[order API](orders.md#new-ioc-limit-order) describes its request fields.

## Order Responses and Liveness

Type-100 replies contain packed `strategy/ManagerMessage` values. Distinguish
forwarding control acknowledgements from session executions; correlate results
using `strgOrdID`. The sample finishes when every submitted order receives
`filled`, `canceled`, or `rejected`, and treats `message.sess.failed` as an error.
See the [order response contract](orders.md#order-responses).

The sample sends an empty TCP type-1 heartbeat every ten seconds on both
connections. This is distinct from schema-level OMS/session heartbeat messages.
Socket timeout, logout, checksum, and protocol-error handling are defined in
the [TCP specification](../protocol/tcp.md).
