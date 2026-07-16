# Web Development Profile

The web-development profile provides a practical baseline for modern frontend and static-site work without forcing every project to use the same framework, formatter, test runner, or package manager forever.

## Boundary

The workstation bootstrap owns host capabilities. Individual repositories own application dependencies, framework choices, lockfiles, lint rules, build configuration, and test configuration.

This means the host should provide Node.js, browser automation, certificate tooling, editor integration, and package-manager support. A project should declare exact versions of Vite, TypeScript, ESLint, Biome, Prettier, Vitest, Playwright, axe-core, React, Vue, Svelte, or other application dependencies in its own package manifest and lockfile.

Global installation of project build tools is discouraged because it creates version drift and makes CI differ from local development.

## Host capabilities

### Required

- supported Node.js runtime through `mise`
- npm supplied with Node.js
- package-manager activation support
- Git and GitHub CLI
- JSON and YAML processing
- Playwright host environment and browser cache
- a local static-file server path
- browser access for OAuth and live preview

### Recommended

- `pnpm` as a selectable package-manager provider
- `mkcert` for trusted local HTTPS certificates
- Microsoft Live Preview for embedded HTML preview in VS Code
- ESLint editor integration
- Prettier editor integration
- Playwright Test editor integration
- EditorConfig support
- GitLens or another optional Git history provider

### Optional

- Docker or another container runtime
- Dev Containers and Codespaces
- Cloudflare Wrangler
- Lighthouse CI
- accessibility testing with axe-core
- visual regression tooling
- framework-specific editor extensions

## Package-manager policy

The product must not impose one package manager globally.

Projects declare their package manager and version in `package.json` where supported:

```json
{
  "packageManager": "pnpm@<project-selected-version>"
}
```

The workstation provides the ability to activate or install the selected package manager. npm remains available as the Node.js baseline. pnpm and Yarn are pluggable providers. Bun may be added as an optional runtime and package-manager provider after its compatibility and support contracts are explicitly tested.

## Project-local baseline

A typical modern frontend project may select:

- Vite for development and production builds
- TypeScript for static typing
- ESLint or Biome for code quality
- Prettier or Biome for formatting
- Vitest for unit and component tests
- Playwright for browser and end-to-end tests
- axe-core for automated accessibility checks
- Lighthouse CI for performance and quality budgets

These are examples, not permanent product mandates. The capability model allows replacement when a better-supported option emerges.

## HTML workflow

### Embedded preview

Use the Microsoft Live Preview extension for fast visual inspection of HTML inside VS Code.

### Browser-equivalent validation

Use a local HTTP server and Playwright for authoritative behavior:

```bash
python3 -m http.server 8000
```

Then validate through:

```text
http://127.0.0.1:8000
```

The embedded preview is for rapid inspection. Playwright remains the validation source for interaction, responsive layouts, browser console errors, downloads, new-tab behavior, and accessibility checks.

## CI/CD baseline

A web repository should normally expose a small command contract such as:

```text
install
format-check
lint
typecheck
unit-test
browser-test
build
package
```

The exact command names may differ, but CI and local development must invoke the same repository-owned commands.

A representative package-script contract is:

```json
{
  "scripts": {
    "format:check": "<formatter check command>",
    "lint": "<lint command>",
    "typecheck": "<typecheck command>",
    "test": "<unit test command>",
    "test:browser": "<browser test command>",
    "build": "<production build command>"
  }
}
```

## Quality gates

Web projects should be able to opt into:

- deterministic dependency installation from a lockfile
- formatting validation
- linting
- type checking
- unit tests
- browser tests
- accessibility checks
- responsive viewport checks
- console-error detection
- production build validation
- broken-link checks
- secret scanning
- dependency and license scanning
- artifact checksums and provenance

## Principle

The bootstrap should make modern web development easy to begin, but it should not become a global framework generator that silently dictates every repository's architecture. Host capability is shared. Project semantics remain local.
