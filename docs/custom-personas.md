# Add a custom persona

Use `gabriel-gadget scaffold` to author a complete portable package without
overwriting existing files. A package contains `persona.json`, an authored
`assets/chat-config.json`, an example ontology, `fixture.json`, `expected.json`,
`scenarios.json` and a README. The SDK discovers packages under its configured
catalog root; it never executes code supplied in a persona package.

```sh
gabriel-gadget scaffold /tmp/my-personas/gardener --id gardener --name Fern \
  --domain 'garden planning' --boundary 'Ask before buying or spraying anything.'
gabriel-gadget --packs /tmp/my-personas validate
gabriel-gadget --packs /tmp/my-personas enroll garden-desk --personas gardener \
  --token-file .state/garden-desk.token
gabriel-gadget --packs /tmp/my-personas serve --config backends.json
```

The generic custom fixture engine prepares the declared synthetic task. Add
domain-specific deterministic engines with tests when contributing richer
examples to this repository; arbitrary package code is never loaded by the bridge.

For live custom behavior, publish the authored chat configuration through the
authorized Gabriel authoring flow, attach its real knowledge/tools/workflows,
and map the catalog ID to its published persona ID and token environment variable
in a cloud or local backend binding. The catalog ID and published backend ID are
different concepts. The gadget selector does not create or activate a persona.

Capabilities are discovered from the published persona. A model endpoint alone
does not supply a workflow harness, browser adapter, local speech or tool safety.
Review the intended domain boundary and test actual provider outputs before use.

One-prompt coding-agent brief:

> Read this repository's SKILL.md. Create a new gadget example named Fern for
> garden planning. It should prepare a watering plan from synthetic plant and
> weather observations, cite its inputs, and ask before buying or spraying.
> Include a fixture, exact expected result, boundary tests and setup instructions.
> Add a cloud/local binding template with environment variable names only.
> Run the package and SDK checks; do not create live effects or paste credentials.
