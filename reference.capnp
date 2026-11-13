@0xa809140cd603445a;

using Go = import "go.capnp";
$Go.package("fmc");
$Go.import("fm-om/fmc");

using Cxx = import "c++.capnp";
$Cxx.namespace("fmc");

using C = import "c.capnp";
$C.fieldgetset;

const clientProtocolVersion :Int64 = 1;
const serverProtocolVersion :Int64 = 1;

# Venue definitions and mappings.
struct Venue
{
    identifier            @0: UInt16;    # Venue identifier
    code                  @1: Text;      # Broker code
    exdest                @2: Text;      # Exdest
    swapIndicator         @3: Bool;      # Swap indicator
    locatesBrokerID       @4: Text;      # Locates broker identifier
}


# Attributes for a security at a venue.
struct VenueSecurityAttribute
{
    venueID       @0: UInt16;
    securityId    @1: UInt64;    # Security identifier
    scalingFactor @2: Float64;
    symbol        @3: Text;
    symbolSfx     @4: Text;
    cfiCode       @5: Text;
    idSource      @6: Text;
    securityID    @7: Text;
    securityExch  @8: Text;
}

# Accounts and their venue mappings.
struct Account
{
    identifier      @0: UInt64; # Account ID
    aggUnit         @1: UInt32; # For aggregation at the account level
    managerAggUnit  @2: UInt32; # Manager aggregation unit
    client          @3: Text; # Client identity that owns this account
}

struct VenueAccountMapping
{
    struct CustomField {
      tag @0 :UInt64;
      value @1 :Text;
    }
    identifier     @0: UInt64;  # Account ID
    venueID        @1: UInt16;  # Venue identifier
    venueAccount   @2: Text;    # Broker account - max 48 characters
    placeTags      @3: List(CustomField);
    cancelTags     @4: List(CustomField);
}

struct LocatePool
{
    identifier     @0: UInt64;  # Account ID
    locatePool     @1: UInt64;  # Locate pool ID
}

struct Locates
{
    securityID     @0: UInt64;
    locatePool     @1: UInt64;
    locate         @2: UInt32;
    locateProvider @3: Text;
}

# Security definitions.
enum InstrumentType
{
    equity @0;
    future @1;
    fx    @2;
    currency @3;
    cryptoPair @4;
}

enum LegSide
{
    buy     @0;
    sell    @1;
}

enum FxType
{
    fxSpot  @0;
    fxNdf   @1;
}

struct FutureExpiration
{
    year    @0: UInt16;
    month    @1: UInt8;
}

struct FutureSpreadLeg
{
    identifier    @0: UInt64;    # Security identifier
    ratio         @1: Float64;   # Ratio of this leg in a spread
}

# Published on the symbology channel.
struct SecurityDefinition
{
    struct CurrencyPair
    {
        quantityCurrency @0: UInt64;    # currency identifier for the destination currency
        fxType           @1: FxType;
    }

    struct Equity
    {
        isin           @0: Text;
        sedol          @1: Text;
    }

    struct Future $Go.name("Fut")
    {
        struct Spread
        {
            legs    @0: List(FutureSpreadLeg);
        }

        multiplier    @0: Float64;
        # Exchange root symbol.
        product       @1: Text;
        expiration    @2: FutureExpiration;
        futureType : union $Go.name("Kind") {
            outright @3 : Void;
            spread @4 : Spread;
        }
    }

    struct Currency
    {
    }

    struct CryptoPair
    {
        quantityCurrency @0: UInt64;    # currency identifier for the destination currency
    }

    identifier        @0: UInt64;            # Security identifier
    symbol            @1: Text;              # Maximum 32 characters
    ric               @2: Text;              # Reuters identifier code - Max 16 characters
    bloombergId       @3: Text;              # Bloomberg ID - Max 16 characters
    instrumentType    @4: InstrumentType;
    quoteCurrency     @5: UInt64;            # Identifier from Currency definition

    assetClass : union
    {
        future   @6: Future $Go.name("FutClass");
        equity   @7: Equity;
        fx       @8: CurrencyPair;
        currency @9: Currency;
        cryptoPair @12: CryptoPair;
    }

    struct YieldQuotedBond
    {
        notionalIssueCoupon      @0 : Int64;
        couponFrequency          @1 : Int64;
        notionalMaturityDateYear @2 : UInt16;
        daysPerYear              @3 : UInt16;
    }

    notionalType : union
    {
        none                     @10 : Void;
        yieldQuotedBond          @11 : YieldQuotedBond;
    }

    compositeFigi     @13: Text;             # Composite Bloomberg ID - Max 16 characters
}

struct ReferenceFxRateSecurity
{
    referenceId      @0: UInt64;    # Identifier for this reference rate security
    baseId           @1: UInt64;    # Currency identifier for the base currency
    destinationId    @2: UInt64;    # currency identifier for the destination currency
                                     # e.g. In EURUSD reference rate:
                                     #    (*)  _baseId refers to the currency ID for EUR
                                     #    (*) _destinationId is the current ID for USD
}

