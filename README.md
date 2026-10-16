# HS3 Test Fixtures

Conformance fixtures for the [HS3](https://github.com/hep-statistics-serialization-standard)
(HEP Statistics Serialization Standard) file format: frozen HS3 model files and
the expected results every backend is compared against.

This repository holds **data only**. The runner, backend adapters, schemas, and
generation tooling live in
[`HS3TestSuiteCode`](https://github.com/hep-statistics-serialization-standard/HS3TestSuiteCode).

## Layout

```
manifest.json                       index of all fixtures (generated)
fixtures/<test_id>/hs3.json         the HS3 model under test
fixtures/<test_id>/metadata.json    provenance, description, scan specs
fixtures/<test_id>/expected.json    frozen expected values (generated)
```

`hs3.json` and `metadata.json` are hand-written. `expected.json` and
`manifest.json` are produced by CI and must not be edited by hand.

## Adding a fixture

The easiest way is the submission form at [hs3.app.cern.ch](https://hs3.app.cern.ch),
which validates your HS3 file and opens the pull request for you. To do it by hand:

1. Create `fixtures/<test_id>/` with `hs3.json` and `metadata.json`.
2. In `metadata.json`, set `reference_backend` to a pullable container image
   that provides `generate-fixtures` (see
   `HS3TestSuiteCode/docs/reference-backend-contract.md`) and list the scans
   you want frozen:

   ```json
   "nll_scans":      [{ "id": "mean", "pdf": "gauss", "data": "gaussData",
                        "parameters": ["mean"], "points": [[-1.0], [0.0], [1.0]] }],
   "pdf_scans":      [{ "id": "shape", "pdf": "gauss", "observables": ["x"],
                        "parameters": ["mean"], "points": [[0.0], [1.0]] }],
   "function_scans": [{ "id": "bias", "function": "bias",
                        "parameters": ["truth"], "points": [[103.0], [113.0]] }]
   ```

3. Open a pull request and add the **`generate fixtures`** label. CI runs
   `generate-fixtures` inside the reference image and pushes `expected.json`
   and `manifest.json` back to the branch. Re-apply the label to regenerate.

What each scan checks, and the comparison rules, are documented in
`HS3TestSuiteCode`.

## License

[MIT](LICENSE).

The `rf*` fixtures are HS3 exports of models from the
[ROOT RooFit tutorials](https://root.cern/doc/master/group__tutorial__roofit.html),
adapted for this suite and relicensed under MIT with the agreement of the
RooFit maintainers. Submitting a fixture means confirming that you have the
right to share it under MIT.
