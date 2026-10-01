# Service path references

`f8pysdk.service_paths.ServicePaths` resolves service metadata against typed, absolute roots.
Standard service indexes live at `<package>/config/service-index.json`; the package root is provided by the loader, not the process working directory.

Supported references are `${F8_PACKAGE_ROOT}`, `${F8_BUNDLE_ROOT}`, `${F8_CONFIG_ROOT}`, `${F8_RESOURCE_ROOT}`, and `${F8_MODEL_ROOT}`. A reference occupies the start of a path and accepts a slash-separated suffix. Unknown names, missing bundle roots, malformed references, drive-qualified suffixes, and symlink/traversal escapes raise `ValueError`.

The service index declares `bundleRoots` by platform (`linux`, `win32`, `darwin`, or `any`), independently for each service. This is an optional addition to `f8serviceIndex/1`; old indexes without it remain readable. A platform bundle root must resolve inside the package. Multiple services may explicitly share one bundle.

```json
{
  "schemaVersion": "f8serviceIndex/1",
  "modelRoot": "${F8_MODEL_ROOT}",
  "services": [{
    "serviceClass": "f8.audiocap",
    "manifests": {"win32": "${F8_PACKAGE_ROOT}/config/services/f8.audiocap/service.win.yml"},
    "describe": "${F8_PACKAGE_ROOT}/config/describes/f8.audiocap.json",
    "bundleRoots": {"win32": "${F8_PACKAGE_ROOT}/runtime/bundles/f8.audiocap/0.0.1/win"}
  }]
}
```

The manifest can use `${F8_BUNDLE_ROOT}/f8audiocap_service.exe` as its command and `${F8_BUNDLE_ROOT}` as its workdir. Python module entrypoints use `python -m module` and `${F8_PACKAGE_ROOT}` as workdir. Command, workdir, argument, and environment references are resolved before launch; no shell or arbitrary environment expansion occurs.

Package and bundle roots are derived from installation metadata, never overridden by environment variables. User configuration, resource, and model roots accept absolute `F8_CONFIG_ROOT`, `F8_RESOURCE_ROOT`, and `F8_MODEL_ROOT` overrides. Otherwise they use platform user directories; the default model root is `<resource root>/models`. The loader injects resolved roots into the child environment. Model metadata ships inside the package; mutable weights and user settings do not belong inside its installation directory.

Legacy relative paths retain their original index/manifest anchors for existing installations. New configs should use named roots. Installer-generated registrations may contain absolute paths and resolved environments; the installer regenerates them when payload locations change.