struct ReferenceFxRateChannel
{
    baseId           @0: UInt64;    # Currency identifier for the base currency
    destinationId    @1: UInt64;    # currency identifier for the destination currency
                                     # e.g. In EURUSD reference rate:
                                     #    (*)  _baseId refers to the currency ID for EUR
                                     #    (*) _destinationId is the current ID for USD
    channelName      @2: Text;      # Channel Name
}

struct RiskChannel
{
    referenceId      @0: UInt64;    # Identifier of the security
    channelName      @1: Text;      # Channel Name
}

struct RiskVenueChannel
{
    securityId      @0: UInt64;    # Identifier of the security
    venueId         @1: UInt64;    # Identifier of the venue
    channelName     @2: Text;      # Channel Name
}

struct Currency
{
    identifier    @0: UInt64;
    currency      @1: Text; # e.g. EURO, USD, JPY, AUD, etc.
}

# Risk information.
enum RiskType
{
    postTrade            @0;
    preTrade             @1;
    preAndPostTrade      @2;
}

struct LimitMaster
{
    limitId        @0: UInt64;
    limitType      @1: Text;     # GMV, NMV, SOQ, etc
    description    @2: Text;
}

struct RiskLimit
{
    riskCurrencyId           @0: UInt64;  # Identifier from Currency definition
    limitId                  @1: UInt64;
    riskType                 @2: RiskType;
    limitValue               @3: Float64;
    limitParameters          @4: List(Float64);

    riskAggLevelId : union
    {
        accountId   @5 : UInt64;
        aggunitId   @6 : UInt64;
        portfolioId @7 : UInt64;
    }
    symbolAggregation : union {
        contract   @8 : UInt64;
        product   @9 : Text;
        none @10 : Void;
    }
}

struct MarkingLimit
{
    limitId                  @0: UInt64;
    limitValue               @1: Float64;
    limitParameters          @2: List(Float64);

    markingAggLevelId : union
    {
        accountId   @3 : UInt64;
        aggunitId   @4 : UInt64;
        portfolioId @5 : UInt64;
    }
    symbolAggregation : union
    {
        contract   @6 : UInt64;
        product   @7 : Text;
        none @8 : Void;
    }
}

# Published on the position channel.
struct Position
{
    securityId               @0: UInt64;    # Security identifier
    accountId                @1: UInt64;    # Account identifier
    quantity                 @2: Int64;     # Account position
    closePrice               @3: Float64;   # Security close price
}

struct Position2
{
    securityId               @0: UInt64;    # Security identifier
    accountId                @1: UInt64;    # Account identifier
    quantity                 @2: Text;      # Account position
    closePrice               @3: Text;      # Security close price
}

struct ClosePrice
{
    securityId               @0: UInt64;            # Security identifier
    closePrice               @1: Float64;           # Security close price
    instrumentType           @2: InstrumentType;    # Instrument type
}

struct MarketDataUpdate
{
    instrumentType    @0: InstrumentType;
    securityId        @1: UInt64;
    bid               @2: Float64;
    ask               @3: Float64;
    lastPrice         @4: Float64;
    timestamp         @5: Int64;
}

struct TradingRestriction
{
    account           @0: UInt64;
    securityId        @1: UInt64;
    instrumentType    @2: InstrumentType;
    longRestriction   @3: Bool;
    shortRestriction  @4: Bool;
    tradeRestriction  @5: Bool;
}

# Messages for the symbology channel
struct Symbology
{
    message : union
    {
        securityDefinition      @0: SecurityDefinition;
        currency                @1: Currency;
        referenceFxRateSecurity @2: ReferenceFxRateSecurity;
        referenceFxRateChannel  @3: ReferenceFxRateChannel;
        riskChannel             @4: RiskChannel;
        riskVenueChannel        @5: RiskVenueChannel;
    }
}

struct VenueData {
    message : union {
        venue                  @0: Venue;
        venueSecurityAttribute @1: VenueSecurityAttribute;
        venueAccountMapping    @2: VenueAccountMapping;
    }
}

# Messages for the risk channel
struct RiskData
{
    message : union
    {
        account            @0: Account;
        locatePool         @1: LocatePool;
        locates            @2: Locates;
        limitMaster        @3: LimitMaster;
        riskLimit          @4: RiskLimit;
        tradingRestriction @5: TradingRestriction;
        position           @6: Position;
        position2          @7: Position2;
        markingLimit       @8: MarkingLimit;
    }
}

# Messages for the marketdata channel
struct MarketData
{
    message : union
    {
        closePrice       @0: ClosePrice;
        marketDataUpdate @1: MarketDataUpdate;
    }
}

