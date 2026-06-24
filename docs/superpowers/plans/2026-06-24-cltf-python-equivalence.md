# CLTF Python Equivalence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an independently installable Python `cltf` package that reproduces the verified R CLTF equations, validation, data services, calibration, and diagnostics.

**Architecture:** Implement focused Python modules under `python/src/cltf/`, using the renamed R package and shared fixtures as an external numerical contract. Build from mathematical primitives upward with test-driven development, then delete the legacy `pyclt/` implementation only after parity tests pass.

**Tech Stack:** Python 3.11+, NumPy, pandas, SciPy, matplotlib, requests, pytest, pyproject.toml

---

Every new or revised Python script and module must use the workspace-standard
header with `Last updated: 2026-06-24`.

## File Map

- Create `python/pyproject.toml`.
- Create `python/README.md`.
- Create `python/src/cltf/` modules.
- Create `python/tests/` unit and conformance tests.
- Create `python/tests/fixtures/` only for small primitive fixtures.
- Delete `pyclt/` after parity is established.
- Replace root Python requirement files after package installation is verified.

### Task 1: Scaffold the Python distribution

**Files:**
- Create: `python/pyproject.toml`
- Create: `python/src/cltf/__init__.py`
- Create: `python/tests/test_package.py`

- [ ] **Step 1: Write the failing import test**

```python
#!/usr/bin/env python3
"""
Script: test_package.py
Objective: Verify Python CLTF package metadata and public imports.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Installed editable Python package.
Outputs: Pytest assertions.
Usage: python -m pytest python/tests/test_package.py -q
Dependencies: pytest, cltf
"""

import cltf


def test_package_version() -> None:
    assert cltf.__version__ == "0.1.0"
```

- [ ] **Step 2: Verify the import fails**

```bash
python -m pytest python/tests/test_package.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'cltf'`.

- [ ] **Step 3: Create package metadata**

Create `python/README.md`:

```markdown
# Python CLTF package

Independent Python implementation of the Convective Lognormal Transfer
Function used by the repository examples and herbicide workbench.
```

Create `python/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=75", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "cltf"
version = "0.1.0"
description = "Convective Lognormal Transfer Function for herbicide dynamics"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "numpy>=1.26",
  "pandas>=2.1",
  "scipy>=1.11",
  "matplotlib>=3.8",
  "requests>=2.31"
]

[project.optional-dependencies]
excel = ["openpyxl>=3.1"]
geo = ["rasterio>=1.3"]
test = ["pytest>=8", "openpyxl>=3.1"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
```

Create `python/src/cltf/__init__.py` with the standard Python script header and:

```python
"""Public interface for the Python CLTF implementation."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Install and test**

```bash
python -m pip install -e 'python[test]'
python -m pytest python/tests/test_package.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add python
git commit -m "build: scaffold Python CLTF package"
```

### Task 2: Implement transport distributions and convolution

**Files:**
- Create: `python/src/cltf/transport.py`
- Create: `python/tests/test_transport.py`

- [ ] **Step 1: Write primitive and conservation tests**

```python
import numpy as np
from scipy.stats import lognorm

from cltf.transport import (
    CLTFLayer,
    cltf_cdf,
    cltf_layer_probabilities,
    cltf_pdf,
    cltf_two_layer_cdf,
)


def test_single_layer_matches_scipy_lognormal() -> None:
    layer = CLTFLayer(mu=1.0, sigma=0.5, retardation=2.0, thickness_mm=100.0)
    y = np.array([0.0, 50.0, 100.0, 200.0, 500.0])
    scale = layer.mu * layer.retardation * layer.thickness_mm

    np.testing.assert_allclose(
        cltf_pdf(y, layer),
        lognorm.pdf(y, s=layer.sigma, scale=scale),
    )
    np.testing.assert_allclose(
        cltf_cdf(y, layer),
        lognorm.cdf(y, s=layer.sigma, scale=scale),
    )


def test_two_layer_probabilities_conserve_mass() -> None:
    top = CLTFLayer(1.0, 0.5, 2.0, 100.0)
    bottom = CLTFLayer(1.2, 0.6, 3.0, 200.0)
    result = cltf_layer_probabilities(
        np.array([0.0, 25.0, 100.0, 500.0, 5000.0]),
        top,
        bottom,
    )

    assert np.all(result >= 0)
    np.testing.assert_allclose(result.sum(axis=1), 1.0, atol=1e-10)
    np.testing.assert_allclose(result[0], [1.0, 0.0, 0.0])


