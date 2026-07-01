# leo-registry

Public catalog of installable **data-driven Leo packages** — the ones that load
with *no rebuild*. A Leo instance fetches `registry.json`, shows a catalog, and
installs an entry by writing a `dynamic_packages` row + optional MCP server and
(optionally) downloading a verified frontend bundle. Nothing is compiled into
Leo.

## Hosting

Source of truth is this git repo. It's published to **Cloudflare Pages** at:

```
https://packages.aurum.academy/registry.json        # the catalog
https://packages.aurum.academy/bundles/<pkg>/ui.js  # frontend bundles
```

`registry.json` is a static, cacheable, public file. It is *not* secret — a
catalog isn't sensitive. Installation is gated by each Leo instance's own auth,
not by hiding this URL. Integrity is enforced per-bundle via `sha256` (see below).

## Adding a package

1. Add an entry to `packages` in `registry.json`. Minimum:

   ```jsonc
   {
     "name": "acme",                      // ^[A-Za-z0-9_-]+$, unique
     "label": "Acme",
     "description": "What it does.",
     "icon": "puzzle",
     "version": "1.0.0",
     "mcp": {                             // where the tools come from
       "transport": "stdio",
       "command": "npx",
       "args": ["-y", "@acme/mcp-server"]
     }
   }
   ```

2. **(Optional) settings / pages / migrations** via `descriptor`:

   ```jsonc
   "descriptor": {
     "fields": [
       { "key": "api_key", "label": "API Key", "field_type": "password", "required": true }
     ],
     "pages": [
       { "path": "dashboard", "label": "Acme", "sidebar_group": "Workspace" }
     ],
     "migrations": ["CREATE TABLE IF NOT EXISTS acme_x (id TEXT PRIMARY KEY)"]
   }
   ```

3. **(Optional) frontend bundle** — if the package has pages, ship an ES module
   that default-exports a `{ [path]: React.ComponentType }` map. Place it at
   `bundles/<name>/ui.js` and reference it with its hash:

   ```jsonc
   "bundle": {
     "url": "https://packages.aurum.academy/bundles/acme/ui.js",
     "sha256": "<64-hex sha256 of the file>"     // REQUIRED — Leo verifies before install
   }
   ```

   Compute the hash: `sha256sum bundles/acme/ui.js`.

### Entitlements (what the package is allowed to do)

Every package declares the capabilities it needs. Leo shows these at install for
the user to consent to, and the broker grants **exactly these and nothing more**
— least privilege. This is what makes installing from a public catalog safe:
"remote" means *scoped*, not just *elsewhere*.

```jsonc
"descriptor": {
  "entitlements": {
    "feed": true,                                  // may post to the feed
    "push": false,                                 // may send push notifications
    "settings_read": ["fal_api_key", "openai_api_key"],  // ONLY these keys
    "network": ["api.fal.ai", "generativelanguage.googleapis.com"],
    "storage_mb": 50
  }
}
```

Ask for the minimum. A package that omits `entitlements` asks for nothing.

### App packages (`kind: "app"`)

Some packages aren't a set of tools — they're a full app with their own backend
and UI (their own storage, endpoints, screens). Those declare `kind: "app"` and
an `app` block. Leo clones the repo, **builds a standalone binary on the host**
(this does NOT rebuild Leo — it's a separate process), runs it as a subprocess
with its own SQLite, and proxies `/p/<name>/*` to it.

```jsonc
{
  "name": "brand-lab",
  "label": "Brand Lab",
  "description": "AI brand identity studio.",
  "icon": "sparkles",
  "descriptor": {
    "kind": "app",
    "app": {
      "repo": "https://github.com/brandondek/leo-brand-lab",
      "branch": "main",
      "build": "cargo build --release",
      "bin": "target/release/leo-brand-lab",
      "port": 0
    },
    "entitlements": {
      "settings_read": ["fal_api_key", "openai_api_key", "google_api_key"],
      "network": ["api.fal.ai", "api.openai.com", "generativelanguage.googleapis.com"],
      "storage_mb": 200
    }
  }
}
```

4. Validate, then open a PR:

   ```bash
   pip install jsonschema
   python3 scripts/validate.py
   ```

   CI runs the same check on every PR. It enforces the schema, unique names,
   required `sha256` on bundles, and that each package actually does something
   (has an MCP server or pages).

## Schema

`schema/registry.schema.json` (JSON Schema 2020-12) is the authoritative format.
Each entry mirrors Leo's `POST /api/packages/install-dynamic` body. Bumping the
top-level `schema` integer signals a breaking format change.
