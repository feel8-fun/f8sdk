# Extension capabilities

An extension is an installation unit, not necessarily a graph service. `ExtensionManifest` can combine `serviceClasses`, `tools`, `skills`, and `resources`; at least one capability is required. A tool/skill-only package may omit its service index. `validate_capabilities` checks IDs, field declarations, launcher constraints, and package-contained asset references without executing code.

Tools declare a stable `toolId`, name, description, command, arguments, workdir, typed input fields, optional platform restrictions, timeout, and confirmation requirement. Fields support strings, integers, finite numbers, booleans, defaults, required inputs, and string choices. Paths use the named roots described in [Service paths](service-paths.md).

Native tools launch a package-contained executable. Managed Python tools declare `python` and use the extension runtime. Shared tools declare `args: [-m, module]`; their installed code runs through the isolated shared entrypoint. Skills declare `skillId` and a package-contained `SKILL.md` path. Resources declare `resourceId`, path, and description.

Studio sends one JSON input on stdin:

```json
{"schemaVersion":"f8toolInput/1","arguments":{"target":"/games/example"}}
```

The process writes diagnostic logs to stderr and one JSON result to stdout:

```json
{"schemaVersion":"f8toolResult/1","success":true,"message":"Done","data":{}}
```

Studio owns task persistence, cancellation, execution deadlines, bounded output, and Agent approval. Tools and assets become available only while their extension is installed and enabled. Tool-side idempotence, previews, external installation records, and domain-specific skills belong to each extension implementation.

The SDK service builder still produces service wheel/runtime payloads. For tool/skill-only extensions, package the declared files directly into an extension ZIP containing `config/extensions.json`. Studio accepts these archives without requiring dummy services or nodes.