def test_adaptive_and_trapezoid_convolution_agree() -> None:
    top = CLTFLayer(1.0, 0.5, 2.0, 100.0)
    bottom = CLTFLayer(1.2, 0.6, 3.0, 200.0)
    y = np.array([25.0, 100.0, 250.0, 500.0, 1000.0])

    adaptive = cltf_two_layer_cdf(y, top, bottom, method="adaptive")
    trapezoid = cltf_two_layer_cdf(
        y,
        top,
        bottom,
        method="trapezoid",
        n_steps=20001,
    )
    np.testing.assert_allclose(trapezoid, adaptive, atol=2e-4)
```

- [ ] **Step 2: Run and verify failure**

```bash
python -m pytest python/tests/test_transport.py -q
```

Expected: FAIL because `cltf.transport` does not exist.

- [ ] **Step 3: Implement the transport API**

Create a frozen dataclass:

```python
@dataclass(frozen=True)
class CLTFLayer:
    mu: float
    sigma: float
    retardation: float
    thickness_mm: float

    def __post_init__(self) -> None:
        values = (self.mu, self.sigma, self.retardation, self.thickness_mm)
        if not all(math.isfinite(value) and value > 0 for value in values):
            raise ValueError("CLTF layer parameters must be finite and positive")

    @property
    def scale_mm(self) -> float:
        return self.mu * self.retardation * self.thickness_mm
```

Implement:

```python
def cltf_pdf(y_mm: ArrayLike, layer: CLTFLayer) -> np.ndarray
def cltf_cdf(y_mm: ArrayLike, layer: CLTFLayer) -> np.ndarray
def cltf_two_layer_cdf(
    y_mm: ArrayLike,
    top_layer: CLTFLayer,
    bottom_layer: CLTFLayer,
    method: Literal["adaptive", "trapezoid"] = "adaptive",
    n_steps: int = 5001,
    rel_tol: float = 1e-8,
) -> np.ndarray
def cltf_layer_probabilities(...) -> np.ndarray
```

Use `scipy.stats.lognorm` for single-layer functions. For adaptive convolution,
integrate in log-infiltration space with `scipy.integrate.quad`, matching
`R/R/cltf.R`. For trapezoid convolution use
`scipy.integrate.trapezoid`. Reject material negative probabilities or mass
errors instead of silently clipping them.

- [ ] **Step 4: Run tests**

```bash
python -m pytest python/tests/test_transport.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add python/src/cltf/transport.py python/tests/test_transport.py
git commit -m "feat: add Python CLTF transport core"
```

### Task 3: Implement concentration conversion and simulation

**Files:**
- Create: `python/src/cltf/concentration.py`
- Create: `python/src/cltf/simulation.py`
- Create: `python/tests/test_concentration.py`
- Create: `python/tests/test_simulation.py`

- [ ] **Step 1: Write conversion and mass-balance tests**

```python
import numpy as np

from cltf.concentration import (
    apply_elapsed_degradation,
    resident_concentration_ug_kg,
    soil_mass_kg_ha,
)


def test_concentration_arithmetic() -> None:
    soil_mass = soil_mass_kg_ha(0, 100, 1.3)
    assert soil_mass == 1.3e6
    assert resident_concentration_ug_kg(21.32, 1.0, soil_mass, 0.2) == 16.4


def test_elapsed_degradation_completes_mass_balance() -> None:
    probabilities = np.array([[0.4, 0.3, 0.3]])
    result = apply_elapsed_degradation(probabilities, np.array([100.0]), 0.01)
    np.testing.assert_allclose(result.sum(axis=1), 1.0, atol=1e-12)
```

```python
from cltf.simulation import simulate_cltf
from cltf.transport import CLTFLayer


def test_simulation_starts_in_top_layer() -> None:
    result = simulate_cltf(
        time_days=[0, 10],
        cumulative_infiltration_mm=[0, 0],
        top_layer=CLTFLayer(1.0, 0.5, 2.0, 100.0),
        bottom_layer=CLTFLayer(1.2, 0.6, 3.0, 200.0),
        decay_rate_day=0.01,
        application_rate_g_ha=21.32,
        top_bulk_density_g_cm3=1.3,
        bottom_bulk_density_g_cm3=1.4,
    )
    assert result.loc[0, "mass_top"] == 1
    np.testing.assert_allclose(
        result[
            ["mass_top", "mass_bottom", "mass_below", "mass_degraded"]
        ].sum(axis=1),
        1.0,
    )
