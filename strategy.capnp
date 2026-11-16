# Copyright (c) 2026 Featuremine. All rights reserved.
#
# Featuremine Proprietary - Restricted Use.
#
# This file is not covered by the repository's MIT License.
# Use, copying, modification, and redistribution require
# prior explicit written authorization from Featuremine.
#
# See LICENSE-RESTRICTED for the complete license terms.

@0x9c7a71efe87ba0d1;

using Go = import "go.capnp";
$Go.package("fmc");
$Go.import("fm-om/fmc");

using Cxx = import "c++.capnp";
$Cxx.namespace("fmc");

using C = import "c.capnp";
$C.fieldgetset;

using Common = import "common.capnp";

# Scope of an execution report for single- or multi-leg instruments.
enum MultiLegReportingType {
    single @0; # Report for a single instrument.
    individualLeg @1; # Report for one leg of a multi-leg instrument.
    multi @2; # Report for the multi-leg instrument.
}

# Envelope for strategy requests, OMS control messages, and session replies.
struct ManagerMessage {
    # Trading direction requested for a new order.
    enum Side {
        buy @0; # Buy the requested quantity.
        sell @1; # Sell the requested quantity.
    }
    # Execution-session order update with numeric prices and quantities.
    struct Exec {

        # Account position information included with an order update.
        struct Position {
            secId @0 :UInt64; # Security represented by this position entry.
            secSeqNum @1 :UInt64; # Sequence value associated with this security.
            qty @2: Float64; # Reported account position quantity.
            usedLocates @3: Float64; # Locate usage reported for this security.
        }

        # Order terms reported on placement or replacement.
        struct Placed {
            # Price instruction reported for the order.
            orderType : union {
              market @0 :Void; # Market order without an explicit limit price.
              limit @1 :Float64; # Reported limit price.
            }
            orderQuantity @2 : Float64; # Order quantity reported by the session.
        }

        # Execution details and order totals carried by a fill report.
        struct Filled {
            lastQuantity @0 :Float64; # Quantity attributed to this execution.
            lastPrice @1 :Float64; # Price attributed to this execution.
            lastFees @2 :Float64; # Fees attributed to this execution.
            liquidityCode @3 :Int64; # Liquidity classification supplied with the execution.
            cumQty @4 :Float64; # Reported cumulative executed quantity.
            leaves @5 :Float64; # Reported remaining order quantity.
            avgPx @6 :Float64; # Reported average execution price.
            lastMkt @7 :Text; # Market identifier associated with the execution.
        }

        # Order totals and execution reference carried by a correction or bust.
        struct Correction {
            cumQty @0 :Float64; # Reported cumulative executed quantity.
            leaves @1 :Float64; # Reported remaining order quantity.
            avgPx @2 :Float64; # Reported average execution price.
            lastQuantity @3 :Float64; # Quantity value reported with the correction or bust.
            execRefID @4 :Text; # Execution reference identifying the affected execution.
        }

        # Order totals carried by a status or restatement report.
        struct Status {
            cumQty @0 :Float64; # Reported cumulative executed quantity.
            leaves @1 :Float64; # Reported remaining order quantity.
            avgPx @2 :Float64; # Reported average execution price.
        }

        # Explanation supplied when an order is rejected.
        struct Rejected {
            reason @0 :Text; # Rejection explanation supplied by the session.
        }

        # Details carried by cancellation, expiry, or end-of-day reports.
        struct Canceled {
            leaves @0 :Float64; # Reported remaining order quantity.
            quantity @1 :Float64; # Quantity value reported with this event.
            reason @2 :Text; # Explanation supplied with the event.
        }

