from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np


class PyHS3Backend:
    name = "pyhs3"

    def __init__(self) -> None:
        os.environ.setdefault("PYTENSOR_FLAGS", "base_compiledir=/tmp/hs3suite_pytensor")
        Path("/tmp/hs3suite_pytensor").mkdir(parents=True, exist_ok=True)

        try:
            import pyhs3  # type: ignore
            from pyhs3.compile import function  # type: ignore
            from pyhs3.likelihoods import Likelihood  # type: ignore
            from pytensor.graph.traversal import explicit_graph_inputs  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "pyhs3 backend requires the local pyhs3 environment. "
                "Run with: mamba run -n pyhs3 python -m hs3suite run --backend pyhs3"
            ) from exc

        self.pyhs3 = pyhs3
        self.Likelihood = Likelihood
        self.function = function
        self.explicit_graph_inputs = explicit_graph_inputs
        self.mode = "FAST_COMPILE"

    def load_workspace(self, path: Path):
        return self.pyhs3.Workspace.load(path, suppress_traceback=False)

    def structure(self, workspace) -> dict[str, list[str]]:
        return {
            "pdfs": _names(workspace.distributions),
            "functions": _names(workspace.functions),
            "data": _names(workspace.data),
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
        # hs3_path is unused here (pyhs3.Workspace already parses "likelihoods" natively)
        # but accepted for signature parity with RooFitBackend.
        target = check["target"]
        likelihood = self._resolve_likelihood(workspace, target)
        model = workspace.model(likelihood, progress=False, mode=self.mode)
        twice_nll = -2 * model.log_prob
        inputs = [
            variable
            for variable in self.explicit_graph_inputs([twice_nll])
            if variable.name is not None
        ]
        evaluator = self.function(
            inputs=inputs,
            outputs=twice_nll,
            mode=self.mode,
            on_unused_input="ignore",
            trust_input=True,
        )

        base_values = self._base_values(model, check, inputs)
        reference = _as_scalar(evaluator(*_ordered_values(inputs, base_values)))

        values: list[float] = []
        scan_parameters = check["scan_parameters"]
        for point in check["scan_points"]:
            scan_values = dict(base_values)
            scan_values.update(zip(scan_parameters, point, strict=True))
            value = _as_scalar(evaluator(*_ordered_values(inputs, scan_values)))
            values.append(value - reference)
        return values

    def _resolve_likelihood(self, workspace, target: dict[str, Any]):
        if "likelihood" in target:
            return _get_named(workspace.likelihoods, target["likelihood"], "likelihood")
        distribution = _get_named(workspace.distributions, target["pdf"], "distribution")
        data = _get_named(workspace.data, target["data"], "data")
        return self.Likelihood(
            name=f"hs3suite_{target['pdf']}_{target['data']}",
            distributions=[distribution],
            data=[data],
        )

    def _base_values(self, model, check: dict[str, Any], inputs: list[Any]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        values.update(model.free_params)
        values.update(check["reference_point"])
        values.update(model.data)

        for variable in inputs:
            name = variable.name
            if name not in values:
                literal = _numeric_literal(name)
                if literal is not None:
                    values[name] = literal

        missing = [variable.name for variable in inputs if variable.name not in values]
        if missing:
            raise AssertionError(f"missing pyhs3 graph inputs: {missing}")
        return values


def _names(collection) -> list[str]:
    if collection is None:
        return []
    return sorted(item.name for item in collection)


def _get_named(collection, name: str, label: str):
    if collection is None:
        raise AssertionError(f"{label} {name!r} not found")
    item = collection.get(name)
    if item is None:
        raise AssertionError(f"{label} {name!r} not found")
    return item


def _numeric_literal(name: str | None) -> float | None:
    if name is None:
        return None
    try:
        return float(name)
    except ValueError:
        return None


def _ordered_values(inputs: list[Any], values: dict[str, Any]) -> list[np.ndarray]:
    return [np.asarray(values[variable.name], dtype=np.float64) for variable in inputs]


def _as_scalar(value: Any) -> float:
    return float(np.asarray(value).reshape(-1)[0])
