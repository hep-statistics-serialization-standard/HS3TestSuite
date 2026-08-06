from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from hs3suite_backend import HS3TestSuiteBackend
except:
    print("module 'hs3suite_backend' not found. Falling back to builtin RooFitBackend!")
    from hs3suite.backends.roofit import RooFitBackend as HS3TestSuiteBackend

from hs3suite.manifest import (
    canonical_sha256,
    extract_features,
    load_json,
    raw_sha256,
    write_json,
)
from hs3suite.specs import FIXTURES as LEGACY_FIXTURES
from hs3suite.specs import FixtureSpec, ScanSpec


def default_parameter_point(payload: dict[str, Any]) -> dict[str, float]:
    for point in payload.get("parameter_points", []):
        if point.get("name") == "default_values":
            return {
                parameter["name"]: float(parameter["value"])
                for parameter in point.get("parameters", [])
                if "name" in parameter and "value" in parameter
            }
    return {}


def structure_targets(payload: dict[str, Any]) -> dict[str, list[str]]:
    def public_function_name(item: dict[str, Any]) -> bool:
        name = item.get("name", "")
        return isinstance(name, str) and not name.endswith("_exponential_inverted")

    return {
        "pdfs": sorted(
            item["name"] for item in payload.get("distributions", []) if "name" in item
        ),
        "functions": sorted(
            item["name"]
            for item in payload.get("functions", [])
            if "name" in item and public_function_name(item)
        ),
        "data": sorted(
            item["name"] for item in payload.get("data", []) if "name" in item
        ),
    }


def comparison() -> dict[str, str]:
    return {
        "type": "pointwise_comp",
        "rule": "|evaluated - expected| <= atol + rtol * |expected|",
    }


def build_expected(spec, payload: dict[str, Any], backend: None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = [
        {"id": "static_integrity", "kind": "static_integrity"},
        {
            "id": "structure_import",
            "kind": "structure_import",
            "target": structure_targets(payload),
        },
    ]
    is_roofit_xfail = bool(
        spec.backend_expectations.get("roofit", {}).get("xfail", False)
    )
    if spec.scans and not is_roofit_xfail:
        if backend is None:
            raise RuntimeError("RooFit backend is required to build scan expectations")
        hs3_path = ROOT / "fixtures" / spec.test_id / "hs3.json"
        workspace = backend.load_workspace(hs3_path)
        for scan in spec.scans:
            target = (
                {"likelihood": scan.likelihood}
                if scan.likelihood is not None
                else {"pdf": scan.pdf, "data": scan.data}
            )
            check = {
                "id": scan.id,
                "kind": "twice_delta_nll_scan",
                "target": target,
                "reference_point": default_parameter_point(payload),
                "scan_parameters": list(scan.parameters),
                "scan_points": [list(point) for point in scan.points],
                "expected": [],
                "tolerance": {"rtol": 1e-8, "atol": 1e-7},
                "comparison": comparison(),
            }
            check["expected"] = backend.run_twice_delta_nll_scan(workspace, check, hs3_path)
            checks.append(check)
    return {"schema_version": 1, "test_id": spec.test_id, "checks": checks}


def build_metadata(spec) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "test_id": spec.test_id,
        "title": spec.title,
        "source": spec.source,
        "description": spec.description,
        "notes": list(spec.notes),
        "modified_from_source": spec.modified_from_source,
        "reference_backend": "roofit 6.41.01",
    }


def build_manifest_entry(spec, payload: dict[str, Any]) -> dict[str, Any]:
    hs3_path = ROOT / "fixtures" / spec.test_id / "hs3.json"
    features = extract_features(payload)
    features["semantic"] = sorted(spec.semantic)
    expected = load_json(ROOT / "fixtures" / spec.test_id / "expected.json")
    entry = {
        "test_id": spec.test_id,
        "path": f"fixtures/{spec.test_id}",
        "hashes": {
            "sha256": raw_sha256(hs3_path),
            "canonical_sha256": canonical_sha256(hs3_path),
        },
        "features": features,
        "tags": sorted(spec.tags),
        "conformance": sorted(spec.conformance),
        "checks": [check["id"] for check in expected["checks"]],
    }
    if spec.backend_expectations:
        entry["backend_expectations"] = spec.backend_expectations
    return entry


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", "-f", nargs="+", default=[], help="")
    parser.add_argument("--extend-manifest", "-e", action="store_true")

    args = parser.parse_args()
    backend = HS3TestSuiteBackend()

    if len(args.fixtures) > 0:
        print("generate fixtures for the test cases:")
        print("\n".join(args.fixtures))
        FIXTURES = []
        for testcase_path in args.fixtures:
            md = load_json(Path(testcase_path) / "metadata.json")
            if "nll_scans" in md:
                scans = []
                for i, scan_md in enumerate(md["nll_scans"]):
                    default_id = (
                        "twice_delta_nll_scan"
                        if len(md["nll_scans"]) == 1
                        else f"twice_delta_nll_scan_{i}"
                    )
                    scans.append(
                        ScanSpec(
                            parameters=tuple(scan_md["parameters"]),
                            points=tuple(tuple(point) for point in scan_md["points"]),
                            pdf=scan_md.get("pdf"),
                            data=scan_md.get("data"),
                            likelihood=scan_md.get("likelihood"),
                            id=scan_md.get("id", default_id),
                        )
                    )
                md["scans"] = tuple(scans)
            FIXTURES.append(
                FixtureSpec(
                    test_id=md["test_id"],
                    title=md["title"],
                    source=md["source"],
                    description=md["description"],
                    scans=md.get("scans", ()),
                    semantic=md.get("semantic", ()),
                    tags=md.get("tags", ()),
                    conformance=md.get("conformance", ()),
                    modified_from_source=md["modified_from_source"],
                    notes=md.get("notes", ""),
                    backend_expectations=md.get("backend_expectations", {}),
                    reference_backend=md["reference_backend"],
                )
            )
    else:
        FIXTURES = LEGACY_FIXTURES
    for spec in FIXTURES:
        payload = load_json(ROOT / "fixtures" / spec.test_id / "hs3.json")
        metadata_path = ROOT / "fixtures" / spec.test_id / "metadata.json"
        if not metadata_path.exists():
            write_json(metadata_path, build_metadata(spec))
        write_json(
            ROOT / "fixtures" / spec.test_id / "expected.json",
            build_expected(spec, payload, backend),
        )

    manifest_path = ROOT / "manifest.json"
    if args.extend_manifest and manifest_path.exists():
        manifest = load_json(manifest_path)
        manifest["schema_version"] = 1
        manifest["generated_by"] = "tools/build_manifest_and_expected.py"
    else:
        manifest = {
            "schema_version": 1,
            "generated_by": "tools/build_manifest_and_expected.py",
            "fixtures": [],
        }

    for spec in FIXTURES:
        payload = load_json(ROOT / "fixtures" / spec.test_id / "hs3.json")
        manifest["fixtures"].append(build_manifest_entry(spec, payload))
    write_json(manifest_path, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
