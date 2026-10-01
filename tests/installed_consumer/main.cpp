#include <string>
#include "f8cppsdk/f8_naming.h"
#include "f8cppsdk/service_runtime.h"

int main() {
  f8::cppsdk::ServiceBus::Config config;
  config.service_id = "installed-consumer";
  f8::cppsdk::ServiceRuntime runtime(config);
  return f8::cppsdk::svc_endpoint_key("installed-consumer", "status").empty() ? 1 : 0;
}
