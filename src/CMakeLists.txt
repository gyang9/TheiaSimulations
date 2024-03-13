add_library( THEIA SHARED
  Theia.cc
  GeoTheiaFactory.cc
  #DichroiconArrayFactory.cc
  HitmanProc.cc
  NtupleProc.cc
  LaserballGenerator.cc
)

target_include_directories( THEIA PUBLIC
  $<BUILD_INTERFACE:${THEIA_INCLUDE_DIR}>
  $<INSTALL_INTERFACE:include>)

file(COPY include/ DESTINATION ${THEIA_INCLUDE_DIR})

add_executable(theia theia.cpp)
target_link_libraries(theia PUBLIC 
  THEIA ${ROOT_LIBRARIES} ${Geant4_LIBRARIES} ${Ratpac_LIBRARIES} ${NLOPT_LIBRARIES})

set_target_properties(THEIA theia
  PROPERTIES
  ARCHIVE_OUTPUT_DIRECTORY ${THEIA_LIBRARY_DIR}
  LIBRARY_OUTPUT_DIRECTORY ${THEIA_LIBRARY_DIR})

install(TARGETS THEIA theia 
  LIBRARY DESTINATION lib
  ARCHIVE DESTINATION lib
  RUNTIME DESTINATION bin)

install(DIRECTORY ${THEIA_INCLUDE_DIR}
  DESTINATION ${CMAKE_INSTALL_PREFIX})