        strgOrdID @0: Int64; # Strategy order identifier used to correlate replies.
        accountID @1: Int64; # Account identifier associated with the order.
        securityId @2 : Int64; # Security identifier associated with the order.
        venueID @3: Int64; # Venue identifier associated with the order.
        orderSide @4: Common.Marking; # Reported trading-side and short-sale classification.
        sessOrdID @5: Text; # Session-side order identifier.
        exchExecID @6: Text;  # Execution identifier from SessionExec.execId.
        exchOrdID @7: Text; # Broker order identifier from SessionPlaced.brokerId.
        transactTime @23: Int64; # Broker transaction time
        executingBroker @24: Text; # Broker identified as executing the order.
        # Execution event and its event-specific payload.
        data: union {
            placed @8 :Placed; # Placement report containing the order terms.
            partiallyFilled @9 :Filled; # Partial execution with remaining order quantity.
            filled @10 :Filled; # Completed execution report.
            rejected @11 :Rejected; # Order rejection and its explanation.
            doneForDay @12 :Canceled; # End-of-day order report.
            canceled @13 :Canceled; # Order cancellation report.
            expired @14 :Canceled; # Order expiry report.
            replaced @15 :Placed; # Replacement report containing the updated terms.
            pendingNew @16 :Void; # New-order request is pending.
            pendingCancel @17 :Void; # Cancellation request is pending.
            pendingReplace @18 :Void; # Replacement request is pending.
            correction @19 :Correction; # Correction to a previously reported execution.
            bust @20 :Correction; # Trade-bust report referring to an execution.
            restated @21 :Status; # Restated order totals.
            status @22 :Status; # Order status and totals.
        }
        requestTime @25 :Int64; # Time when associated request is written to the socket
        tag @26:Text; # Application tag associated with the order.
        receiveTime @27 :Int64; # Time when execution is received from the socket
        reportingType @28 :MultiLegReportingType = single; # Single-instrument or multi-leg report scope.
        strgSocketNs @29 :Int64; # Nanoseconds from request placement to socket send.
        omsSocketNs @30 :Int64; # Nanoseconds from OMS receipt to socket send.
        socketStrgNs @31 :Int64; # Nanoseconds from socket receipt to writing the ManagerMessage.
        customTags @32 :List(Common.CustomField); # Additional tag/value metadata supplied with the report.
        accountPosition @33 :List(Position); # Account position entries included with the report.
    }

    # Request to create an order using numeric prices and quantities.
    struct Place {
        # Trigger price for a stop order.
        struct Stop {
            stopPx @0 :Float64; # Price that triggers the stop instruction.
        }
        # Trigger and limit prices for a stop-limit order.
        struct StopLimit {
            stopPx @0 :Float64; # Price that triggers the stop instruction.
            limitPx @1 :Float64; # Limit price for the stop-limit order.
        }
        strgOrdID @0: Int64; # New strategy order ID, retained for replies and later requests.
        accountID @1 : Int64; # Account identifier from reference data.
        securityId @2 : Int64; # Security identifier from reference data.
        venueID @3: Int64; # Venue identifier from reference data.
        orderSide @4 : Side; # Requested buy or sell direction.
        # Select the order's price instruction.
        orderType : union {
          market @5 :Void; # Market order without an explicit limit price.
          limit @6 :Float64; # Limit price; must be finite.
          stop @24 :Stop; # Stop instruction with a trigger price.
          stopLimit @25 :StopLimit; # Stop-limit instruction with trigger and limit prices.
        }
        quantity @7 : Float64; # Requested quantity; must be positive, non-zero and finite.
        # Select whether to constrain the displayed quantity.
        maxFloor :union {
          none @8 :Void; # No maximum displayed quantity supplied.
          maxFloor @9 :Float64; # Maximum displayed quantity; must be positive, non-zero and finite.
        }
        # Select whether to supply a minimum quantity constraint.
        minQty :union {
          none @17 :Void; # No minimum quantity supplied.
          minQty @18 :Float64; # Minimum quantity; must be positive, non-zero and finite.
        }
        timeInForce @10 : Common.TimeInForce; # Requested duration or execution policy.
        # Select direct market access or an algorithm representation.
        algorithm :union {
            dma @11 :Void; # Direct market access without an algorithm payload.
            deprecated1 @12 :Common.VWAP; # Deprecated VWAP parameter representation.
            deprecated2 @13 :Common.POV; # Deprecated percentage-of-volume parameter representation.
            deprecated3 @14 :Common.TWAP; # Deprecated TWAP parameter representation.
            deprecated4 @15 :Common.Ghost; # Deprecated Ghost parameter representation.
            deprecated5 @16 :Common.Iceberg; # Deprecated Iceberg parameter representation.
            deprecated6 @20 :Common.CustomAlgo; # Deprecated named-algorithm representation.
            algo @21: Text; # Textual algorithm specification understood by the OMS.
        }
        customTags @22 :List(Common.CustomField); # Additional tag/value fields for this request.
        tag @19:Text; # Application tag associated with the order.
        short @23 :Bool; # Short-sale flag accompanying the requested side.
        groupID @26 : Int64; # Identifier supplied for request-group coordination.
        groupCountdown @27 : Int64; # Countdown metadata associated with the request group.
    }

