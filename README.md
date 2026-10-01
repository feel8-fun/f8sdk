# Feel8 SDK

Shared service SDK for Python and C++. This repository owns the communication
contracts, generated models, runtime libraries, generators and SDK tests.
It builds without Studio or any extension checkout.

- `python/`: the `f8pysdk` wheel and Python tests.
- `cpp/`: the installed `f8cppsdk` CMake package and optional minimal example.
- `schemas/`: canonical service JSON, binary stream and runtime contracts.
- `tools/`: explicit generators; generated models are checked into Git.
- `tests/`: native SDK tests and shared cross-language fixtures.

Both SDKs currently use version `0.1.0`. Update both package manifests and the
CMake project version together when releasing a shared contract change.

## Develop and verify

Install Pixi 0.81.0, then run:

```sh
pixi install --locked
pixi run contracts_check
pixi run lint
pixi run typecheck
pixi run test
pixi run wheel
```

Native build commands are in `.github/workflows/quality.yml`. Conan supplies
JSON/logging dependencies; Pixi supplies Zenoh, compiler tools and GTest.
SDK CI builds native tests, exercises Python/C++ communication, verifies a
consumer of the installed CMake package, and publishes wheel/CMake artifacts.
Set `F8SDK_BUILD_TESTS=OFF` when building the SDK only. Enable the optional
example with `F8SDK_BUILD_EXAMPLES=ON`; it is never part of Studio's runtime.

## Consume

Python extensions use the wheel, or pin this repository at `.sdk` and declare
`f8pysdk = { path = ".sdk/python", editable = false }` in their Pixi manifest.
Installed C++ consumers use `find_package(f8cppsdk CONFIG REQUIRED)` and link
`f8::f8cppsdk`; the installed CMake helpers support native service deployment.
Keep dependencies on the public `f8pysdk`/`f8cppsdk` APIs rather than source paths.

Studio includes this repository as the `sdk/` submodule. Its CI owns Studio and
extension integration tests; SDK CI owns unit tests and contract checks.
The Studio HTTP/document schemas remain owned by Studio.
