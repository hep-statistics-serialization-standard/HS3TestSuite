from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScanSpec:
    parameters: tuple[str, ...]
    points: tuple[tuple[float, ...], ...]
    pdf: str | None = None
    data: str | None = None
    likelihood: str | None = None
    id: str = "twice_delta_nll_scan"

    def __post_init__(self) -> None:
        has_pdf = self.pdf is not None
        has_data = self.data is not None
        if has_pdf != has_data:
            raise ValueError(f"ScanSpec {self.id!r}: pdf and data must both be set or both omitted")
        has_pdf_data = has_pdf and has_data
        has_likelihood = self.likelihood is not None
        if has_pdf_data == has_likelihood:
            raise ValueError(
                f"ScanSpec {self.id!r}: specify exactly one of (pdf and data) or likelihood"
            )
        if not self.parameters:
            raise ValueError(f"ScanSpec {self.id!r}: parameters must be non-empty")
        for point in self.points:
            if len(point) != len(self.parameters):
                raise ValueError(
                    f"ScanSpec {self.id!r}: point {point!r} has {len(point)} coords, "
                    f"expected {len(self.parameters)}"
                )

    @classmethod
    def one_dim(
        cls,
        pdf: str,
        data: str,
        parameter: str,
        points: tuple[float, ...],
        id: str = "twice_delta_nll_scan",
    ) -> "ScanSpec":
        """Ergonomic constructor for the common single-parameter, single pdf+data scan."""
        return cls(
            parameters=(parameter,),
            points=tuple((p,) for p in points),
            pdf=pdf,
            data=data,
            id=id,
        )


@dataclass(frozen=True)
class FixtureSpec:
    test_id: str
    title: str
    source: str
    description: str
    scans: tuple[ScanSpec, ...]
    reference_backend: str
    semantic: tuple[str, ...] = ()
    tags: tuple[str, ...] = ("roofit_tutorial",)
    conformance: tuple[str, ...] = ("basic",)
    modified_from_source: bool = False
    notes: tuple[str, ...] = ()
    backend_expectations: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        ids = [scan.id for scan in self.scans]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"FixtureSpec {self.test_id!r}: duplicate scan ids {sorted(dupes)}")

