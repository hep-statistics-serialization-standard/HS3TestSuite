from __future__ import annotations

import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hs3suite.backends.roofit import RooFitBackend, suppress_root_output  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Upconvert HS3 JSON files by importing and re-exporting them with RooFit."
    )
    parser.add_argument(
        "hs3_files",
        nargs="*",
        type=Path,
        help="HS3 JSON files to upconvert. Defaults to every fixture hs3.json in manifest.json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Write upconverted files under this directory instead of overwriting in place.",
    )
    parser.add_argument(
        "--show-root-output",
        action="store_true",
        help="Do not suppress RooFit diagnostics while importing and exporting.",
    )
    return parser


def discover_hs3_files(root: Path, explicit_files: Iterable[Path]) -> list[Path]:
    files = [path.resolve() for path in explicit_files]
    if files:
        return files

    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        return [
            (root / fixture["path"] / "hs3.json").resolve()
            for fixture in manifest.get("fixtures", [])
        ]

    return sorted((root / "fixtures").glob("*/hs3.json"))


def output_path_for(input_path: Path, root: Path, output_dir: Path | None) -> Path:
    if output_dir is None:
        return input_path

    try:
        relative_path = input_path.relative_to(root)
    except ValueError:
        relative_path = Path(input_path.name)
    return output_dir / relative_path


def upconvert_hs3_file(
    backend: RooFitBackend,
    input_path: Path,
    output_path: Path,
    *,
    suppress_output: bool,
) -> None:
    if not input_path.is_file():
        raise FileNotFoundError(input_path)

    workspace = backend.ROOT.RooWorkspace("ws")
    tool = backend.ROOT.RooJSONFactoryWSTool(workspace)
    context = suppress_root_output() if suppress_output else nullcontext()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        dir=output_path.parent,
    )
    os.close(fd)

    temp_path = Path(temp_name)
    try:
        with context:
            if not tool.importJSON(str(input_path)):
                raise RuntimeError("RooFit importJSON returned false")
            if not tool.exportJSON(str(temp_path)):
                raise RuntimeError("RooFit exportJSON returned false")
        os.replace(temp_path, output_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir.resolve() if args.output_dir else None
    hs3_files = discover_hs3_files(ROOT, args.hs3_files)

    if not hs3_files:
        print("No HS3 files found.", file=sys.stderr)
        return 1

    backend = RooFitBackend()
    failures: list[tuple[Path, Exception]] = []

    for input_path in hs3_files:
        output_path = output_path_for(input_path, ROOT, output_dir)
        try:
            upconvert_hs3_file(
                backend,
                input_path,
                output_path,
                suppress_output=not args.show_root_output,
            )
        except Exception as exc:
            failures.append((input_path, exc))
            print(f"FAILED {display_path(input_path, ROOT)}: {exc}", file=sys.stderr)
            continue

        source = display_path(input_path, ROOT)
        target = display_path(output_path, ROOT)
        if source == target:
            print(f"UPDATED {source}")
        else:
            print(f"UPDATED {source} -> {target}")

    if failures:
        print(f"Failed to upconvert {len(failures)} of {len(hs3_files)} HS3 file(s).", file=sys.stderr)
        return 1

    print(f"Upconverted {len(hs3_files)} HS3 file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