```

- [ ] **Step 2: Run and verify missing modules**

```bash
python -m pytest \
  python/tests/test_concentration.py \
  python/tests/test_simulation.py -q
```

Expected: FAIL.

- [ ] **Step 3: Implement exact R-equivalent formulas**

Implement:

```python
def soil_mass_kg_ha(
    depth_top_mm: float,
    depth_bottom_mm: float,
    bulk_density_g_cm3: float,
) -> float

def apply_elapsed_degradation(
    layer_probabilities: ArrayLike,
    time_days: ArrayLike,
    decay_rate_day: float,
) -> np.ndarray

def resident_concentration_ug_kg(
    application_rate_g_ha: float,
    remaining_fraction: ArrayLike,
    soil_mass_kg_ha_value: float,
    effective_porosity: float = 0.2,
) -> np.ndarray

def simulate_cltf(...) -> pd.DataFrame
```

Use the exact R output columns:

```text
time_days
cumulative_infiltration_mm
mass_top
mass_bottom
mass_below
mass_degraded
concentration_top_ug_kg
concentration_bottom_ug_kg
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest \
  python/tests/test_concentration.py \
  python/tests/test_simulation.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add python/src/cltf/concentration.py python/src/cltf/simulation.py \
  python/tests/test_concentration.py python/tests/test_simulation.py
git commit -m "feat: add Python resident-concentration simulation"
```

### Task 4: Implement water balance and PET

**Files:**
- Create: `python/src/cltf/water_balance.py`
- Create: `python/src/cltf/climate.py`
- Create: `python/tests/test_water_balance.py`
- Create: `python/tests/test_climate.py`

- [ ] **Step 1: Write R-reference tests**

```python
def test_water_balance_and_first_passage() -> None:
    np.testing.assert_allclose(
        daily_infiltration([0, 10, 2], [3, 3, 3], [5, 0, 0]),
        [2, 7, 0],
    )
    np.testing.assert_allclose(
        first_passage_time([0, 5, 5, 5, 9], [0, 1, 2, 3, 4], [0, 5, 6, 9, 10]),
        [0, 1, 4, 4, np.nan],
        equal_nan=True,
    )


def test_pet_matches_r_reference() -> None:
    result = pet_from_temperature(
        jday=[164, 165, 166, 167, 168],
        tmax_c=[18.4, 19.2, 20.1, 17.8, 16.5],
        tmin_c=[7.1, 6.8, 8.0, 5.6, 4.9],
        latitude_deg=-32.85,
    )
    np.testing.assert_allclose(result, [1.2, 1.3, 1.3, 1.2, 1.1], atol=1e-6)
```

- [ ] **Step 2: Run and verify failure**

```bash
python -m pytest \
  python/tests/test_water_balance.py \
  python/tests/test_climate.py -q
```

Expected: FAIL.

- [ ] **Step 3: Translate the R helpers exactly**

Implement these public functions:

```python
daily_infiltration(...)
cumulative_infiltration(...)
first_passage_time(...)
pet_from_temperature(...)
```

Translate helper formulas and the 29-day temperature-range smoothing from
`R/R/climate.R`. Return PET in mm/day and preserve R rounding.

- [ ] **Step 4: Run tests and commit**

```bash
python -m pytest \
  python/tests/test_water_balance.py \
  python/tests/test_climate.py -q
git add python/src/cltf python/tests
git commit -m "feat: add Python climate and water balance"
```

### Task 5: Implement observation preparation

**Files:**
- Create: `python/src/cltf/observations.py`
- Create: `python/tests/test_observations.py`

- [ ] **Step 1: Write depth, non-detect, summary, and workbook tests**

```python
def test_depth_intervals_and_non_detects() -> None:
    assert depth_interval_mm("SA", "10cm") == (0.0, 100.0)
    assert depth_interval_mm("NSW", "30cm") == (150.0, 300.0)
    prepared = prepare_non_detects(
        concentration_ug_kg=[2, 0, 0],
        is_non_detect=[False, True, False],
        detection_limit_ug_kg=[np.nan, 0.2, np.nan],
    )
    np.testing.assert_allclose(
        prepared["analysis_concentration_ug_kg"],
        [2, 0.1, np.nan],
        equal_nan=True,
    )


def test_workbook_import_smoke() -> None:
    path = Path("/g/data/ym05/herbicide/context/Herbicide Dissipation 2024.xlsx")
    if not path.exists():
        pytest.skip("source workbook unavailable")
    result = read_herbicide_workbook(path, sheets=("SA", "NSW", "Qld"))
    assert len(result) == 1216