    # Request to cancel an existing strategy order.
    struct Cancel {
        strgOrdID @0: Int64; # Existing strategy order identifier to cancel.
        groupID @1 : Int64; # Identifier supplied for request-group coordination.
        groupCountdown @2 : Int64; # Countdown metadata associated with the request group.
    }

    # Order reference for a system-initiated cancellation.
    struct SystemCancel {
        strgOrdID @0: Int64; # Strategy order identifier affected by the cancellation.
    }

    # Request to change an existing order's price, quantity, or both.
    struct Replace {
        strgOrdID @0: Int64; # Existing strategy order identifier to replace.
        # Select a new price or leave the existing price unchanged.
        price :union {
          unknown @1 :Void; # Preserve the order's current price.
          price @2 :Float64; # Replacement price; must be finite.
        }
        # Select a new quantity or leave the existing quantity unchanged.
        quantity :union {
          unknown @3 :Void; # Preserve the order's current quantity.
          quantity @4 :Float64; # Replacement quantity; must be positive, non-zero and finite.
        }
        groupID @5 : Int64; # Identifier supplied for request-group coordination.
        groupCountdown @6 : Int64; # Countdown metadata associated with the request group.
    }

    # Execution-session order update with textual prices and quantities.
    struct Exec2 {
        # Account position information with quantities represented as text.
        struct Position {
            secId @0 :UInt64; # Security represented by this position entry.
            secSeqNum @1 :UInt64; # Sequence value associated with this security.
            qty @2: Text; # Reported account position quantity as text.
            usedLocates @3: Text; # Reported locate usage as text.
        }
        # Order terms reported on placement or replacement, using text values.
        struct Placed {
            # Price instruction reported for the order.
            orderType : union {
              market @0 :Void; # Market order without an explicit limit price.
              limit @1 :Text; # Reported limit price as text.
            }
            orderQuantity @2 : Text; # Order quantity reported by the session as text.
        }

        # Execution details and order totals with textual prices and quantities.
        struct Filled {
            lastQuantity @0 :Text; # Quantity attributed to this execution, as text.
            lastPrice @1 :Text; # Price attributed to this execution, as text.
            lastFees @2 :Text; # Fees attributed to this execution, as text.
            liquidityCode @3 :Int64; # Liquidity classification supplied with the execution.
            cumQty @4 :Text; # Reported cumulative executed quantity as text.
            leaves @5 :Text; # Reported remaining order quantity as text.
            avgPx @6 :Text; # Reported average execution price as text.
            lastMkt @7 :Text; # Market identifier associated with the execution.
        }

        # Text-valued order totals and execution reference for a correction or bust.
        struct Correction {
            cumQty @0 :Text; # Reported cumulative executed quantity as text.
            leaves @1 :Text; # Reported remaining order quantity as text.
            avgPx @2 :Text; # Reported average execution price as text.
            lastQuantity @3 :Text; # Quantity value reported with the correction or bust, as text.
            execRefID @4 :Text; # Execution reference identifying the affected execution.
        }

