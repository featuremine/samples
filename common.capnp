@0xdb1a5666ec41faea;

using Go = import "go.capnp";
$Go.package("fmc");
$Go.import("fm-om/fmc");

using Cxx = import "c++.capnp";
$Cxx.namespace("fmc");

using C = import "c.capnp";
$C.fieldgetset;

enum TimeInForce {
    none @0;
    day @1;
    gtc @2;
    opg @3;
    ioc @4;
    fok @5;
    gtx @6;
    gtd @7;
    atc @8;
}

enum Marking {
    buy @0;
    sell @1;
    sellShort @2;
    unknown @3;
}

struct SecurityID {
  idSource @0 :Text;
  securityID @1 :Text;
}

struct CustomField {
  tag @0 :UInt64;
  value @1 :Text;
}

struct VWAP {
  start @0 :Text;
  end @1 :Text;
  participationRate @2 :Int64;
  customArgs @3 :List(CustomField);
}

struct POV {
  start @0 :Text;
  end @1 :Text;
  participationRate @2 :Int64;
  customArgs @3 :List(CustomField);
}

struct TWAP {
  start @0 :Text;
  end @1 :Text;
  customArgs @2 :List(CustomField);
}

struct Ghost {
  customArgs @0 :List(CustomField);
}

struct Iceberg {
  customArgs @0 :List(CustomField);
}

struct CustomAlgo {
  algoName @0 :Text;
  customArgs @1 :List(CustomField);
}

struct FailedClient {
    count @0 :Int64;
}

struct MissingClient {
    count @0 :Int64;
}

struct MissingVendor {
    count @0 :Int64;
}
