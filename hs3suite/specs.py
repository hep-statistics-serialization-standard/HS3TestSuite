from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass(frozen=True, kw_only=True)
class ScanSpec:
    """Base for a check that evaluates something over a list of points.

    Subclasses differ only in *what* is evaluated, and each carries the wiring for its
    own check kind: ``kind`` names the runner implementation and the backend method
    (``run_<kind>``), ``target()`` builds the check's target dict, and ``tolerance()``
    supplies the default comparison tolerance.
    """

    parameters: tuple[str, ...]
    points: tuple[tuple[float, ...], ...]
    id: str = "scan"

    kind: ClassVar[str] = ""

    def __post_init__(self) -> None:
        if not self.parameters:
            raise ValueError(f"{type(self).__name__} {self.id!r}: parameters must be non-empty")
        for point in self.points:
            if len(point) != len(self.parameters):
                raise ValueError(
                    f"{type(self).__name__} {self.id!r}: point {point!r} has {len(point)} "
                    f"coords, expected {len(self.parameters)}"
                )

    def target(self) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def tolerance(cls) -> dict[str, float]:
        return {"rtol": 1e-8, "atol": 1e-7}


@dataclass(frozen=True, kw_only=True)
class NLLScanSpec(ScanSpec):
    """Scan 2*(NLL(point) - NLL(reference)). Needs data."""

    pdf: str | None = None
    data: str | None = None
    likelihood: str | None = None
    id: str = "twice_delta_nll_scan"

    kind: ClassVar[str] = "twice_delta_nll_scan"

    def __post_init__(self) -> None:
        super().__post_init__()
        has_pdf = self.pdf is not None
        has_data = self.data is not None
        if has_pdf != has_data:
            raise ValueError(
                f"NLLScanSpec {self.id!r}: pdf and data must both be set or both omitted"
            )
        has_pdf_data = has_pdf and has_data
        has_likelihood = self.likelihood is not None
        if has_pdf_data == has_likelihood:
            raise ValueError(
                f"NLLScanSpec {self.id!r}: specify exactly one of (pdf and data) or likelihood"
            )

    def target(self) -> dict[str, Any]:
        if self.likelihood is not None:
            return {"likelihood": self.likelihood}
        return {"pdf": self.pdf, "data": self.data}

    @classmethod
    def one_dim(
        cls,
        pdf: str,
        data: str,
        parameter: str,
        points: tuple[float, ...],
        id: str = "twice_delta_nll_scan",
    ) -> "NLLScanSpec":
        """Ergonomic constructor for the common single-parameter, single pdf+data scan."""
        return cls(
            parameters=(parameter,),
            points=tuple((p,) for p in points),
            pdf=pdf,
            data=data,
            id=id,
        )


@dataclass(frozen=True, kw_only=True)
class PdfScanSpec(ScanSpec):
    """Scan a pdf's density, normalised over ``observables``. Needs no data."""

    pdf: str | None = None
    observables: tuple[str, ...] | None = None
    id: str = "pdf_scan"

    kind: ClassVar[str] = "pdf_scan"

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.pdf:
            raise ValueError(f"PdfScanSpec {self.id!r}: pdf is required")
        if not self.observables:
            raise ValueError(f"PdfScanSpec {self.id!r}: observables must be non-empty")

    def target(self) -> dict[str, Any]:
        return {"pdf": self.pdf, "observables": list(self.observables)}

    @classmethod
    def tolerance(cls) -> dict[str, float]:
        # rtol-dominated: densities across a scan can span many orders of magnitude, so
        # the NLL scan's atol of 1e-7 would be far too slack.
        return {"rtol": 1e-8, "atol": 1e-12}

    @classmethod
    def one_dim(
        cls,
        pdf: str,
        observables: tuple[str, ...],
        parameter: str,
        points: tuple[float, ...],
        id: str = "pdf_scan",
    ) -> "PdfScanSpec":
        """Ergonomic constructor for the common single-parameter pdf scan."""
        return cls(
            parameters=(parameter,),
            points=tuple((p,) for p in points),
            pdf=pdf,
            observables=observables,
            id=id,
        )