        # Text-valued order totals carried by a status or restatement report.
        struct Status {
            cumQty @0 :Text; # Reported cumulative executed quantity as text.
            leaves @1 :Text; # Reported remaining order quantity as text.
            avgPx @2 :Text; # Reported average execution price as text.
        }

        # Explanation supplied when an order is rejected.
        struct Rejected {
            reason @0 :Text; # Rejection explanation supplied by the session.
        }

        # Text-valued details for cancellation, expiry, or end-of-day reports.
        struct Canceled {
            leaves @0 :Text; # Reported remaining order quantity as text.
            quantity @1 :Text; # Quantity value reported with this event, as text.
            reason @2 :Text; # Explanation supplied with the event.
        }

        strgOrdID @0: Int64; # Strategy order identifier used to correlate replies.
        accountID @1: Int64; # Account identifier associated with the order.
        securityId @2 : Int64; # Security identifier associated with the order.
        venueID @3: Int64; # Venue identifier associated with the order.
        orderSide @4: Common.Marking; # Reported trading-side and short-sale classification.
        sessOrdID @5: Text; # Session-side order identifier.
        exchExecID @6: Text;  # Execution identifier from SessionExec.execId.
        exchOrdID @7: Text; # Broker order identifier from SessionPlaced.brokerId.
        transactTime @23: Int64; # Broker transaction time
        executingBroker @24: Text; # Broker identified as executing the order.
        # Execution event and its event-specific payload.
        data: union {
            placed @8 :Placed; # Placement report containing the order terms.
            partiallyFilled @9 :Filled; # Partial execution with remaining order quantity.
            filled @10 :Filled; # Completed execution report.
            rejected @11 :Rejected; # Order rejection and its explanation.
            doneForDay @12 :Canceled; # End-of-day order report.
            canceled @13 :Canceled; # Order cancellation report.
            expired @14 :Canceled; # Order expiry report.
            replaced @15 :Placed; # Replacement report containing the updated terms.
            pendingNew @16 :Void; # New-order request is pending.
            pendingCancel @17 :Void; # Cancellation request is pending.
            pendingReplace @18 :Void; # Replacement request is pending.
            correction @19 :Correction; # Correction to a previously reported execution.
            bust @20 :Correction; # Trade-bust report referring to an execution.
            restated @21 :Status; # Restated order totals.
            status @22 :Status; # Order status and totals.
        }
        requestTime @25 :Int64; # Time when associated request is written to the socket
        tag @26:Text; # Application tag associated with the order.
        receiveTime @27 :Int64; # Time when execution is received from the socket
        reportingType @28 :MultiLegReportingType = single; # Single-instrument or multi-leg report scope.
        strgSocketNs @29 :Int64; # Nanoseconds from request placement to socket send.
        omsSocketNs @30 :Int64; # Nanoseconds from OMS receipt to socket send.
        socketStrgNs @31 :Int64; # Nanoseconds from socket receipt to writing the ManagerMessage.
        customTags @32 :List(Common.CustomField); # Additional tag/value metadata supplied with the report.
        accountPosition @33 :List(Position); # Account position entries included with the report.
    }

