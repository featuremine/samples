# Copyright (c) 2026 Featuremine. All rights reserved.
#
# Featuremine Proprietary - Restricted Use.
#
# This file is not covered by the repository's MIT License.
# Use, copying, and modification are permitted only for use with local
# Featuremine Titan or Featuremine-owned hosted services. Retain this
# license and all original notices. Sharing and redistribution require
# prior written authorization from Featuremine.
#
# See LICENSE-RESTRICTED for the complete license terms.

@0xa809140cd603445a;

using Go = import "go.capnp";
$Go.package("fmc");
$Go.import("fm-om/fmc");

using Cxx = import "c++.capnp";
$Cxx.namespace("fmc");

using C = import "c.capnp";
$C.fieldgetset;

const clientProtocolVersion :Int64 = 1;  # Client protocol version constant.
const serverProtocolVersion :Int64 = 1;  # Server protocol version constant.

# Venue definitions and routing attributes.
struct Venue
{
    identifier            @0: UInt16;    # Venue identifier.
    code                  @1: Text;      # Broker or venue code.
    exdest                @2: Text;      # Execution destination value.
    swapIndicator         @3: Bool;      # Swap-related indicator.
    locatesBrokerID       @4: Text;      # Broker identifier for locates.
}


# Venue-specific identifiers and attributes for a security.
struct VenueSecurityAttribute
{
    venueID       @0: UInt16;  # Venue identifier.
    securityId    @1: UInt64;    # Security identifier.
    scalingFactor @2: Float64;  # Venue-specific scaling factor.
    symbol        @3: Text;  # Venue-specific trading symbol.
    symbolSfx     @4: Text;  # Venue-specific symbol suffix.
    cfiCode       @5: Text;  # Instrument classification code.
    idSource      @6: Text;  # Identifier scheme or source.
    securityID    @7: Text;  # Value in the selected identifier scheme.
    securityExch  @8: Text;  # Security exchange code.
}

# Account identity, ownership, and aggregation units.
struct Account
{
    identifier      @0: UInt64; # Account identifier.
    aggUnit         @1: UInt32; # Account-level aggregation unit.
    managerAggUnit  @2: UInt32; # Manager aggregation unit.
    client          @3: Text; # Client identity that owns this account.
}

# Maps an account to its venue account and request tags.
struct VenueAccountMapping
{
    # A tagged text value attached to a venue request.
    struct CustomField {
      tag @0 :UInt64;  # Custom field identifier.
      value @1 :Text;  # Text value for the custom field.
    }
    identifier     @0: UInt64;  # Account identifier.
    venueID        @1: UInt16;  # Venue identifier.
    venueAccount   @2: Text;    # Broker account value; maximum 48 characters.
    placeTags      @3: List(CustomField);  # Custom tags for placement requests.
    cancelTags     @4: List(CustomField);  # Custom tags for cancellation requests.
}

# Associates an account with a locate pool.
struct LocatePool
{
    identifier     @0: UInt64;  # Account identifier.
    locatePool     @1: UInt64;  # Locate pool identifier.
}

# Locate information for a security and locate pool.
struct Locates
{
    securityID     @0: UInt64;  # Security identifier.
    locatePool     @1: UInt64;  # Locate pool identifier.
    locate         @2: UInt32;  # Locate value for this security and pool.
    locateProvider @3: Text;  # Provider associated with the locate.
}

# The instrument category of a security.
enum InstrumentType
{
    equity @0;  # Equity instrument.
    future @1;  # Futures instrument.
    fx    @2;  # Foreign-exchange instrument.
    currency @3;  # Currency instrument.
    cryptoPair @4;  # Cryptocurrency pair.
}

# The type of foreign-exchange instrument.
enum FxType
{
    fxSpot  @0;  # Spot foreign exchange.
    fxNdf   @1;  # Non-deliverable forward foreign exchange.
}

# The expiration year and month of a future.
struct FutureExpiration
{
    year    @0: UInt16;  # Expiration year.
    month    @1: UInt8;  # Expiration month.
}

# Identifies a spread leg and its ratio.
struct FutureSpreadLeg
{
    identifier    @0: UInt64;    # Security identifier for the leg.
    ratio         @1: Float64;   # Ratio of this leg in the spread.
}

# Security identifiers, currency references, and asset-class details.
struct SecurityDefinition
{
    # Quantity currency and instrument type for an FX pair.
    struct CurrencyPair
    {
        quantityCurrency @0: UInt64;    # Currency identifier in which quantity is expressed.
        fxType           @1: FxType;  # Foreign-exchange instrument type.
    }

    # Equity-specific security identifiers.
    struct Equity
    {
        isin           @0: Text;  # ISIN security identifier.
        sedol          @1: Text;  # SEDOL security identifier.
    }

    # Contract and expiration details for a future.
    struct Future $Go.name("Fut")
    {
        # The component legs of a futures spread.
        struct Spread
        {
            legs    @0: List(FutureSpreadLeg);  # Component legs and their ratios.
        }

