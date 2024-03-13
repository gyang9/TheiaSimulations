#ifndef __THEIA_Theia__
#define __THEIA_Theia__

#include <Config.hh>
#include <RAT/Rat.hh>
#include <RAT/AnyParse.hh>
#include <RAT/ProcBlockManager.hh>
#include <RAT/ProcAllocator.hh>
#include <RAT/GLG4Gen.hh>
#include <RAT/Factory.hh>
#include <GeoTheiaFactory.hh>
//#include <DichroiconArrayFactory.hh>
#include <HitmanProc.hh>
#include <NtupleProc.hh>
#include <LaserballGenerator.hh>
#include <string>

namespace THEIA {

class Theia : public RAT::Rat {
 public:
  Theia(RAT::AnyParse* parser, int argc, char** argv);
};

}  // namespace THEIA

#endif
