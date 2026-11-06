#!/usr/bin/env python3
"""Validate registry.json against the schema plus registry-wide invariants.

Run locally: python3 scripts/validate.py
CI runs this on every PR (see .github/workflows/validate.yml).
"""
import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    sys.exit("Missing dependency: pip install jsonschema")

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "registry.json"
SCHEMA = ROOT / "schema" / "registry.schema.json"


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    schema = json.loads(SCHEMA.read_text())

    errors = []

    # 1. JSON Schema validation.
    validator = Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(registry), key=lambda e: e.path):
        loc = "/".join(str(p) for p in err.path) or "(root)"
        errors.append(f"schema: {loc}: {err.message}")

    # 2. Registry-wide invariants the schema can't express.
    names = [p.get("name") for p in registry.get("packages", [])]
    dupes = {n for n in names if names.count(n) > 1}
    for n in sorted(dupes):
        errors.append(f"duplicate package name: {n!r}")

    # The registry is a full catalog: core and compiled built-in packages are
    # metadata-only entries (installed via a flag, no remote descriptor), so an
    # entry without mcp/app/pages is valid. Schema validation + unique names are
    # the invariants that matter.

    # 3. A `hosted` block's four naming fields must agree with each other and
    #    with the entry. The schema holds each one's shape; only this can hold
    #    them to EACH OTHER, and that is the half that fails quietly.
    #
    #    The sha256 pins the BYTES and not which package they are. So a `url`
    #    copied from a neighbouring entry, with that artifact's own correct hash
    #    beside it, passes every integrity check on the install path and
    #    installs a package nobody reviewed. There is no later gate that reads
    #    the URL: step 2 of the install verifies the hash it was given against
    #    the bytes it fetched, and both belong to the wrong package.
    for p in registry.get("packages", []):
        hosted = p.get("hosted")
        if not isinstance(hosted, dict):
            continue
        name = p.get("name")
        pkgname = hosted.get("pkgname")
        if pkgname != f"leo-package-{name}":
            errors.append(
                f"{name}: hosted.pkgname is {pkgname!r}, expected "
                f"'leo-package-{name}' — it would be served under one name and "
                f"land on disk under another"
            )
        expected = f"{pkgname}-{hosted.get('version')}-{hosted.get('arch')}.pkg.tar.zst"
        basename = str(hosted.get("url", "")).split("?")[0].split("#")[0].rsplit("/", 1)[-1]
        if basename != expected:
            errors.append(
                f"{name}: hosted.url ends in {basename!r}, but pkgname/version/"
                f"arch describe {expected!r} — the hash pins the bytes, not "
                f"which package they are"
            )

    if errors:
        print(f"registry.json INVALID ({len(errors)} problem(s)):\n", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"registry.json OK — {len(names)} package(s) validated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
