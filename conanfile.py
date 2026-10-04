from conan import ConanFile
from conan.tools.cmake import CMake, cmake_layout


class F8Sdk(ConanFile):
    name = "f8cppsdk"
    version = "0.1.0"
    license = "Apache-2.0"
    url = "https://github.com/feel8-fun/f8sdk"
    description = "Feel8 C++ service runtime and communication SDK"
    package_type = "library"
    settings = "os", "compiler", "build_type", "arch"
    generators = "CMakeDeps", "CMakeToolchain"
    exports_sources = "CMakeLists.txt", "cpp/*", "cmake/*", "schemas/*", "tools/*", "python/*", "tests/*", "LICENSE"
    options = {"shared": [True, False], "fPIC": [True, False]}
    default_options = {"shared": False, "fPIC": True}

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def requirements(self):
        self.requires("nlohmann_json/3.12.0")
        self.requires("spdlog/1.16.0")
        self.requires("cxxopts/3.3.1")

    def layout(self):
        cmake_layout(self)

    def build(self):
        cmake = CMake(self)
        cmake.configure({"F8SDK_BUILD_TESTS": "OFF"})
        cmake.build()

    def package(self):
        CMake(self).install()

    def package_info(self):
        self.cpp_info.libs = ["f8cppsdk"]
        self.cpp_info.set_property("cmake_file_name", "f8cppsdk")
        self.cpp_info.set_property("cmake_target_name", "f8::f8cppsdk")
