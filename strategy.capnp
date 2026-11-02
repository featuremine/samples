@0x9c7a71efe87ba0d1;

using Go = import "go.capnp";
$Go.package("fmc");
$Go.import("fm-om/fmc");

using Cxx = import "c++.capnp";
$Cxx.namespace("fmc");

using C = import "c.capnp";
$C.fieldgetset;

using Common = import "common.capnp";

enum MultiLegReportingType {
    single @0;
    individualLeg @1;
    multi @2;
}

struct ManagerMessage {
    enum Side {
        buy @0;
        sell @1;
    }
    struct Exec {

        struct Position {
            secId @0 :UInt64;
            secSeqNum @1 :UInt64;
            qty @2: Float64;
            usedLocates @3: Float64;
        }

        struct Placed {
            orderType : union {
              market @0 :Void;
              limit @1 :Float64;
            }
            orderQuantity @2 : Float64;
        }

        struct Filled {
            lastQuantity @0 :Float64;
            lastPrice @1 :Float64;
            lastFees @2 :Float64;
            liquidityCode @3 :Int64;
            cumQty @4 :Float64;
            leaves @5 :Float64;
            avgPx @6 :Float64;
            lastMkt @7 :Text;
        }

        struct Correction {
            cumQty @0 :Float64;
            leaves @1 :Float64;
            avgPx @2 :Float64;
            lastQuantity @3 :Float64;
            execRefID @4 :Text;
        }

        struct Status {
            cumQty @0 :Float64;
            leaves @1 :Float64;
            avgPx @2 :Float64;
        }

        struct Rejected {
            reason @0 :Text;
        }

        struct Canceled {
            leaves @0 :Float64;
            quantity @1 :Float64;
            reason @2 :Text;
        }

        strgOrdID @0: Int64;
        accountID @1: Int64;
        securityId @2 : Int64;
        venueID @3: Int64;
        orderSide @4: Common.Marking;
        sessOrdID @5: Text;
        exchExecID @6: Text;  # = SessionExec.execId
        exchOrdID @7: Text; # = SessionPlaced.brokerId
        transactTime @23: Int64; # Broker transaction time
        executingBroker @24: Text;
        data: union {
            placed @8 :Placed;
            partiallyFilled @9 :Filled;
            filled @10 :Filled;
            rejected @11 :Rejected;
            doneForDay @12 :Canceled;
            canceled @13 :Canceled;
            expired @14 :Canceled;
            replaced @15 :Placed;
            pendingNew @16 :Void;
            pendingCancel @17 :Void;
            pendingReplace @18 :Void;
            correction @19 :Correction;
            bust @20 :Correction;
            restated @21 :Status;
            status @22 :Status;
        }
        requestTime @25 :Int64; # Time when associated request is written to the socket
        tag @26:Text;
        receiveTime @27 :Int64; # Time when execution is received from the socket
        reportingType @28 :MultiLegReportingType = single;
        strgSocketNs @29 :Int64; # Time from the placement of the request to the moment it is already sent through the socket
        omsSocketNs @30 :Int64; # Time from the moment the OMS receives the request to the moment it is already sent through the socket
        socketStrgNs @31 :Int64; # Time from the moment the response is received through the socket to the moment it is written as a ManagerMessage
        customTags @32 :List(Common.CustomField);
        accountPosition @33 :List(Position);
    }

    struct Place {
        struct Stop {
            stopPx @0 :Float64;
        }
        struct StopLimit {
            stopPx @0 :Float64;
            limitPx @1 :Float64;
        }
        strgOrdID @0: Int64;
        accountID @1 : Int64;
        securityId @2 : Int64;
        venueID @3: Int64;
        orderSide @4 : Side;
        orderType : union {
          market @5 :Void;
          limit @6 :Float64; # Must be finite
          stop @24 :Stop;
          stopLimit @25 :StopLimit;
        }
        quantity @7 : Float64; # Must be positive, non-zero and finite
        maxFloor :union {
          none @8 :Void;
          maxFloor @9 :Float64; # Must be positive, non-zero and finite
        }
        minQty :union {
          none @17 :Void;
          minQty @18 :Float64; # Must be positive, non-zero and finite
        }
        timeInForce @10 : Common.TimeInForce;
        algorithm :union {
            dma @11 :Void;
            deprecated1 @12 :Common.VWAP;
            deprecated2 @13 :Common.POV;
            deprecated3 @14 :Common.TWAP;
            deprecated4 @15 :Common.Ghost;
            deprecated5 @16 :Common.Iceberg;
            deprecated6 @20 :Common.CustomAlgo;
            algo @21: Text;
        }
        customTags @22 :List(Common.CustomField);
        tag @19:Text;
        short @23 :Bool;
        groupID @26 : Int64;
        groupCountdown @27 : Int64;
    }