```

- [ ] **Step 2: Run and verify failure**

```bash
python -m pytest python/tests/test_observations.py -q
```

Expected: FAIL.

- [ ] **Step 3: Implement observation functions**

Implement:

```python
depth_interval_mm(...)
prepare_non_detects(...)
geometric_concentration(...)
read_herbicide_workbook(...)
infer_application_rate_g_ha(...)
```

Use pandas and `read_excel()`. Preserve the exact normalized R column names,
date handling, replicate grouping, zero exclusion, unit-status text, and sort
order.

- [ ] **Step 4: Run tests and commit**

```bash
python -m pytest python/tests/test_observations.py -q
git add python/src/cltf/observations.py python/tests/test_observations.py
git commit -m "feat: add Python observation preparation"
```

### Task 6: Implement SILO and SLGA cache services

**Files:**
- Create: `python/src/cltf/silo.py`
- Create: `python/src/cltf/slga.py`
- Create: `python/tests/test_silo.py`
- Create: `python/tests/test_slga.py`

- [ ] **Step 1: Write cache-first tests**

Use dependency injection for HTTP readers. Assert:

```python
def test_silo_cache_prevents_second_request(tmp_path: Path) -> None:
    calls = 0

    def downloader(url: str, destination: Path) -> None:
        nonlocal calls
        calls += 1
        shutil.copy("R/inst/extdata/sa_silo.csv", destination)

    first = fetch_silo_point(
        -32.831016,
        135.14494,
        "2024-06-12",
        "2024-06-13",
        tmp_path,
        username="test@example.org",
        password="testpassword",
        downloader=downloader,
    )
    second = fetch_silo_point(
        -32.831016,
        135.14494,
        "2024-06-12",
        "2024-06-13",
        tmp_path,
        downloader=lambda *_: pytest.fail("cache was not used"),
    )
    assert calls == 1
    pd.testing.assert_frame_equal(first, second)
```

For SLGA, assert standard bands, overlap weighting, manual override network
bypass, and that API keys are absent from normalized caches.

- [ ] **Step 2: Implement matching cache schemas**

Implement the R-equivalent public functions:

```python
round_silo_coordinate(...)
parse_silo_csv(...)
fetch_silo_point(...)
parse_slga_bulk_density(...)
weight_bulk_density(...)
fetch_slga_bulk_density(...)
```

Use `requests` for HTTP and optional `rasterio` for authenticated COG fallback.
Do not write credentials into URLs stored in metadata or into cache files.

- [ ] **Step 3: Run and commit**

```bash
python -m pytest python/tests/test_silo.py python/tests/test_slga.py -q
git add python/src/cltf/silo.py python/src/cltf/slga.py \
  python/tests/test_silo.py python/tests/test_slga.py
git commit -m "feat: add Python SILO and SLGA services"
```

### Task 7: Implement deterministic calibration and profiles

**Files:**
- Create: `python/src/cltf/calibration.py`
- Create: `python/tests/test_calibration.py`

- [ ] **Step 1: Port the synthetic recovery fixture**

Create the same truth, 12 forcing times, two layers, seed 42 perturbations,
bounds, and initial values used by `R/tests/testthat/test-calibration.R`.

Assert:

```python
assert np.isfinite(fit.objective)
assert fit.objective < initial_objective
assert set(fit.bound_hit) == {"mu", "sigma", "R_top", "R_bottom", "k"}
np.testing.assert_allclose(
    [
        fit.transport_scales["top"],
        fit.transport_scales["bottom"],
    ],
    [
        fit.parameters["mu"] * fit.parameters["R_top"],
        fit.parameters["mu"] * fit.parameters["R_bottom"],
    ],
)
assert "products" in fit.identifiability_note
```

- [ ] **Step 2: Implement calibration dataclasses and functions**

Create:

```python
@dataclass(frozen=True)
class CLTFFit:
    parameters: dict[str, float]
    objective: float
    convergence: int
    message: str
    start_index: int
    bound_hit: dict[str, bool]
    predictions: pd.DataFrame
    all_starts: pd.DataFrame
    lower: dict[str, float]
    upper: dict[str, float]
    starts: np.ndarray
    transport_scales: dict[str, float]
    identifiability_note: str
