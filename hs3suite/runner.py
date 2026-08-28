from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .backends import build_backend
from .manifest import load_json, verify_hashes
from .validation import validate_suite


@dataclass
class CheckResult:
    test_id: str
    check_id: str
    status: str
    message: str = ""


def compare_vectors(actual: list[float], expected: list[float], tolerance: dict[str, float]) -> None:
    if len(actual) != len(expected):
        raise AssertionError(f"length mismatch: {len(actual)} != {len(expected)}")
    rtol = float(tolerance["rtol"])
    atol = float(tolerance["atol"])
    for index, (got, want) in enumerate(zip(actual, expected, strict=True)):
        allowed = atol + rtol * abs(want)
        delta = abs(got - want)
        if delta > allowed:
            raise AssertionError(
                f"point {index}: got {got:.17g}, expected {want:.17g}, "
                f"delta {delta:.3g} > {allowed:.3g}"
            )


def run_suite(root: Path, backend_name: str, selected: set[str] | None = None) -> list[CheckResult]:
    backend = build_backend(backend_name)
    manifest = load_json(root / "manifest.json")
    results: list[CheckResult] = []

    for error in validate_suite(root):
        results.append(CheckResult("<suite>", "schema_validation", "failed", error))
    for error in verify_hashes(root, manifest):
        results.append(CheckResult("<suite>", "hash_validation", "failed", error))
    if any(result.status == "failed" for result in results):
        return results

    for fixture in manifest["fixtures"]:
        test_id = fixture["test_id"]
        if selected and test_id not in selected:
            continue
        expected = load_json(root / fixture["path"] / "expected.json")
        backend_expectation = fixture.get("backend_expectations", {}).get(backend_name, {})
        is_xfail = bool(backend_expectation.get("xfail", False))
        reason = backend_expectation.get("reason", "expected backend failure")

        try:
            fixture_results = _run_fixture(root, backend, fixture, expected)
        except Exception as exc:
            status = "xfail" if is_xfail else "failed"
            results.append(CheckResult(test_id, "<fixture>", status, f"{reason}: {exc}" if is_xfail else str(exc)))
            continue

        if is_xfail:
            failures = [result for result in fixture_results if result.status == "failed"]
            if failures:
                results.append(CheckResult(test_id, "<fixture>", "xfail", f"{reason}: {failures[0].message}"))
            else:
                results.append(CheckResult(test_id, "<fixture>", "failed", f"XPASS: {reason}"))
        else:
            results.extend(fixture_results)

    return results


def _run_fixture(root: Path, backend, fixture: dict[str, Any], expected: dict[str, Any]) -> list[CheckResult]:
    test_id = fixture["test_id"]
    hs3_path = root / fixture["path"] / "hs3.json"
    workspace = None
    results: list[CheckResult] = []

    for check in expected["checks"]:
        check_id = check["id"]
        kind = check["kind"]
        try:
            if kind == "static_integrity":
                load_json(hs3_path)
            else:
                if workspace is None:
                    workspace = backend.load_workspace(hs3_path)
                if kind == "structure_import":
                    backend.run_structure_check(workspace, check)
                elif kind == "twice_delta_nll_scan":
                    actual = backend.run_twice_delta_nll_scan(workspace, check, hs3_path)
                    compare_vectors(actual, check["expected"], check["tolerance"])
                elif kind == "pdf_scan":
                    actual = backend.run_pdf_scan(workspace, check, hs3_path)
                    compare_vectors(actual, check["expected"], check["tolerance"])
                elif kind == "function_scan":
                    actual = backend.run_function_scan(workspace, check, hs3_path)
                    compare_vectors(actual, check["expected"], check["tolerance"])
                else:
                    raise AssertionError(f"unsupported check kind {kind!r}")
        except Exception as exc:
            results.append(CheckResult(test_id, check_id, "failed", str(exc)))
        else:
            results.append(CheckResult(test_id, check_id, "passed"))
    return results


def summarize(results: list[CheckResult]) -> dict[str, int]:
    summary = {"passed": 0, "failed": 0, "skipped": 0, "xfail": 0}
    for result in results:
        summary[result.status] = summary.get(result.status, 0) + 1
    return summary
