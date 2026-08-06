from __future__ import annotations

from pathlib import Path

import jsonschema

from .manifest import load_json


SCHEMAS = {
    "manifest": "manifest.schema.json",
    "metadata": "metadata.schema.json",
    "expected": "expected.schema.json",
}


def validate_suite(root: Path) -> list[str]:
    errors: list[str] = []
    schemas = {
        name: load_json(root / "schemas" / filename)
        for name, filename in SCHEMAS.items()
    }
    try:
        jsonschema.validate(load_json(root / "manifest.json"), schemas["manifest"])
    except jsonschema.ValidationError as exc:
        errors.append(f"manifest.json: {exc.message}")

    for fixture_dir in sorted((root / "fixtures").iterdir()):
        if not fixture_dir.is_dir():
            continue
        for kind in ("metadata", "expected"):
            path = fixture_dir / f"{kind}.json"
            if not path.exists():
                errors.append(f"{path.relative_to(root)}: file not found")
                continue
            payload = load_json(path)
            try:
                jsonschema.validate(payload, schemas[kind])
            except jsonschema.ValidationError as exc:
                errors.append(f"{path.relative_to(root)}: {exc.message}")
            if kind == "expected":
                errors.extend(_duplicate_check_id_errors(path, root, payload))
    return errors


def _duplicate_check_id_errors(path: Path, root: Path, payload: dict) -> list[str]:
    ids = [check["id"] for check in payload.get("checks", []) if "id" in check]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if not dupes:
        return []
    return [f"{path.relative_to(root)}: duplicate check id {dup!r}" for dup in dupes]
