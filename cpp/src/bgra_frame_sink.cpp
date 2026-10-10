#include "f8cppsdk/bgra_frame_sink.h"
#include "f8cppsdk/time_utils.h"
#include <cstring>
#include <limits>
#include <utility>
namespace f8::cppsdk {
class ZenohBgraFrameSink::Impl {
 public:
  explicit Impl(std::shared_ptr<f8::cppsdk::ZenohLatestVideoFramePublisher> publisher)
      : publisher_(std::move(publisher)) {}

  bool ensureConfiguration(unsigned width, unsigned height) {
    if (width == 0 || height == 0 || width > std::numeric_limits<unsigned>::max() / 4u ||
        static_cast<std::size_t>(height) > std::numeric_limits<std::size_t>::max() / (width * 4u)) {
      return false;
    }
    width_ = width;
    height_ = height;
    pitch_ = width * 4u;
    return true;
  }

  bool writeFrame(const void* data, unsigned stride_bytes) {
    if (!publisher_ || !publisher_->valid() || !data || width_ == 0 || height_ == 0 || pitch_ == 0) {
      return false;
    }
    if (stride_bytes < pitch_) {
      return false;
    }

    const std::byte* payload = static_cast<const std::byte*>(data);
    std::size_t payload_bytes = static_cast<std::size_t>(pitch_) * static_cast<std::size_t>(height_);
    if (stride_bytes != pitch_) {
      scratch_.assign(payload_bytes, std::byte{0});
      for (unsigned y = 0; y < height_; ++y) {
        std::memcpy(scratch_.data() + static_cast<std::size_t>(y) * pitch_,
                    payload + static_cast<std::size_t>(y) * stride_bytes, pitch_);
      }
      payload = scratch_.data();
      payload_bytes = scratch_.size();
    }

    f8::cppsdk::VideoFrameView frame;
    frame.width = width_;
    frame.height = height_;
    frame.pitch = pitch_;
    frame.format = f8::cppsdk::kVideoFormatBgra32;
    frame.frame_id = frame_id_ + 1;
    frame.ts_ms = f8::cppsdk::now_ms();
    frame.payload = payload;
    frame.payload_bytes = payload_bytes;
    if (!publisher_->publish_frame(frame)) {
      return false;
    }
    frame_id_ = frame.frame_id;
    return true;
  }

  unsigned outputWidth() const { return width_; }
  unsigned outputHeight() const { return height_; }
  unsigned outputPitch() const { return pitch_; }
  std::uint64_t frameId() const { return frame_id_; }

 private:
  std::shared_ptr<f8::cppsdk::ZenohLatestVideoFramePublisher> publisher_;
  unsigned width_ = 0;
  unsigned height_ = 0;
  unsigned pitch_ = 0;
  std::uint64_t frame_id_ = 0;
  std::vector<std::byte> scratch_;
};

ZenohBgraFrameSink::ZenohBgraFrameSink(std::shared_ptr<ZenohLatestVideoFramePublisher> publisher)
    : impl_(std::make_unique<Impl>(std::move(publisher))) {}
ZenohBgraFrameSink::~ZenohBgraFrameSink() = default;
bool ZenohBgraFrameSink::ensureConfiguration(unsigned width, unsigned height) { return impl_->ensureConfiguration(width, height); }
bool ZenohBgraFrameSink::writeFrame(const void* data, unsigned stride) { return impl_->writeFrame(data, stride); }
unsigned ZenohBgraFrameSink::outputWidth() const { return impl_->outputWidth(); }
unsigned ZenohBgraFrameSink::outputHeight() const { return impl_->outputHeight(); }
unsigned ZenohBgraFrameSink::outputPitch() const { return impl_->outputPitch(); }
std::uint64_t ZenohBgraFrameSink::frameId() const { return impl_->frameId(); }

}  // namespace f8::cppsdk