```

Implement:

```python
cltf_objective(...)
fit_cltf(...)
profile_cltf_parameter(...)
```

Use `scipy.optimize.minimize(method="L-BFGS-B")`, deterministic
`numpy.random.default_rng(seed)`, finite penalty `1e6`, and replicate-level
root mean squared log residuals.

- [ ] **Step 3: Run and commit**

```bash
python -m pytest python/tests/test_calibration.py -q
git add python/src/cltf/calibration.py python/tests/test_calibration.py
git commit -m "feat: add Python CLTF calibration"
```

### Task 8: Implement Python diagnostics and public exports

**Files:**
- Create: `python/src/cltf/plotting.py`
- Create: `python/tests/test_plotting.py`
- Modify: `python/src/cltf/__init__.py`

- [ ] **Step 1: Write Agg-backend smoke tests**

Test seven functions:

```text
plot_climate_forcing
plot_observed_fitted
plot_residuals
plot_mass_fractions
plot_mass_balance
plot_objective_profile
plot_bulk_density
```

Each test saves a PNG and asserts a non-zero file size.

- [ ] **Step 2: Implement plots**

Use matplotlib with:

```python
matplotlib.rcParams["font.family"] = ["Arial", "DejaVu Sans"]
```

Match R axis semantics, log concentration scales, replicate/geometric-mean
distinction, and colourblind-safe colours.

- [ ] **Step 3: Export the complete public API**

`python/src/cltf/__init__.py` must import and list in `__all__` every approved
public function and `CLTFLayer`/`CLTFFit`.

- [ ] **Step 4: Run and commit**

```bash
MPLBACKEND=Agg python -m pytest python/tests/test_plotting.py -q
git add python/src/cltf python/tests/test_plotting.py
git commit -m "feat: add Python CLTF diagnostics"
```

### Task 9: Add primitive cross-language conformance tests

**Files:**
- Create: `reference/tolerances.json`
- Create: `reference/primitives.json`
- Create: `python/tests/test_r_conformance.py`
- Create: `R/tests/testthat/test-shared-conformance.R`

- [ ] **Step 1: Create fixed language-neutral fixtures**

`reference/tolerances.json`:

```json
{
  "absolute": 1e-8,
  "relative": 1e-8,
  "trapezoid_absolute": 0.0002,
  "calibration_objective_absolute": 0.00001
}
```

`reference/primitives.json` contains fixed inputs and expected R outputs for:

- PET vector;
- daily and cumulative infiltration;
- first-passage targets;
- one-layer PDF/CDF;
- two-layer probabilities;
- concentration conversion;
- elapsed degradation.

- [ ] **Step 2: Add R and Python readers**

Both tests load the same JSON and compare native function outputs to expected
values using the declared tolerances.

- [ ] **Step 3: Run both suites**

```bash
Rscript -e 'testthat::test_local("R", filter = "shared-conformance")'
python -m pytest python/tests/test_r_conformance.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add reference R/tests/testthat/test-shared-conformance.R \
  python/tests/test_r_conformance.py
git commit -m "test: add cross-language CLTF conformance fixtures"
```

### Task 10: Remove the legacy Python implementation

**Files:**
- Delete: `pyclt/`
- Modify: root `requirements.txt`
- Modify: root `requirements-workbench.txt`
- Delete: incompatible legacy Python examples and outputs

- [ ] **Step 1: Prove no active import requires `pyclt`**

```bash
rg -n 'from pyclt|import pyclt|CLTParameters|TwoLayerCLT|run_series' \
  --glob '!docs/superpowers/**' .
```

Expected: matches are limited to the legacy app and examples scheduled for
replacement in later plans.

- [ ] **Step 2: Delete the legacy package**

```bash
git rm -r pyclt
```

Delete incompatible legacy Python examples and BCG01 outputs:

```bash
git rm examples/synthetic_demo.py examples/bcg01_demo.py \
  examples/generate_bcg01_climate.py \
  examples/data/bcg01_2019_climate.csv \
  examples/data/bcg01_results.csv \
  examples/data/bcg01_results.png
```

- [ ] **Step 3: Replace root requirements**

`requirements.txt`:

```text
-e ./python
```

`requirements-workbench.txt`:

```text
-e ./python
-r apps/herbicide_workbench/requirements.txt
```

- [ ] **Step 4: Run Python package tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider python/tests
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove legacy Python CLT implementation"
```

## Completion Gate

- `python/` installs as distribution and import package `cltf`.
- Numerical primitives match R fixtures within declared tolerances.
- Calibration is deterministic and exposes the scaling ridge.
- SILO and SLGA cache behaviour matches R without credential leakage.
- Diagnostic plots render under a non-interactive backend.
- No active `pyclt`, `CLTParameters`, `TwoLayerCLT`, or `run_series` code remains.
- The Python suite passes from a clean editable installation.
