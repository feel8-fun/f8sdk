"""Golden wire compatibility, including signed timestamps and 64-bit identities."""

from __future__ import annotations

from pathlib import Path
import struct
import subprocess

import pytest

from f8pysdk.generated.stream_wire import AudioChunkHeader, VideoFrameHeader

ROOT = Path(__file__).resolve().parents[2]


def test_generated_stream_files_are_current() -> None:
    from tools.generate_stream_wire import generate

    from tools.generate_runtime_keys import generate as generate_keys
    from tools.generate_runtime_policy import generate as generate_policy

    for path, content in (generate() | generate_keys() | generate_policy()).items():
        assert path.read_text() == content, f"Regenerate {path}"


def test_cpp_python_headers_match_existing_wire_bytes(tmp_path: Path) -> None:
    video = VideoFrameHeader(
        0xF85A1001, 2, 64, 3, 2, 12, 1, 24, 0xFEDCBA9876543210, -1234567, 0xFFEEDDCCBBAA9988, 0x7766554433221100
    )
    audio = AudioChunkHeader(0xF85A2001, 1, 60, 48000, 2, 1, 3, 8, 24, 0xFEDCBA9876543210, 0xAABBCCDDEEFF0011, -7654321)
    golden = struct.pack("<8IQqQQ", *video) + struct.pack("<9IQQq", *audio)
    assert video.pack() + audio.pack() == golden
    assert VideoFrameHeader.unpack_from(golden) == video
    assert AudioChunkHeader.unpack_from(golden[64:]) == audio
    source = tmp_path / "wire.cpp"
    source.write_text(r"""
#include "f8cppsdk/generated/stream_wire.h"
#include "f8cppsdk/generated/runtime_keys.h"
#include <array>
#include <iostream>
int main() {
  using namespace f8::cppsdk;
  if (wire_keys::data("svc", "node", "port") != "f8/svc/svc/nodes/node/data/port") return 4;
  if (wire_keys::command("svc", "status") != "f8/cmd/svc/svc/status") return 5;
  VideoFrameHeader video{0xF85A1001,2,64,3,2,12,1,24,0xFEDCBA9876543210ULL,-1234567,0xFFEEDDCCBBAA9988ULL,0x7766554433221100ULL};
  AudioChunkHeader audio{0xF85A2001,1,60,48000,2,1,3,8,24,0xFEDCBA9876543210ULL,0xAABBCCDDEEFF0011ULL,-7654321};
  std::array<std::uint8_t,124> data{};
  video.encode(data.data()); audio.encode(data.data()+64);
  VideoFrameHeader v; AudioChunkHeader a;
  if (VideoFrameHeader::decode(data.data(),63,v) || AudioChunkHeader::decode(data.data(),59,a)) return 1;
  if (!VideoFrameHeader::decode(data.data(),64,v) || !AudioChunkHeader::decode(data.data()+64,60,a)) return 2;
  if (v.ts_ms != -1234567 || a.ts_ms != -7654321 || v.frame_id != video.frame_id || a.frame_index != audio.frame_index) return 3;
  std::cout.write(reinterpret_cast<const char*>(data.data()), data.size());
}
""")
    (tmp_path / "CMakeLists.txt").write_text(
        'cmake_minimum_required(VERSION 3.20)\nproject(wire LANGUAGES CXX)\n'
        'add_executable(wire wire.cpp)\ntarget_compile_features(wire PRIVATE cxx_std_17)\n'
        f'target_include_directories(wire PRIVATE "{(ROOT / "cpp/include").as_posix()}")\n'
        'set_target_properties(wire PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin" '
        'RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}/bin")\n'
    )
    subprocess.run(
        ["cmake", "-S", str(tmp_path), "-B", str(tmp_path / "build")], check=True, capture_output=True,
    )
    subprocess.run(["cmake", "--build", str(tmp_path / "build"), "--config", "Release"], check=True, capture_output=True)
    import sys
    executable = tmp_path / "build/bin" / ("wire.exe" if sys.platform == "win32" else "wire")
    result = subprocess.run([str(executable)], check=True, capture_output=True)
    assert result.stdout == golden


def test_public_naming_uses_current_command_paths() -> None:
    from f8pysdk.f8_naming import data_key, svc_endpoint_key, cmd_channel_key
    from f8pysdk.zenoh_naming import zenoh_command_key, zenoh_state_key

    assert data_key(" svc ", from_node_id="node", port_id="port") == "f8/svc/svc/nodes/node/data/port"
    assert svc_endpoint_key("svc", "status") == zenoh_command_key("svc", "status") == "f8/cmd/svc/svc/status"
    assert cmd_channel_key("svc") == "f8/cmd/svc/svc/cmd"
    assert zenoh_state_key("svc", node_id="node", field="a.b") == "f8/svc/svc/state/nodes/node/state/a/b"
    with pytest.raises(ValueError):
        data_key("bad/service", from_node_id="node", port_id="port")