FIXTURES: tuple[FixtureSpec, ...] = (
    FixtureSpec(
        "rf101_basics",
        "RooFit rf101 basic Gaussian",
        "ROOT RooFit tutorial rf101_basics.py",
        "Single Gaussian PDF with an unbinned toy dataset.",
        (ScanSpec.one_dim("gauss", "gaussData", "mean", (-1.0, 0.0, 1.0, 2.0, 3.0)),),
        "roofit 6.41.01",
        ("unbinned", "gaussian"),
    ),
    FixtureSpec(
        "rf103_interprfuncs",
        "RooFit rf103 interpreted functions",
        "ROOT RooFit tutorial rf103_interprfuncs.py",
        "Generic interpreted PDF plus a Gaussian with formula-driven mean.",
        (ScanSpec.one_dim("genpdf", "genpdfData", "alpha", (3.0, 4.0, 5.0, 6.0, 7.0)),),
        "roofit 6.41.01",
        ("unbinned", "generic_expression"),
    ),
    FixtureSpec(
        "rf110_normintegration",
        "RooFit rf110 normalization integration",
        "ROOT RooFit tutorial rf110_normintegration.py",
        "Gaussian with integral and CDF objects plus generated data for scans.",
        (ScanSpec.one_dim("gx", "gxData", "mean", (-4.0, -3.0, -2.0, -1.0, 0.0)),),
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
        (ScanSpec.one_dim("gauss", "gaussData", "mean", (-1.0, 0.0, 1.0, 2.0, 3.0)),),
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
        (ScanSpec.one_dim("model", "modelData", "mx", (-1.0, -0.5, 0.0, 0.5, 1.0)),),
        "roofit 6.41.01",
        ("unbinned", "ranges", "mixture"),
    ),
    FixtureSpec(
        "rf207_comptools",
        "RooFit rf207 component tools",
        "ROOT RooFit tutorial rf207_comptools.py",
        "Composite signal/background model with customized component clone.",
        (ScanSpec.one_dim("model", "data", "bkgfrac", (0.2, 0.35, 0.5, 0.65, 0.8)),),
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
        (ScanSpec.one_dim("lxg", "lxgData", "ml", (3.0, 4.0, 5.0, 6.0, 7.0)),),
        "roofit 6.41.01",
        ("unbinned", "fft_convolution"),
    ),
    FixtureSpec(
        "rf209_anaconv",
        "RooFit rf209 analytical convolution",
        "ROOT RooFit tutorial rf209_anaconv.py",
        "Decay PDFs with truth and Gaussian resolution models.",
        (ScanSpec.one_dim("decay_gm1", "decay_gm1Data", "tau", (1.0, 1.3, 1.548, 1.8, 2.1)),),
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
        (ScanSpec.one_dim("Mf", "MfData", "gbias", (0.0, 0.1, 0.2, 0.3, 0.4)),),
        "roofit 6.41.01",
        ("unbinned", "fft_convolution", "generic_expression"),
    ),
    FixtureSpec(
        "rf301_composition",
        "RooFit rf301 composition",
        "ROOT RooFit tutorial rf301_composition.py",
        "Gaussian whose mean is a polynomial function of another observable.",
        (ScanSpec.one_dim("model", "modelData", "a0", (-1.5, -1.0, -0.5, 0.0, 0.5)),),
        "roofit 6.41.01",
        ("unbinned", "composition"),
    ),
    FixtureSpec(
        "rf302_utilfuncs",
        "RooFit rf302 utility functions",
        "ROOT RooFit tutorial rf302_utilfuncs.py",
        "Gaussian models using formula, polynomial, addition, and product functions.",
        (ScanSpec.one_dim("model_2", "model_2Data", "a0", (-2.5, -2.0, -1.5, -1.0, -0.5)),),
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
        (ScanSpec.one_dim("model", "modelData", "a0", (-1.5, -1.0, -0.5, 0.0, 0.5)),),
        "roofit 6.41.01",
        ("unbinned", "conditional"),
    ),
    FixtureSpec(
        "rf304_uncorrprod",
        "RooFit rf304 uncorrelated product",
        "ROOT RooFit tutorial rf304_uncorrprod.py",
        "Two-dimensional product of independent Gaussian PDFs.",
        (ScanSpec.one_dim("gaussxy", "gaussxyData", "mean1", (0.0, 1.0, 2.0, 3.0, 4.0)),),
        "roofit 6.41.01",
        ("unbinned", "product_pdf"),
    ),
    FixtureSpec(
        "rf305_condcorrprod",
        "RooFit rf305 conditional correlated product",
        "ROOT RooFit tutorial rf305_condcorrprod.py",
        "Conditional product model with y-dependent Gaussian mean.",
        (ScanSpec.one_dim("model", "modelData", "a0", (-1.5, -1.0, -0.5, 0.0, 0.5)),),
        "roofit 6.41.01",
        ("unbinned", "conditional", "product_pdf"),
    ),
    FixtureSpec(
        "rf308_normintegration2d",
        "RooFit rf308 two-dimensional integration",
        "ROOT RooFit tutorial rf308_normintegration2d.py",
        "Two-dimensional Gaussian product with integral and CDF objects plus data.",
        (ScanSpec.one_dim("gxy", "gxyData", "meanx", (-4.0, -3.0, -2.0, -1.0, 0.0)),),
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
        (ScanSpec.one_dim("model", "modelData", "a0", (-5.0, -4.0, -3.5, -3.0, -2.0)),),
        "roofit 6.41.01",
        ("unbinned", "multidimensional", "generic_expression"),
    ),
    FixtureSpec(
        "rf311_rangeplot",
        "RooFit rf311 range plotting model",
        "ROOT RooFit tutorial rf311_rangeplot.py",
        "Three-dimensional signal/background mixture with named ranges.",
        (ScanSpec.one_dim("model", "modelData", "fsig", (0.0, 0.05, 0.1, 0.2, 0.3)),),
        "roofit 6.41.01",
        ("unbinned", "ranges", "mixture", "multidimensional"),
    ),
    FixtureSpec(
        "rf313_paramranges",
        "RooFit rf313 parameterized ranges",
        "ROOT RooFit tutorial rf313_paramranges.py",
        "Three-dimensional product polynomial model with parameterized ranges and generated data.",
        (ScanSpec.one_dim("pxyz", "pxyzData", "z0", (-0.05, 0.0, 0.1, 0.2, 0.35)),),
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
        (ScanSpec.one_dim("modelEff", "modelEffData", "tau", (-2.0, -1.75, -1.54, -1.2, -0.9)),),
        "roofit 6.41.01",
        ("unbinned", "efficiency_product"),
    ),
)


SPEC_BY_ID = {spec.test_id: spec for spec in FIXTURES}
