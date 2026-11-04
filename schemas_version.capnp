@0xbf5147fba4b2e123;

using Go = import "go.capnp";
$Go.package("fmc");
$Go.import("fm-om/fmc");

using Cxx = import "c++.capnp";
$Cxx.namespace("fmc");

using C = import "c.capnp";
$C.fieldgetset;

const schemasVersionMajor :UInt16 = 1;
const schemasVersionMinor :UInt16 = 0;
const schemasVersionPatch :UInt16 = 11;

const schemasVersion :Text = "1.0.11";