    struct Cancel {
        strgOrdID @0: Int64;
        groupID @1 : Int64;
        groupCountdown @2 : Int64;
    }

    struct SystemCancel {
        strgOrdID @0: Int64;
    }

    struct Replace {
        strgOrdID @0: Int64;
        price :union {
          unknown @1 :Void;
          price @2 :Float64; # Must be finite
        }
        quantity :union {
          unknown @3 :Void;
          quantity @4 :Float64; # Must be positive, non-zero and finite
        }
        groupID @5 : Int64;
        groupCountdown @6 : Int64;
    }

    struct Exec2 {
        struct Position {
            secId @0 :UInt64;
            secSeqNum @1 :UInt64;
            qty @2: Text;
            usedLocates @3: Text;
        }
        struct Placed {
            orderType : union {
              market @0 :Void;
              limit @1 :Text;
            }
            orderQuantity @2 : Text;
        }

        struct Filled {
            lastQuantity @0 :Text;
            lastPrice @1 :Text;
            lastFees @2 :Text;
            liquidityCode @3 :Int64;
            cumQty @4 :Text;
            leaves @5 :Text;
            avgPx @6 :Text;
            lastMkt @7 :Text;
        }

        struct Correction {
            cumQty @0 :Text;
            leaves @1 :Text;
            avgPx @2 :Text;
            lastQuantity @3 :Text;
            execRefID @4 :Text;
        }

        struct Status {
            cumQty @0 :Text;
            leaves @1 :Text;
            avgPx @2 :Text;
        }

        struct Rejected {
            reason @0 :Text;
        }

        struct Canceled {
            leaves @0 :Text;
            quantity @1 :Text;
            reason @2 :Text;
        }

        strgOrdID @0: Int64;
        accountID @1: Int64;
        securityId @2 : Int64;
        venueID @3: Int64;
        orderSide @4: Common.Marking;
        sessOrdID @5: Text;
        exchExecID @6: Text;  # = SessionExec.execId
        exchOrdID @7: Text; # = SessionPlaced.brokerId
        transactTime @23: Int64; # Broker transaction time
        executingBroker @24: Text;
        data: union {
            placed @8 :Placed;
            partiallyFilled @9 :Filled;
            filled @10 :Filled;
            rejected @11 :Rejected;
            doneForDay @12 :Canceled;
            canceled @13 :Canceled;
            expired @14 :Canceled;
            replaced @15 :Placed;
            pendingNew @16 :Void;
            pendingCancel @17 :Void;
            pendingReplace @18 :Void;
            correction @19 :Correction;
            bust @20 :Correction;
            restated @21 :Status;
            status @22 :Status;
        }
        requestTime @25 :Int64; # Time when associated request is written to the socket
        tag @26:Text;
        receiveTime @27 :Int64; # Time when execution is received from the socket
        reportingType @28 :MultiLegReportingType = single;
        strgSocketNs @29 :Int64; # Time from the placement of the request to the moment it is already sent through the socket
        omsSocketNs @30 :Int64; # Time from the moment the OMS receives the request to the moment it is already sent through the socket
        socketStrgNs @31 :Int64; # Time from the moment the response is received through the socket to the moment it is written as a ManagerMessage
        customTags @32 :List(Common.CustomField);
        accountPosition @33 :List(Position);
    }

    struct Place2 {
        struct Stop {
            stopPx @0 :Text;
        }
        struct StopLimit {
            stopPx @0 :Text;
            limitPx @1 :Text;
        }
        strgOrdID @0: Int64;
        accountID @1 : Int64;
        securityId @2 : Int64;
        venueID @3: Int64;
        orderSide @4 : Side;
        orderType : union {
          market @5 :Void;
          limit @6 :Text; # Must be finite
          stop @19 :Stop;
          stopLimit @20 :StopLimit;
        }
        quantity @7 : Text; # Must be positive, non-zero and finite
        maxFloor :union {
          none @8 :Void;
          maxFloor @9 :Text; # Must be positive, non-zero and finite
        }
        minQty :union {
          none @13 :Void;
          minQty @14 :Text; # Must be positive, non-zero and finite
        }
        timeInForce @10 : Common.TimeInForce;
        algorithm :union {
            dma @11 :Void;
            deprecated1 @12 :Common.CustomAlgo;
            algo @17: Text;
        }
        customTags @16 :List(Common.CustomField);
        tag @15:Text;
        short @18 :Bool;
        groupID @21 : Int64;
        groupCountdown @22 : Int64;
    }

    struct Replace2 {
        strgOrdID @0: Int64;
        price :union {
          unknown @1 :Void;
          price @2 :Text; # Must be finite
        }
        quantity :union {
          unknown @3 :Void;
          quantity @4 :Text; # Must be positive, non-zero and finite
        }
        groupID @5 : Int64;
        groupCountdown @6 : Int64;
    }

