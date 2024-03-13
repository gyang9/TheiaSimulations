#include <stdlib.h>

#include <Theia.hh>
#include <RAT/AnyParse.hh>
#include <iostream>
#include <string>

int main(int argc, char** argv) {
  auto parser = new RAT::AnyParse(argc, argv);
  std::cout << "Theia version: " << RAT::THEIAVERSION << std::endl;
  auto theia = THEIA::Theia(parser, argc, argv);
  theia.Begin();
  theia.Report();
}
