#include <chrono>
#include <csignal>
#include <exception>
#include <iostream>
#include <thread>

#include "f8cppsdk/service_runtime.h"

namespace {
volatile std::sig_atomic_t stopped = 0;
void stop(int) { stopped = 1; }
}

int main(int argc, char** argv) {
  if (argc != 2) {
    std::cerr << "Usage: f8_minimal_service <service-id>\n";
    return 2;
  }
  std::signal(SIGINT, stop);
  std::signal(SIGTERM, stop);
  try {
    f8::cppsdk::ServiceBus::Config config;
    config.service_id = argv[1];
    config.service_class = "f8.example.minimal";
    f8::cppsdk::ServiceRuntime runtime(config);
    if (!runtime.start()) {
      std::cerr << "Failed to start service " << config.service_id << '\n';
      return 1;
    }
    while (!stopped) {
      std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
    runtime.stop();
  } catch (const std::exception& error) {
    std::cerr << "Minimal service failed: " << error.what() << '\n';
    return 1;
  }
}