        multiplier    @0: Float64;  # Contract multiplier value.
        product       @1: Text;  # Exchange root symbol.
        expiration    @2: FutureExpiration;  # Contract expiration year and month.
        # Selects an outright future or a spread.
        futureType : union $Go.name("Kind") {
            outright @3 : Void;  # Outright future without spread-leg details.
            spread @4 : Spread;  # Spread-leg details.
        }
    }

    # Marks a security as a currency.
    struct Currency
    {
    }

    # Quantity currency for a cryptocurrency pair.
    struct CryptoPair
    {
        quantityCurrency @0: UInt64;    # Currency identifier in which quantity is expressed.
    }

    identifier        @0: UInt64;            # Security identifier.
    symbol            @1: Text;              # Security symbol; maximum 32 characters.
    ric               @2: Text;              # RIC identifier; maximum 16 characters.
    bloombergId       @3: Text;              # Bloomberg identifier; maximum 16 characters.
    instrumentType    @4: InstrumentType;  # Instrument category.
    quoteCurrency     @5: UInt64;            # Currency identifier for the quoted price.

    # Selects the security's asset-class-specific attributes.
    assetClass : union
    {
        future   @6: Future $Go.name("FutClass");  # Futures attributes.
        equity   @7: Equity;  # Equity attributes.
        fx       @8: CurrencyPair;  # Foreign-exchange pair attributes.
        currency @9: Currency;  # Currency marker.
        cryptoPair @12: CryptoPair;  # Cryptocurrency-pair attributes.
    }

    # Notional bond terms for a yield-quoted instrument.
    struct YieldQuotedBond
    {
        notionalIssueCoupon      @0 : Int64;  # Notional issue coupon value.
        couponFrequency          @1 : Int64;  # Coupon-frequency value.
        notionalMaturityDateYear @2 : UInt16;  # Notional maturity year.
        daysPerYear              @3 : UInt16;  # Day-count year length.
    }

    # Selects optional notional valuation details.
    notionalType : union
    {
        none                     @10 : Void;  # No notional valuation details.
        yieldQuotedBond          @11 : YieldQuotedBond;  # Yield-quoted bond details.
    }

    compositeFigi     @13: Text;             # Composite FIGI identifier; maximum 16 characters.
}

# Identifies a reference-rate security and its currency pair.
struct ReferenceFxRateSecurity
{
    referenceId      @0: UInt64;    # Identifier for the reference-rate security.
    baseId           @1: UInt64;    # Currency identifier for the base currency.
    destinationId    @2: UInt64;    # Currency identifier for the destination currency.
                                     # e.g. In EURUSD reference rate:
                                     #    (*)  _baseId refers to the currency ID for EUR
                                     #    (*) _destinationId is the current ID for USD
}

# Associates a currency pair with its reference-rate channel.
struct ReferenceFxRateChannel
{
    baseId           @0: UInt64;    # Currency identifier for the base currency.
    destinationId    @1: UInt64;    # Currency identifier for the destination currency.
                                     # e.g. In EURUSD reference rate:
                                     #    (*)  _baseId refers to the currency ID for EUR
                                     #    (*) _destinationId is the current ID for USD
    channelName      @2: Text;      # Channel carrying the reference-rate data.
}

# Associates a security identifier with its data channel.
struct RiskChannel
{
    referenceId      @0: UInt64;    # Security identifier.
    channelName      @1: Text;      # Channel associated with the security.
}

# Associates a security and venue with their data channel.
struct RiskVenueChannel
{
    securityId      @0: UInt64;    # Security identifier.
    venueId         @1: UInt64;    # Venue identifier.
    channelName     @2: Text;      # Channel associated with the security and venue.
}

# A currency identifier and its name or code.
struct Currency
{
    identifier    @0: UInt64;  # Currency identifier.
    currency      @1: Text; # Currency name or code, such as USD or JPY.
}

# The trading stage to which a risk limit applies.
enum RiskType
{
    postTrade            @0;  # Post-trade risk.
    preTrade             @1;  # Pre-trade risk.
    preAndPostTrade      @2;  # Pre-trade and post-trade risk.
}

# Defines a limit identifier, type, and description.
struct LimitMaster
{
    limitId        @0: UInt64;  # Limit identifier.
    limitType      @1: Text;     # Limit type code, such as GMV, NMV, or SOQ.
    description    @2: Text;  # Description of the limit.
}

# A risk limit with currency, scope, and type-specific parameters.
struct RiskLimit
{
    riskCurrencyId           @0: UInt64;  # Currency identifier for the limit.
    limitId                  @1: UInt64;  # Identifier from the limit definitions.
    riskType                 @2: RiskType;  # Trading stage to which the limit applies.
    limitValue               @3: Float64;  # Configured limit value.
    limitParameters          @4: List(Float64);  # Additional parameters for the selected limit type.

