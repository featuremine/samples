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

@0xdb1a5666ec41faea;

using Go = import "go.capnp";
$Go.package("fmc");
$Go.import("fm-om/fmc");

using Cxx = import "c++.capnp";
$Cxx.namespace("fmc");

using C = import "c.capnp";
$C.fieldgetset;

# Instructions for how long an order remains eligible for execution.
enum TimeInForce {
    none @0;  # No time-in-force instruction specified.
    day @1;  # Valid for the trading day.
    gtc @2;  # Good until canceled.
    opg @3;  # Eligible for the opening.
    ioc @4;  # Immediate or cancel.
    fok @5;  # Fill or kill.
    gtx @6;  # Good until crossing.
    gtd @7;  # Good until the specified date.
    atc @8;  # Eligible at the close.
}

# Order side and short-sale marking.
enum Marking {
    buy @0;  # Buy-side order.
    sell @1;  # Sell-side order.
    sellShort @2;  # Sell order marked short.
    unknown @3;  # Side or marking not specified.
}

# A security identifier together with its identifying scheme.
struct SecurityID {
  idSource @0 :Text;  # Identifier scheme or source.
  securityID @1 :Text;  # Value in the selected identifier scheme.
}

# An additional tagged text value.
struct CustomField {
  tag @0 :UInt64;  # Custom field identifier.
  value @1 :Text;  # Text value for the custom field.
}

# Parameters for volume-weighted average price execution.
struct VWAP {
  start @0 :Text;  # Configured execution-window start.
  end @1 :Text;  # Configured execution-window end.
  participationRate @2 :Int64;  # Algorithm participation-rate setting.
  customArgs @3 :List(CustomField);  # Additional algorithm parameters.
}

# Parameters for percentage-of-volume execution.
struct POV {
  start @0 :Text;  # Configured execution-window start.
  end @1 :Text;  # Configured execution-window end.
  participationRate @2 :Int64;  # Algorithm participation-rate setting.
  customArgs @3 :List(CustomField);  # Additional algorithm parameters.
}

# Parameters for time-weighted average price execution.
struct TWAP {
  start @0 :Text;  # Configured execution-window start.
  end @1 :Text;  # Configured execution-window end.
  customArgs @2 :List(CustomField);  # Additional algorithm parameters.
}

# Custom parameters for the Ghost algorithm.
struct Ghost {
  customArgs @0 :List(CustomField);  # Additional algorithm parameters.
}

# Custom parameters for the Iceberg algorithm.
struct Iceberg {
  customArgs @0 :List(CustomField);  # Additional algorithm parameters.
}

# A named algorithm with its custom parameters.
struct CustomAlgo {
  algoName @0 :Text;  # Name of the requested algorithm.
  customArgs @1 :List(CustomField);  # Additional algorithm parameters.
}

# Diagnostic information associated with a failed client.
struct FailedClient {
    count @0 :Int64;  # Diagnostic counter value.
}

# Diagnostic information associated with a missing client.
struct MissingClient {
    count @0 :Int64;  # Diagnostic counter value.
}

# Diagnostic information associated with a missing vendor.
struct MissingVendor {
    count @0 :Int64;  # Diagnostic counter value.
}