@dataclass(frozen=True, kw_only=True)
class FunctionScanSpec(ScanSpec):
    """Scan a plain function value. Needs no data and no normalisation."""

    function: str | None = None
    id: str = "function_scan"

    kind: ClassVar[str] = "function_scan"

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.function:
            raise ValueError(f"FunctionScanSpec {self.id!r}: function is required")

    def target(self) -> dict[str, Any]:
        return {"function": self.function}

    @classmethod
    def tolerance(cls) -> dict[str, float]:
        return {"rtol": 1e-8, "atol": 1e-12}

    @classmethod
    def one_dim(
        cls,
        function: str,
        parameter: str,
        points: tuple[float, ...],
        id: str = "function_scan",
    ) -> "FunctionScanSpec":
        """Ergonomic constructor for the common single-parameter function scan."""
        return cls(
            parameters=(parameter,),
            points=tuple((p,) for p in points),
            function=function,
            id=id,
        )


@dataclass(frozen=True)
class FixtureSpec:
    test_id: str
    title: str
    source: str
    description: str
    nll_scans: tuple[NLLScanSpec, ...]
    reference_backend: str
    semantic: tuple[str, ...] = ()
    tags: tuple[str, ...] = ("roofit_tutorial",)
    conformance: tuple[str, ...] = ("basic",)
    modified_from_source: bool = False
    notes: tuple[str, ...] = ()
    backend_expectations: dict[str, dict[str, Any]] = field(default_factory=dict)
    pdf_scans: tuple[PdfScanSpec, ...] = ()
    function_scans: tuple[FunctionScanSpec, ...] = ()

    def __post_init__(self) -> None:
        ids = [check.id for check in self.all_scans()]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"FixtureSpec {self.test_id!r}: duplicate check ids {sorted(dupes)}")

    def all_scans(self) -> tuple[ScanSpec, ...]:
        """Every check-producing spec, in the order their checks are emitted."""
        return (*self.nll_scans, *self.pdf_scans, *self.function_scans)