    # Request to create an order using textual prices and quantities.
    struct Place2 {
        # Text-valued trigger price for a stop order.
        struct Stop {
            stopPx @0 :Text; # Price that triggers the stop instruction, as text.
        }
        # Text-valued trigger and limit prices for a stop-limit order.
        struct StopLimit {
            stopPx @0 :Text; # Price that triggers the stop instruction, as text.
            limitPx @1 :Text; # Limit price for the stop-limit order, as text.
        }
        strgOrdID @0: Int64; # New strategy order ID, retained for replies and later requests.
        accountID @1 : Int64; # Account identifier from reference data.
        securityId @2 : Int64; # Security identifier from reference data.
        venueID @3: Int64; # Venue identifier from reference data.
        orderSide @4 : Side; # Requested buy or sell direction.
        # Select the order's price instruction using textual price values.
        orderType : union {
          market @5 :Void; # Market order without an explicit limit price.
          limit @6 :Text; # Limit price as text; its numeric value must be finite.
          stop @19 :Stop; # Stop instruction with a textual trigger price.
          stopLimit @20 :StopLimit; # Stop-limit instruction with textual trigger and limit prices.
        }
        quantity @7 : Text; # Requested quantity as text; must represent a positive, non-zero finite value.
        # Select whether to constrain the displayed quantity.
        maxFloor :union {
          none @8 :Void; # No maximum displayed quantity supplied.
          maxFloor @9 :Text; # Maximum displayed quantity as text; must represent a positive, non-zero finite value.
        }
        # Select whether to supply a minimum quantity constraint.
        minQty :union {
          none @13 :Void; # No minimum quantity supplied.
          minQty @14 :Text; # Minimum quantity as text; must represent a positive, non-zero finite value.
        }
        timeInForce @10 : Common.TimeInForce; # Requested duration or execution policy.
        # Select direct market access or an algorithm representation.
        algorithm :union {
            dma @11 :Void; # Direct market access without an algorithm payload.
            deprecated1 @12 :Common.CustomAlgo; # Deprecated named-algorithm representation.
            algo @17: Text; # Textual algorithm specification understood by the OMS.
        }
        customTags @16 :List(Common.CustomField); # Additional tag/value fields for this request.
        tag @15:Text; # Application tag associated with the order.
        short @18 :Bool; # Short-sale flag accompanying the requested side.
        groupID @21 : Int64; # Identifier supplied for request-group coordination.
        groupCountdown @22 : Int64; # Countdown metadata associated with the request group.
    }

    # Request to change an existing order using textual price and quantity values.
    struct Replace2 {
        strgOrdID @0: Int64; # Existing strategy order identifier to replace.
        # Select a new price or leave the existing price unchanged.
        price :union {
          unknown @1 :Void; # Preserve the order's current price.
          price @2 :Text; # Replacement price as text; its numeric value must be finite.
        }
        # Select a new quantity or leave the existing quantity unchanged.
        quantity :union {
          unknown @3 :Void; # Preserve the order's current quantity.
          quantity @4 :Text; # Replacement quantity as text; must represent a positive, non-zero finite value.
        }
        groupID @5 : Int64; # Identifier supplied for request-group coordination.
        groupCountdown @6 : Int64; # Countdown metadata associated with the request group.
    }

    # Rejection details shared by cancel and replace requests.
    struct CancelRej {
        strgOrdID @0: Int64; # Strategy order identifier affected by the rejected request.
        reason @1 :Text; # Rejection explanation supplied by the session.
        sessOrdID @2 :Text; # Session-side order identifier.
        transactTime @3: Int64; # Broker transaction time
        requestTime @4 :Int64; # Time when associated request is written to the socket
        tag @5:Text; # Application tag associated with the request.
        receiveTime @6 :Int64; # Time when execution is received from the socket
        customTags @7 :List(Common.CustomField); # Additional tag/value metadata supplied with the rejection.
    }

    # Request failure reported through a control or execution-session message.
    struct Failed {
        # Optional account and security context for the failed request.
        struct OrderInfo {
            accountID @0: Int64; # Account identifier associated with the failed request.
            securityId @1 : Int64; # Security identifier associated with the failed request.
        }
        # Request category associated with the failure.
        enum Type {
            place @0; # Failure concerns a new-order request.
            cancel @1; # Failure concerns a cancellation request.
            replace @2; # Failure concerns a replacement request.
        }
        strgOrdID @0 :Int64; # Strategy order identifier associated with the failure.
        sessOrdID @5 :Text; # Session-side order identifier supplied with the failure.
        type @1: Type; # Kind of request that failed.
        reason @2 : Text; # Explanation of the request failure.
        requestTime @3 :Int64; # Time when associated request is received by the OMS
        tag @4 :Text; # Application tag associated with the request.
        currBid @6 :Float64; # Bid price included with the failure context.
        currAsk @7 :Float64; # Ask price included with the failure context.
        # Select whether to include account and security context.
        info :union {
            none @8 :Void; # No additional order context supplied.
            info @9 :OrderInfo; # Account and security context for the failure.
        }
        mdSeqNum @10: UInt64; # Market-data sequence value included with the failure.
    }

