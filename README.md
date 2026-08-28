# HS3TestSuite

Backend-neutral HS3 conformance fixtures and checks.

The committed fixtures are frozen HS3 JSON files with per-test expected
results. The suite is designed so backends can be compared on the same HS3
input files and the same machine-readable expectations.

## How to Run

Run all checks with the RooFit backend:

```bash
python -m hs3suite run --backend roofit
```

Run one fixture:

```bash
python -m hs3suite run --backend roofit --test-id rf101_basics
```

Run with the pyhs3 backend from the local mamba environment:

```bash
mamba run -n pyhs3 python -m hs3suite run --backend pyhs3
```

Or, from inside that environment:

```bash
python -m hs3suite run --backend pyhs3 --test-id rf101_basics
```

Validate the suite metadata, hashes, and runner behavior:

```bash
pytest
```

## Repository Layout

- `manifest.json`: index of all fixtures, their features, hashes, checks, and
  backend-specific expectations.
- `fixtures/<test_id>/hs3.json`: frozen HS3 model file.
- `fixtures/<test_id>/metadata.json`: human-readable provenance and notes.
- `fixtures/<test_id>/expected.json`: machine-readable checks and frozen
  expected values.
- `schemas/*.schema.json`: local JSON schemas for manifest, metadata, and
  expected files.
- `hs3suite/`: Python runner and backend adapters.
- `tests/`: pytest coverage for schema validation, hashes, feature extraction,
  runner behavior, and xfail handling.

## IDs

There are several IDs with different meanings:

- `test_id`: identifies one fixture, for example `rf101_basics`. It ties
  together the manifest entry and the files under `fixtures/rf101_basics/`.
- check `id`: identifies one check inside `expected.json`, for example
  `static_integrity`, `structure_import`, `twice_delta_nll_scan`, `pdf_scan`, or
  `function_scan`.
- check `kind`: tells the runner how to execute a check. The current kinds are
  `static_integrity`, `structure_import`, `twice_delta_nll_scan`, `pdf_scan`, and
  `function_scan`.
- schema `$id`: JSON Schema identifier only; it is not a fixture or check ID.

Runner output uses `test_id::check_id`, for example:

```text
PASSED  rf101_basics::twice_delta_nll_scan
```

## Manifest

`manifest.json` is the suite index. For each fixture it records:

- `test_id`: fixture name.
- `path`: directory containing `hs3.json`, `metadata.json`, and `expected.json`.
- `hashes.sha256`: byte-for-byte SHA-256 of `hs3.json`.
- `hashes.canonical_sha256`: SHA-256 after canonical JSON serialization.
- `features.sections`: HS3 top-level list sections present in the file, such
  as `data`, `distributions`, `domains`, `functions`, or `parameter_points`.
- `features.types`: HS3 `type` values found in relevant sections, such as
  `gaussian_dist`, `product_domain`, or `unbinned`.
- `features.semantic`: manually assigned higher-level feature tags, such as
  `gaussian`, `integral`, `fft_convolution`, or `product_pdf`.
- `tags`: general labels, currently `roofit_tutorial`.
- `conformance`: conformance grouping labels.
- `checks`: check IDs present in the fixture's `expected.json`.
- `backend_expectations`: known backend-specific behavior, such as expected
  failures.

The hashes make fixture changes explicit. If `hs3.json` changes, expected
values and manifest hashes should be updated together.

## Fixture Files

Each fixture directory contains three files.

`hs3.json` is the actual HS3 input file consumed by backends. It is the thing
under test.

`metadata.json` is descriptive. It records the source tutorial, title,
description, reference backend, and notes about any intentional modifications
from the original tutorial.

`expected.json` defines the checks. A typical file has:

```json
{
  "schema_version": 1,
  "test_id": "rf101_basics",
  "checks": [
    { "id": "static_integrity", "kind": "static_integrity" },
    {
      "id": "structure_import",
      "kind": "structure_import",
      "target": {
        "pdfs": ["gauss"],
        "functions": [],
        "data": ["gaussData"]
      }
    },
    {
      "id": "twice_delta_nll_scan",
      "kind": "twice_delta_nll_scan",
      "target": { "pdf": "gauss", "data": "gaussData" },
      "reference_point": { "mean": 1.0, "sigma": 3.0, "x": 0.0 },
      "scan_parameters": ["mean"],
      "scan_points": [[-1.0], [0.0], [1.0], [2.0], [3.0]],
      "expected": [888.0456117195517, 224.26202740723056, 0.0, 213.06114567253644, 856.1426350606562],
      "tolerance": { "atol": 1e-7, "rtol": 1e-8 }
    }
  ]
}
```

`scan_parameters` is a list and each entry of `scan_points` is a list of the same length, so a scan can vary several parameters at once.

A `pdf_scan` check has the same shape but needs no dataset, so it also works on an `hs3.json` with no `data` section at all:

