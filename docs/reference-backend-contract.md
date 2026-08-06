# Reference-backend generation contract

This document specifies what a reference-backend Docker image must provide so the
`generate` job in `.github/workflows/update-fixtures.yaml` can use it to generate a
*new* fixture's `expected.json` and manifest entry when a PR adds
`fixtures/<test_id>/hs3.json` + `metadata.json` and is labeled `generate fixtures`.
This flow is for onboarding new fixtures only — it never re-generates or mutates an
already-committed fixture.

It exists so that adding a new reference backend never requires touching this
workflow, and never requires the backend author to write Python. The builtin RooFit
pipeline (`tools/build_manifest_and_expected.py`, with the optional
`hs3suite_backend.HS3TestSuiteBackend` plugin seam described in `CLAUDE.md`) remains
the default, blessed path for backend authors who are fine writing Python. This
contract exists for everyone else.

## Picking up an image

`update-fixtures.yaml`'s `determine-jobs` job reads each new fixture's
`fixtures/<test_id>/metadata.json`, and uses its `reference_backend` field directly as
the container image reference (`matrix.image`) for the `generate` job. That field must
therefore be a real, pullable image reference (e.g.
`ghcr.io/your-org/hs3testsuite-mybackend:1.0`), not just a human-readable label.

## The `generate-fixtures` executable

The image must expose an executable named `generate-fixtures` on `$PATH`.

GitHub Actions' `jobs.<job>.container` never invokes the image's `ENTRYPOINT` or
`CMD` — it starts the container, keeps it alive, and runs each workflow step via
`docker exec`. So `generate-fixtures` must be a real, discoverable executable, not
something wired up only through the image's default command.

**Invocation:**

```
generate-fixtures <absolute-path-to-fixture-dir>
```

Called as, e.g.:

```
generate-fixtures "$GITHUB_WORKSPACE/fixtures/rf101_basics"
```

**Environment:** the step runs inside the already-checked-out PR branch. Working
directory is the repo root (`$GITHUB_WORKSPACE`). `<fixture-dir>/hs3.json` and
`<fixture-dir>/metadata.json` already exist on disk (the PR that triggers this flow
adds both).

**Required effects on success:**

- `<fixture-dir>/expected.json` is written, valid against
  `schemas/expected.schema.json`.
- `<repo-root>/manifest.json` is *extended* (not replaced) with this fixture's entry,
  valid against `schemas/manifest.schema.json` — including correct
  `hashes.sha256` / `hashes.canonical_sha256` for `hs3.json` (see `raw_sha256` /
  `canonical_sha256` in `hs3suite/manifest.py`).

A non-zero exit code fails the `generate` job and nothing is committed.

For the RooFit reference image, `generate-fixtures` is a thin wrapper that sources the
ROOT environment and execs
`python3 "$GITHUB_WORKSPACE/tools/build_manifest_and_expected.py" -e -f "$1"` — i.e. it
delegates to this repo's existing Python pipeline. A backend author working in another
language instead ships a self-contained `generate-fixtures` that reproduces the same
effects above without depending on this repo's Python at all.

## Validating a backend container (not yet designed)

There is currently no automated check that a non-RooFit `generate-fixtures`
implementation produces numerically correct output — schema-valid isn't the same as
correct. Cross-checking each new submission against RooFit was considered and
rejected: RooFit can't import every HS3 feature, so it can't serve as ground truth for
fixtures that specifically exercise features RooFit doesn't support, which is likely
to be exactly why a non-RooFit backend was used in the first place.

The direction being considered instead is validating the *backend container itself*,
independent of any specific new fixture: run a candidate `generate-fixtures` image
against a fixed set of existing fixtures that are tagged as using only HS3 "core"
features (features every conformant backend is expected to support), and check
agreement there. This requires fixtures to be mapped to conformance classes first,
which doesn't exist yet (see `conformance`/`semantic` fields in `hs3suite/specs.py` and
`features` in `manifest.json` for the current, incomplete building blocks). Until that
mapping exists, there is no automated backend-container validation — new
non-RooFit-generated fixtures are trusted on review, not gated by CI.