    # Session-side order reference attached to a mismatch report.
    struct MismatchVendor {
        sessOrdID @0: Text; # Session-side order identifier involved in the mismatch.
    }

    # Control probe with an optional order-validation payload.
    struct TestRequest {
        time @0: Int64; # Time value carried by the probe.
        # Select whether to include an order request for validation.
        validate :union {
            none @1 :Void; # No order-validation payload.
            new @2 :Place; # Order request with numeric prices and quantities.
            new2 @3 :Place2; # Order request with textual prices and quantities.
        }
    }

    # Control-probe reply with an optional order-validation result.
    struct TestResponse {
        time @0: Int64; # Time value carried by the probe response.
        # Select the order-validation result, when one is supplied.
        validate :union {
            none @1 :Void; # No order-validation result.
            placeForwarded @2: PlaceForwarded; # Forwarding details supplied with the validation result.
            failed @3: Failed; # Failure details supplied with the validation result.
        }
        mdSeqNum @4: UInt64; # Market-data sequence value included with the response.
    }

    # Execution-session liveness notification.
    struct Heartbeat {
        session @0 :Text; # Execution session identified by the heartbeat.
    }

    # Execution-session logon notification and heartbeat interval.
    struct Logon {
        session @0 :Text; # Execution session identified by the logon.
        interval @1 :Int64; # Heartbeat interval advertised by the session.
    }

    # Execution-session logout notification.
    struct Logout {
        session @0 :Text; # Execution session identified by the logout.
    }

    # Diagnostic describing a message that could not be processed.
    struct BadMessage {
        session @0 :Text; # Session associated with the problematic message.
        message @1 :Text; # Message text included in the diagnostic.
        seqnum @2 :Int64; # Sequence value attached to the problematic message.
    }

    # Acknowledgement that a new-order request was forwarded for execution.
    struct PlaceForwarded {
        # Security reference included with the forwarding acknowledgement.
        struct Securities {
            identifier @0: UInt64; # Security identifier associated with the forwarded request.
            seqNum @1 :UInt64; # Sequence value reported for this security.
        }

        # Account position information included with the acknowledgement.
        struct Position {
            secId @0 :UInt64; # Security represented by this position entry.
            secSeqNum @1 :UInt64; # Sequence value associated with this security.
            qty @2: Float64; # Reported account position quantity.
            usedLocates @3: Float64; # Locate usage reported for this security.
        }

        strgOrdID @0: Int64; # Strategy order identifier for the forwarded request.
        sessOrdID @1 :Text; # Session-side order identifier.
        price @2 :Float64; # Price reported for the forwarded order.
        quantity @3 :Float64; # Quantity reported for the forwarded order.
        market @4 :Bool; # Whether the forwarded order is a market order.
        marking @5: Common.Marking; # Reported trading-side and short-sale classification.
        accountID @6: Int64; # Account identifier for the forwarded order.
        securities @7 :List(Securities); # Security references and their associated sequence values.
        clientRequestTime @8 : Int64; # Time when associated request is received by the OMS
        venueID @9: Int64; # Venue identifier for the forwarded request.
        currBid @10 :Float64; # Bid quote included with the forwarding context.
        currAsk @11 :Float64; # Ask quote included with the forwarding context.
        accountPosition @12 :List(Position); # Account position entries included with the acknowledgement.
        mdSeqNum @13: UInt64; # Market-data sequence value included with the acknowledgement.
    }