FIXTURES: tuple[FixtureSpec, ...] = (
    FixtureSpec(
        "rf101_basics",
        "RooFit rf101 basic Gaussian",
        "ROOT RooFit tutorial rf101_basics.py",
        "Single Gaussian PDF with an unbinned toy dataset.",
        (NLLScanSpec.one_dim("gauss", "gaussData", "mean", (-1.0, 0.0, 1.0, 2.0, 3.0)),),
        "roofit 6.41.01",
        ("unbinned", "gaussian"),
    ),
    FixtureSpec(
        "rf103_interprfuncs",
        "RooFit rf103 interpreted functions",
        "ROOT RooFit tutorial rf103_interprfuncs.py",
        "Generic interpreted PDF plus a Gaussian with formula-driven mean.",
        (NLLScanSpec.one_dim("genpdf", "genpdfData", "alpha", (3.0, 4.0, 5.0, 6.0, 7.0)),),
        "roofit 6.41.01",
        ("unbinned", "generic_expression"),
    ),
    FixtureSpec(
        "rf110_normintegration",
        "RooFit rf110 normalization integration",
        "ROOT RooFit tutorial rf110_normintegration.py",
        "Gaussian with integral and CDF objects plus generated data for scans.",
        (NLLScanSpec.one_dim("gx", "gxData", "mean", (-4.0, -3.0, -2.0, -1.0, 0.0)),),
        "roofit 6.41.01",
        ("unbinned", "integral", "cdf"),
        modified_from_source=True,
        notes=("The original tutorial has no data; this fixture adds a toy dataset.",),
    ),
    FixtureSpec(
        "rf111_derivatives",
        "RooFit rf111 derivatives",
        "ROOT RooFit tutorial rf111_derivatives.py",
        "Gaussian with derivative functions and generated data for scans.",
        (NLLScanSpec.one_dim("gauss", "gaussData", "mean", (-1.0, 0.0, 1.0, 2.0, 3.0)),),
        "roofit 6.41.01",
        ("unbinned", "derivative"),
        modified_from_source=True,
        notes=("The original tutorial has no data; this fixture adds a toy dataset.",),
    ),
    FixtureSpec(
        "rf203_ranges",
        "RooFit rf203 ranges",
        "ROOT RooFit tutorial rf203_ranges.py",
        "Gaussian plus polynomial mixture with a named observable range.",
        (NLLScanSpec.one_dim("model", "modelData", "mx", (-1.0, -0.5, 0.0, 0.5, 1.0)),),
        "roofit 6.41.01",
        ("unbinned", "ranges", "mixture"),
    ),
    FixtureSpec(
        "rf207_comptools",
        "RooFit rf207 component tools",
        "ROOT RooFit tutorial rf207_comptools.py",
        "Composite signal/background model with customized component clone.",
        (NLLScanSpec.one_dim("model", "data", "bkgfrac", (0.2, 0.35, 0.5, 0.65, 0.8)),),
        "roofit 6.41.01",
        ("unbinned", "composition", "customizer"),
        modified_from_source=True,
        notes=("The original tutorial stored an empty dataset; this fixture samples the model.",),
    ),
    FixtureSpec(
        "rf208_convolution_fft3",
        "RooFit rf208 FFT convolution",
        "ROOT RooFit tutorial rf208_convolution_fft3.py",
        "Landau convolved with a Gaussian using RooFFTConvPdf.",
        (NLLScanSpec.one_dim("lxg", "lxgData", "ml", (3.0, 4.0, 5.0, 6.0, 7.0)),),
        "roofit 6.41.01",
        ("unbinned", "fft_convolution"),
    ),
    FixtureSpec(
        "rf209_anaconv",
        "RooFit rf209 analytical convolution",
        "ROOT RooFit tutorial rf209_anaconv.py",
        "Decay PDFs with truth and Gaussian resolution models.",
        (NLLScanSpec.one_dim("decay_gm1", "decay_gm1Data", "tau", (1.0, 1.3, 1.548, 1.8, 2.1)),),
        "roofit 6.41.01",
        ("unbinned", "analytical_convolution", "resolution_model"),
        modified_from_source=True,
        notes=(
            "The original tutorial has no data; this fixture adds a decay toy dataset.",
            "ROOT 6.41.01 exports invalid internal convolution names for this fixture.",
        ),
        backend_expectations={
            "roofit": {
                "xfail": True,
                "reason": "RooJSONFactoryWSTool import rejects invalid internal convolution names.",
            }
        },
    ),
    FixtureSpec(
        "rf210_angularconv",
        "RooFit rf210 angular convolution",
        "ROOT RooFit tutorial rf210_angularconv.py",
        "Angular FFT convolution in psi and cos(psi).",
        (NLLScanSpec.one_dim("Mf", "MfData", "gbias", (0.0, 0.1, 0.2, 0.3, 0.4)),),
        "roofit 6.41.01",
        ("unbinned", "fft_convolution", "generic_expression"),
    ),
    FixtureSpec(
        "rf301_composition",
        "RooFit rf301 composition",
        "ROOT RooFit tutorial rf301_composition.py",
        "Gaussian whose mean is a polynomial function of another observable.",
        (NLLScanSpec.one_dim("model", "modelData", "a0", (-1.5, -1.0, -0.5, 0.0, 0.5)),),
        "roofit 6.41.01",
        ("unbinned", "composition"),
    ),
    FixtureSpec(
        "rf302_utilfuncs",
        "RooFit rf302 utility functions",
        "ROOT RooFit tutorial rf302_utilfuncs.py",
        "Gaussian models using formula, polynomial, addition, and product functions.",
        (NLLScanSpec.one_dim("model_2", "model_2Data", "a0", (-2.5, -2.0, -1.5, -1.0, -0.5)),),
        "roofit 6.41.01",
        ("unbinned", "utility_functions"),
        modified_from_source=True,
        notes=("The original tutorial has no data; this fixture samples a representative model.",),
    ),
    FixtureSpec(
        "rf303_conditional",
        "RooFit rf303 conditional model",
        "ROOT RooFit tutorial rf303_conditional.py",
        "Conditional Gaussian model with generated data and external prototype data.",
        (NLLScanSpec.one_dim("model", "modelData", "a0", (-1.5, -1.0, -0.5, 0.0, 0.5)),),
        "roofit 6.41.01",
        ("unbinned", "conditional"),
    ),
    FixtureSpec(
        "rf304_uncorrprod",
        "RooFit rf304 uncorrelated product",
        "ROOT RooFit tutorial rf304_uncorrprod.py",
        "Two-dimensional product of independent Gaussian PDFs.",
        (NLLScanSpec.one_dim("gaussxy", "gaussxyData", "mean1", (0.0, 1.0, 2.0, 3.0, 4.0)),),
        "roofit 6.41.01",
        ("unbinned", "product_pdf"),
    ),
    FixtureSpec(
        "rf305_condcorrprod",
        "RooFit rf305 conditional correlated product",
        "ROOT RooFit tutorial rf305_condcorrprod.py",
        "Conditional product model with y-dependent Gaussian mean.",
        (NLLScanSpec.one_dim("model", "modelData", "a0", (-1.5, -1.0, -0.5, 0.0, 0.5)),),
        "roofit 6.41.01",
        ("unbinned", "conditional", "product_pdf"),
    ),
    FixtureSpec(
        "rf308_normintegration2d",
        "RooFit rf308 two-dimensional integration",
        "ROOT RooFit tutorial rf308_normintegration2d.py",
        "Two-dimensional Gaussian product with integral and CDF objects plus data.",
        (NLLScanSpec.one_dim("gxy", "gxyData", "meanx", (-4.0, -3.0, -2.0, -1.0, 0.0)),),
        "roofit 6.41.01",
        ("unbinned", "integral", "cdf", "product_pdf"),
        modified_from_source=True,
        notes=("The original tutorial has no data; this fixture adds a toy dataset.",),
    ),
    FixtureSpec(
        "rf309_ndimplot",
        "RooFit rf309 N-dimensional plotting model",
        "ROOT RooFit tutorial rf309_ndimplot.py",
        "Two- and three-dimensional composed Gaussian models with toy data.",
        (NLLScanSpec.one_dim("model", "modelData", "a0", (-5.0, -4.0, -3.5, -3.0, -2.0)),),
        "roofit 6.41.01",
        ("unbinned", "multidimensional", "generic_expression"),
    ),
    FixtureSpec(
        "rf311_rangeplot",
        "RooFit rf311 range plotting model",
        "ROOT RooFit tutorial rf311_rangeplot.py",
        "Three-dimensional signal/background mixture with named ranges.",
        (NLLScanSpec.one_dim("model", "modelData", "fsig", (0.0, 0.05, 0.1, 0.2, 0.3)),),
        "roofit 6.41.01",
        ("unbinned", "ranges", "mixture", "multidimensional"),
    ),
    FixtureSpec(
        "rf313_paramranges",
        "RooFit rf313 parameterized ranges",
        "ROOT RooFit tutorial rf313_paramranges.py",
        "Three-dimensional product polynomial model with parameterized ranges and generated data.",
        (NLLScanSpec.one_dim("pxyz", "pxyzData", "z0", (-0.05, 0.0, 0.1, 0.2, 0.35)),),
        "roofit 6.41.01",
        ("unbinned", "parameterized_ranges", "product_pdf"),
        modified_from_source=True,
        notes=(
            "The original tutorial has no data; this fixture adds a toy dataset.",
            "The parameterized-range integral is not stored because ROOT 6.41.01 segfaults on import.",
        ),
    ),
    FixtureSpec(
        "rf703_effpdfprod",
        "RooFit rf703 efficiency product PDF",
        "ROOT RooFit tutorial rf703_effpdfprod.py",
        "Exponential model multiplied by an efficiency turn-on function.",
        (NLLScanSpec.one_dim("modelEff", "modelEffData", "tau", (-2.0, -1.75, -1.54, -1.2, -0.9)),),
        "roofit 6.41.01",
        ("unbinned", "efficiency_product"),
    ),
)


SPEC_BY_ID = {spec.test_id: spec for spec in FIXTURES}
