from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import sys
from typing import Any

from ..manifest import load_json


class RooFitBackend:
    name = "roofit"

    def __init__(self) -> None:
        import ROOT  # type: ignore

        self.ROOT = ROOT
        ROOT.gROOT.SetBatch(True)
        ROOT.gErrorIgnoreLevel = ROOT.kFatal
        ROOT.RooMsgService.instance().setGlobalKillBelow(ROOT.RooFit.FATAL)

    def load_workspace(self, path: Path):
        ws = self.ROOT.RooWorkspace("hs3suite_ws")
        tool = self.ROOT.RooJSONFactoryWSTool(ws)
        with suppress_root_output():
            tool.importJSON(str(path))
        return ws

    def structure(self, workspace) -> dict[str, list[str]]:
        return {
            "pdfs": sorted(obj.GetName() for obj in workspace.allPdfs()),
            "functions": sorted(obj.GetName() for obj in workspace.allFunctions()),
            "data": sorted(obj.GetName() for obj in workspace.allData()),
        }

    def run_structure_check(self, workspace, check: dict[str, Any]) -> None:
        actual = self.structure(workspace)
        target = check.get("target", {})
        for key in ("pdfs", "functions", "data"):
            required = set(target.get(key, []))
            missing = required.difference(actual[key])
            if missing:
                raise AssertionError(f"missing {key}: {sorted(missing)}")

    def run_twice_delta_nll_scan(self, workspace, check: dict[str, Any], hs3_path: Path) -> list[float]:
        target = check["target"]
        pairs = self._resolve_target_pairs(target, hs3_path)
        pdf_data_objs = []
        for pdf_name, data_name in pairs:
            pdf = workspace.pdf(pdf_name)
            if pdf is None:
                raise AssertionError(f"PDF {pdf_name!r} not found")
            data = workspace.data(data_name)
            if data is None:
                raise AssertionError(f"data {data_name!r} not found")
            pdf_data_objs.append((pdf, data))

        self._apply_parameter_point(workspace, check["reference_point"])
        with suppress_root_output():
            nlls = [
                pdf.createNLL(data, self.ROOT.RooFit.NumCPU(1), self.ROOT.RooFit.EvalBackend("legacy"))
                for pdf, data in pdf_data_objs
            ]
            if len(nlls) == 1:
                combined_nll = nlls[0]
            else:
                arglist = self.ROOT.RooArgList()
                for nll in nlls:
                    arglist.add(nll)
                combined_nll = self.ROOT.RooAddition(
                    "hs3suite_combined_nll", "hs3suite combined NLL", arglist
                )
            reference = float(combined_nll.getVal())

        values = []
        scan_parameters = check["scan_parameters"]
        for point in check["scan_points"]:
            self._apply_parameter_point(workspace, check["reference_point"])
            for name, value in zip(scan_parameters, point, strict=True):
                var = workspace.var(name)
                if var is None:
                    raise AssertionError(f"scan parameter {name!r} not found")
                var.setVal(float(value))
            with suppress_root_output():
                values.append(2.0 * (float(combined_nll.getVal()) - reference))
        return values

    def _resolve_target_pairs(self, target: dict[str, Any], hs3_path: Path) -> list[tuple[str, str]]:
        if "likelihood" in target:
            payload = load_json(hs3_path)
            name = target["likelihood"]
            entry = next(
                (e for e in payload.get("likelihoods", []) if e.get("name") == name), None
            )
            if entry is None:
                raise AssertionError(f"likelihood {name!r} not found in {hs3_path}'s 'likelihoods' section")
            distributions = entry["distributions"]
            data = entry["data"]
            if len(distributions) != len(data):
                raise AssertionError(f"likelihood {name!r}: distributions/data length mismatch")
            return list(zip(distributions, data, strict=True))
        return [(target["pdf"], target["data"])]

    def _apply_parameter_point(self, workspace, values: dict[str, float]) -> None:
        for name, value in values.items():
            var = workspace.var(name)
            if var is not None:
                var.setVal(float(value))


@contextmanager
def suppress_root_output():
    """Suppress noisy C++ diagnostics that bypass RooMsgService."""

    sys.stdout.flush()
    sys.stderr.flush()
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    stdout_fd = os.dup(1)
    stderr_fd = os.dup(2)
    try:
        os.dup2(devnull_fd, 1)
        os.dup2(devnull_fd, 2)
        yield
    finally:
        os.dup2(stdout_fd, 1)
        os.dup2(stderr_fd, 2)
        os.close(stdout_fd)
        os.close(stderr_fd)
        os.close(devnull_fd)
