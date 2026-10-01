#include <string>
#include "f8cppsdk/f8_naming.h"
#include "f8cppsdk/service_runtime.h"
#include "f8cppsdk/runtime_cxxopts.h"

int main() {
  cxxopts::Options options("consumer");
  f8::cppsdk::add_runtime_backend_options(options);
  f8::cppsdk::ServiceBus::Config config;
  config.service_id = "installed-consumer";
  f8::cppsdk::ServiceRuntime runtime(config);
  return f8::cppsdk::svc_endpoint_key("installed-consumer", "status").empty() ? 1 : 0;
}