    # Selects the account, aggregation unit, or portfolio scope.
    riskAggLevelId : union
    {
        accountId   @5 : UInt64;  # Account identifier for the limit scope.
        aggunitId   @6 : UInt64;  # Aggregation-unit identifier for the limit scope.
        portfolioId @7 : UInt64;  # Portfolio identifier for the limit scope.
    }
    # Selects the security-level scope for aggregation.
    symbolAggregation : union {
        contract   @8 : UInt64;  # Contract identifier for symbol aggregation.
        product   @9 : Text;  # Product value for symbol aggregation.
        none @10 : Void;  # No symbol-level aggregation selection.
    }
}

# A marking limit with its scope and type-specific parameters.
struct MarkingLimit
{
    limitId                  @0: UInt64;  # Identifier from the limit definitions.
    limitValue               @1: Float64;  # Configured limit value.
    limitParameters          @2: List(Float64);  # Additional parameters for the selected limit type.

    # Selects the account, aggregation unit, or portfolio scope.
    markingAggLevelId : union
    {
        accountId   @3 : UInt64;  # Account identifier for the limit scope.
        aggunitId   @4 : UInt64;  # Aggregation-unit identifier for the limit scope.
        portfolioId @5 : UInt64;  # Portfolio identifier for the limit scope.
    }
    # Selects the security-level scope for aggregation.
    symbolAggregation : union
    {
        contract   @6 : UInt64;  # Contract identifier for symbol aggregation.
        product   @7 : Text;  # Product value for symbol aggregation.
        none @8 : Void;  # No symbol-level aggregation selection.
    }
}

# Account position and close price, published on the position channel.
struct Position
{
    securityId               @0: UInt64;    # Security identifier.
    accountId                @1: UInt64;    # Account identifier.
    quantity                 @2: Int64;     # Account position.
    closePrice               @3: Float64;   # Security close price.
}

# Account position and close price represented as text.
struct Position2
{
    securityId               @0: UInt64;    # Security identifier.
    accountId                @1: UInt64;    # Account identifier.
    quantity                 @2: Text;      # Account position as text.
    closePrice               @3: Text;      # Security close price as text.
}

# A security's close price and instrument type.
struct ClosePrice
{
    securityId               @0: UInt64;            # Security identifier.
    closePrice               @1: Float64;           # Security close price.
    instrumentType           @2: InstrumentType;    # Instrument category.
}

# A security's bid, ask, last price, and update timestamp.
struct MarketDataUpdate
{
    instrumentType    @0: InstrumentType;  # Instrument category.
    securityId        @1: UInt64;  # Security identifier.
    bid               @2: Float64;  # Bid price.
    ask               @3: Float64;  # Ask price.
    lastPrice         @4: Float64;  # Last price.
    timestamp         @5: Int64;  # Timestamp associated with this update.
}

# Trading restriction flags for an account and security.
struct TradingRestriction
{
    account           @0: UInt64;  # Account identifier.
    securityId        @1: UInt64;  # Security identifier.
    instrumentType    @2: InstrumentType;  # Instrument category.
    longRestriction   @3: Bool;  # Whether a long-side restriction is set.
    shortRestriction  @4: Bool;  # Whether a short-side restriction is set.
    tradeRestriction  @5: Bool;  # Whether a trading restriction is set.
}

# Envelope for security, currency, and channel reference messages.
struct Symbology
{
    # Selects the symbology message payload.
    message : union
    {
        securityDefinition      @0: SecurityDefinition;  # Security-definition record.
        currency                @1: Currency;  # Currency record.
        referenceFxRateSecurity @2: ReferenceFxRateSecurity;  # Reference-rate security definition.
        referenceFxRateChannel  @3: ReferenceFxRateChannel;  # Reference-rate channel mapping.
        riskChannel             @4: RiskChannel;  # Security-to-channel mapping.
        riskVenueChannel        @5: RiskVenueChannel;  # Security-and-venue channel mapping.
    }
}

# Envelope for venue definitions and account or security mappings.
struct VenueData {
    # Selects the venue-data payload.
    message : union {
        venue                  @0: Venue;  # Venue definition.
        venueSecurityAttribute @1: VenueSecurityAttribute;  # Venue-specific security attributes.
        venueAccountMapping    @2: VenueAccountMapping;  # Account-to-venue mapping.
    }
}

# Envelope for account, locate, limit, restriction, or position data.
struct RiskData
{
    # Selects the risk-data payload.
    message : union
    {
        account            @0: Account;  # Account definition.
        locatePool         @1: LocatePool;  # Account-to-locate-pool mapping.
        locates            @2: Locates;  # Security locate information.
        limitMaster        @3: LimitMaster;  # Limit definition.
        riskLimit          @4: RiskLimit;  # Risk-limit configuration.
        tradingRestriction @5: TradingRestriction;  # Account and security restriction flags.
        position           @6: Position;  # Numeric account position.
        position2          @7: Position2;  # Account position represented as text.
        markingLimit       @8: MarkingLimit;  # Marking-limit configuration.
    }
}

# Envelope for close prices and market-data updates.
struct MarketData
{
    # Selects the market-data payload.
    message : union
    {
        closePrice       @0: ClosePrice;  # Security close-price record.
        marketDataUpdate @1: MarketDataUpdate;  # Bid, ask, and last-price update.
    }
}

