#pragma once

#include <cstdint>
#include <memory>

#include "f8cppsdk/latest_video_frame_transport.h"

namespace f8::cppsdk {

class BgraFrameSink {
 public:
  virtual ~BgraFrameSink() = default;

  virtual bool ensureConfiguration(unsigned width, unsigned height) = 0;
  virtual bool writeFrame(const void* data, unsigned stride_bytes) = 0;

  virtual unsigned outputWidth() const = 0;
  virtual unsigned outputHeight() const = 0;
  virtual unsigned outputPitch() const = 0;
  virtual std::uint64_t frameId() const = 0;
};

// Repacks padded BGRA rows and advances identity only after a successful publish.
class ZenohBgraFrameSink final : public BgraFrameSink {
 public:
  explicit ZenohBgraFrameSink(std::shared_ptr<ZenohLatestVideoFramePublisher> publisher);
  ~ZenohBgraFrameSink();
  bool ensureConfiguration(unsigned width, unsigned height) override;
  bool writeFrame(const void* data, unsigned stride_bytes) override;
  unsigned outputWidth() const override;
  unsigned outputHeight() const override;
  unsigned outputPitch() const override;
  std::uint64_t frameId() const override;
 private:
  class Impl;
  std::unique_ptr<Impl> impl_;
};

}  // namespace f8::cppsdk