    struct CancelRej {
        strgOrdID @0: Int64;
        reason @1 :Text;
        sessOrdID @2 :Text;
        transactTime @3: Int64; # Broker transaction time
        requestTime @4 :Int64; # Time when associated request is written to the socket
        tag @5:Text;
        receiveTime @6 :Int64; # Time when execution is received from the socket
        customTags @7 :List(Common.CustomField);
    }

    struct Failed {
        struct OrderInfo {
            accountID @0: Int64;
            securityId @1 : Int64;
        }
        enum Type {
            place @0;
            cancel @1;
            replace @2;
        }
        strgOrdID @0 :Int64;
        sessOrdID @5 :Text;
        type @1: Type;
        reason @2 : Text;
        requestTime @3 :Int64; # Time when associated request is received by the OMS
        tag @4 :Text;
        currBid @6 :Float64;
        currAsk @7 :Float64;
        info :union {
            none @8 :Void;
            info @9 :OrderInfo;
        }
        mdSeqNum @10: UInt64;
    }

    struct MismatchVendor {
        sessOrdID @0: Text;
    }

    struct TestRequest {
        time @0: Int64;
        validate :union {
            none @1 :Void;
            new @2 :Place;
            new2 @3 :Place2;
        }
    }

    struct TestResponse {
        time @0: Int64;
        validate :union {
            none @1 :Void;
            placeForwarded @2: PlaceForwarded;
            failed @3: Failed;
        }
        mdSeqNum @4: UInt64;
    }

    struct Heartbeat {
        session @0 :Text;
    }

    struct Logon {
        session @0 :Text;
        interval @1 :Int64;
    }

    struct Logout {
        session @0 :Text;
    }

    struct BadMessage {
        session @0 :Text;
        message @1 :Text;
        seqnum @2 :Int64;
    }

    struct PlaceForwarded {
        struct Securities {
            identifier @0: UInt64;
            seqNum @1 :UInt64;
        }

        struct Position {
            secId @0 :UInt64;
            secSeqNum @1 :UInt64;
            qty @2: Float64;
            usedLocates @3: Float64;
        }

        strgOrdID @0: Int64;
        sessOrdID @1 :Text;
        price @2 :Float64;
        quantity @3 :Float64;
        market @4 :Bool;
        marking @5: Common.Marking;
        accountID @6: Int64;
        securities @7 :List(Securities);
        clientRequestTime @8 : Int64; # Time when associated request is received by the OMS
        venueID @9: Int64;
        currBid @10 :Float64;
        currAsk @11 :Float64;
        accountPosition @12 :List(Position);
        mdSeqNum @13: UInt64;
    }

    struct CancelForwarded {
        strgOrdID @0: Int64;
        sessOrdID @1 :Text;
        clientRequestTime @2 : Int64; # Time when associated request is received by the OMS
        venueID @3: Int64;
    }

    struct ReplaceForwarded {
        struct Position {
            secId @0 :UInt64;
            secSeqNum @1 :UInt64;
            qty @2: Float64;
            usedLocates @3: Float64;
        }

        strgOrdID @0: Int64;
        sessOrdID @1 :Text;
        price @2 :Float64;
        quantity @3 :Float64;
        short @4 :Bool;
        clientRequestTime @5 : Int64; # Time when associated request is received by the OMS
        venueID @6: Int64;
        currBid @7 :Float64;
        currAsk @8 :Float64;
        accountPosition @9 :List(Position);
        mdSeqNum @10: UInt64;
    }

    message :union {
        ctrl :union {
            mismatchVendor @0 :MismatchVendor;
            missingClient @1 :Common.MissingClient;
            missingVendor @2 :Common.MissingVendor;
            failed @3 :Failed;
            heartbeat @4 :Void;
            testRequest @15 :TestRequest;
            testResponse @16 :TestResponse;
            badMessage @18 :BadMessage;
            placeForwarded @22 :PlaceForwarded;
            cancelForwarded @23 :CancelForwarded;
            replaceForwarded @24 :ReplaceForwarded;
            systemCancel @25 :SystemCancel;
        }
        sess :union {
            failed @5: Failed;
            exec @6: Exec;
            cancelRej @7 :CancelRej;
            replaceRej @8 :CancelRej;
            heartbeat @12 :Heartbeat;
            logon @13 :Logon;
            logout @14 :Logout;
            exec2 @19: Exec2;
        }
        strg :union {
            new @9 :Place;
            cancel @10 :Cancel;
            replace @11 :Replace;
            new2 @20 :Place2;
            replace2 @21 :Replace2;
        }
    }
    seqnum @17 :UInt64;
}