    # Acknowledgement that a cancellation request was forwarded.
    struct CancelForwarded {
        strgOrdID @0: Int64; # Strategy order identifier for the forwarded cancellation.
        sessOrdID @1 :Text; # Session-side order identifier.
        clientRequestTime @2 : Int64; # Time when associated request is received by the OMS
        venueID @3: Int64; # Venue identifier for the forwarded cancellation.
    }

    # Acknowledgement that a replacement request was forwarded.
    struct ReplaceForwarded {
        # Account position information included with the acknowledgement.
        struct Position {
            secId @0 :UInt64; # Security represented by this position entry.
            secSeqNum @1 :UInt64; # Sequence value associated with this security.
            qty @2: Float64; # Reported account position quantity.
            usedLocates @3: Float64; # Locate usage reported for this security.
        }

        strgOrdID @0: Int64; # Strategy order identifier for the forwarded replacement.
        sessOrdID @1 :Text; # Session-side order identifier.
        price @2 :Float64; # Price reported for the forwarded replacement.
        quantity @3 :Float64; # Quantity reported for the forwarded replacement.
        short @4 :Bool; # Short-sale flag reported for the replacement.
        clientRequestTime @5 : Int64; # Time when associated request is received by the OMS
        venueID @6: Int64; # Venue identifier for the forwarded replacement.
        currBid @7 :Float64; # Bid quote included with the forwarding context.
        currAsk @8 :Float64; # Ask quote included with the forwarding context.
        accountPosition @9 :List(Position); # Account position entries included with the acknowledgement.
        mdSeqNum @10: UInt64; # Market-data sequence value included with the acknowledgement.
    }

    # Select a control message, an execution-session reply, or a strategy request.
    message :union {
        # OMS control messages, forwarding acknowledgements, and diagnostics.
        ctrl :union {
            mismatchVendor @0 :MismatchVendor; # Mismatch diagnostic carrying a session order reference.
            missingClient @1 :Common.MissingClient; # Missing-client diagnostic.
            missingVendor @2 :Common.MissingVendor; # Missing-vendor diagnostic.
            failed @3 :Failed; # Request failure reported through the control path.
            heartbeat @4 :Void; # Control heartbeat without additional payload.
            testRequest @15 :TestRequest; # Control probe with optional order validation.
            testResponse @16 :TestResponse; # Response to a control probe.
            badMessage @18 :BadMessage; # Diagnostic for a message that could not be processed.
            placeForwarded @22 :PlaceForwarded; # New-order forwarding acknowledgement.
            cancelForwarded @23 :CancelForwarded; # Cancellation forwarding acknowledgement.
            replaceForwarded @24 :ReplaceForwarded; # Replacement forwarding acknowledgement.
            systemCancel @25 :SystemCancel; # System-initiated cancellation for the indicated order.
        }
        # Execution-session responses and availability notifications.
        sess :union {
            failed @5: Failed; # Request failure reported by an execution session.
            exec @6: Exec; # Execution report with numeric prices and quantities.
            cancelRej @7 :CancelRej; # Rejection of a cancellation request.
            replaceRej @8 :CancelRej; # Rejection of a replacement request.
            heartbeat @12 :Heartbeat; # Liveness notification for an execution session.
            logon @13 :Logon; # Execution-session logon and heartbeat interval.
            logout @14 :Logout; # Execution-session logout notification.
            exec2 @19: Exec2; # Execution report with textual prices and quantities.
        }
        # Order requests submitted by the strategy.
        strg :union {
            new @9 :Place; # New-order request with numeric prices and quantities.
            cancel @10 :Cancel; # Cancellation request for an existing order.
            replace @11 :Replace; # Replacement request with numeric price and quantity values.
            new2 @20 :Place2; # New-order request with textual prices and quantities.
            replace2 @21 :Replace2; # Replacement request with textual price and quantity values.
        }
    }
    seqnum @17 :UInt64; # Application sequence number; each output channel has its own sequence.
}