```json
{
  "id": "pdf_scan",
  "kind": "pdf_scan",
  "target": { "pdf": "gauss", "observables": ["x"] },
  "reference_point": { "mean": 0.0, "sigma": 1.0, "x": 0.0 },
  "scan_parameters": ["x"],
  "scan_points": [[-2.0], [-1.0], [0.0], [1.0], [2.0]],
  "expected": [0.05399096651318806, 0.24197072451914337, 0.3989422804014327, 0.24197072451914337, 0.05399096651318806],
  "tolerance": { "atol": 1e-12, "rtol": 1e-8 }
}
```

## Check Types

`static_integrity` parses `hs3.json` as JSON. This catches malformed files
before any backend is involved.

`structure_import` imports the HS3 file into the backend and verifies that
expected PDFs, functions, and datasets are present. In the RooFit backend this
means loading the file into a `RooWorkspace` using `RooJSONFactoryWSTool`.

`twice_delta_nll_scan` is the main quantitative check. It:

1. Imports the HS3 model.
2. Finds the target PDF and dataset.
3. Applies the `reference_point`.
4. Builds an NLL.
5. Evaluates `2 * (NLL(scan point) - NLL(reference point))` at each scan point.
6. Compares pointwise with `abs(actual - expected) <= atol + rtol * abs(expected)`.

The suite prefers `2DeltaNLL` rather than raw NLL because raw NLL can include
backend-dependent constants or offsets.

`pdf_scan` and `function_scan` are the quantitative checks for models that carry no data.  
Each:

1. Imports the HS3 model.
2. Finds the target PDF or function.
3. At each scan point, re-applies the `reference_point` and then overwrites the
   scanned names.
4. Evaluates the target.
5. Compares pointwise with the same rule as `twice_delta_nll_scan`.

They differ only in the target. `pdf_scan` takes
`{ "pdf": ..., "observables": [...] }` and evaluates a probability density
**normalised over the listed observables**. `function_scan` takes
`{ "function": ... }` and evaluates a plain function value.

The `observables` list is required for `pdf_scan` for the same reason the suite
prefers `2DeltaNLL` over raw NLL: an unnormalised pdf value carries an arbitrary
backend-dependent constant. Declaring the observables in the fixture makes the normalisation domain
part of the frozen contract rather than an implicit backend convention.

`function_scan` needs no normalisation set: a `RooAbsReal` has no normalisation to
apply, so its raw value is already comparable across backends.

## Backend Imports

The word "import" in this suite usually means backend import of an HS3 model,
not a Python import.

For RooFit, backend import is:

```python
ws = ROOT.RooWorkspace("hs3suite_ws")
tool = ROOT.RooJSONFactoryWSTool(ws)
tool.importJSON("fixtures/<test_id>/hs3.json")
```

After import, the backend adapter exposes common operations to the runner:

- list PDFs/functions/data for structural checks
- build an NLL from a PDF and dataset
- evaluate fixed scan points

The RooFit and pyhs3 adapters implement the same runner operations.

For pyhs3, backend import is:

```python
ws = pyhs3.Workspace.load("fixtures/<test_id>/hs3.json", suppress_traceback=False)
```

The committed fixtures do not include likelihood objects for every scan. The
pyhs3 adapter creates a temporary in-memory `pyhs3.likelihoods.Likelihood`
from the `target.pdf` and `target.data` fields in `expected.json`, then
evaluates `-2 * model.log_prob` at the frozen scan points. The HS3 fixture
files and manifest hashes are unchanged.

PyTensor compilation uses `/tmp/hs3suite_pytensor` as the default compiledir
when `PYTENSOR_FLAGS` is not already set. This avoids relying on a writable
home-directory PyTensor cache.

## Expected Failures

Known backend-specific failures are represented in `manifest.json` under
`backend_expectations`.

Currently `rf209_anaconv` is marked as an expected RooFit failure because
ROOT 6.41.01 exports internal analytical-convolution names that
`RooJSONFactoryWSTool.importJSON()` rejects on import.

Expected failures count as `XFAIL`, not as failed tests. If an expected-failing
fixture unexpectedly passes, the runner reports `XPASS` as a failure so the
manifest can be reviewed.

The pyhs3 backend intentionally does not mark current implementation gaps as
skip or xfail. Unsupported pyhs3 features and numerical disagreements are
reported as `FAILED` checks so a pyhs3 run shows directly which HS3 features
still need implementation.

## Runner Flow

The runner does the following:

1. Build the requested backend adapter.
2. Load `manifest.json`.
3. Validate JSON files against local schemas.
4. Verify `hs3.json` hashes from the manifest.
5. For each selected fixture, load `expected.json`.
6. Execute each check according to its `kind`.
7. Report `PASSED`, `FAILED`, `XFAIL`, or `SKIPPED`.

The command exits with a nonzero status only if there are real failures.

## Updating Tests

The committed files are the source of truth for the public suite. If a fixture
or expected value is changed, keep these pieces consistent:

- `fixtures/<test_id>/hs3.json`
- `fixtures/<test_id>/expected.json`
- `fixtures/<test_id>/metadata.json`
- `manifest.json` hashes and check list

The current pytest coverage checks schemas, hashes, feature extraction, one
representative RooFit scan, and expected-failure handling.
