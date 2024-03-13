#ifndef __RAT_GeoTheiaFactory__
#define __RAT_GeoTheiaFactory__

#include <RAT/GeoSolidFactory.hh>

namespace THEIA {
class GeoTheiaFactory : public RAT::GeoSolidFactory {
 public:
  GeoTheiaFactory() : GeoSolidFactory("theia"){};
  virtual G4VSolid *ConstructSolid(RAT::DBLinkPtr table);
};

}  // namespace THEIA

#endif
