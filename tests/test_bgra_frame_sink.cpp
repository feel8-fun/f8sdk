#include <gtest/gtest.h>
#include <array>
#include <limits>
#include "f8cppsdk/bgra_frame_sink.h"

TEST(BgraFrameSink, RepackPaddedRowsAndKeepIdentityOnFailure) {
  f8::cppsdk::RuntimeBackendConfig config;
  config.bus_backend = f8::cppsdk::BusBackend::kMem;
  auto publisher = std::make_shared<f8::cppsdk::ZenohLatestVideoFramePublisher>();
  f8::cppsdk::ZenohLatestVideoFrameSubscriber subscriber;
  ASSERT_TRUE(subscriber.open(config, "test/bgra/sink"));
  ASSERT_TRUE(publisher->open(config, "test/bgra/sink"));
  f8::cppsdk::ZenohBgraFrameSink sink(publisher);
  EXPECT_FALSE(sink.ensureConfiguration(0, 2));
  EXPECT_FALSE(sink.ensureConfiguration(std::numeric_limits<unsigned>::max(), 2));
  ASSERT_TRUE(sink.ensureConfiguration(1, 2));
  const std::array<std::byte, 12> pixels{std::byte{1}, std::byte{2}, std::byte{3}, std::byte{4},
      std::byte{99}, std::byte{99}, std::byte{5}, std::byte{6}, std::byte{7}, std::byte{8},
      std::byte{99}, std::byte{99}};
  EXPECT_FALSE(sink.writeFrame(pixels.data(), 3));
  EXPECT_EQ(sink.frameId(), 0u);
  ASSERT_TRUE(sink.writeFrame(pixels.data(), 6));
  const auto frame = subscriber.wait_latest(std::chrono::milliseconds(500));
  ASSERT_TRUE(frame.has_value());
  EXPECT_EQ(frame->pitch, 4u);
  EXPECT_EQ(frame->payload, (std::vector<std::byte>{std::byte{1}, std::byte{2}, std::byte{3}, std::byte{4},
      std::byte{5}, std::byte{6}, std::byte{7}, std::byte{8}}));
  EXPECT_EQ(sink.frameId(), 1u);
  publisher->close();
  EXPECT_FALSE(sink.writeFrame(pixels.data(), 6));
  EXPECT_EQ(sink.frameId(), 1u);
}
