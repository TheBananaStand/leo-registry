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

    if errors:
        print(f"registry.json INVALID ({len(errors)} problem(s)):\n", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"registry.json OK — {len(names)} package(s) validated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
