# CLTF Web Application and Repository Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy relative-concentration Streamlit application with the Python CLTF model, add site mapping and residue-assessment workflows, complete the naming audit and branding, then rename the GitHub repository and local checkout.

**Architecture:** The app imports the installed Python `cltf` package directly and uses a small internal site registry plus cache-first service layer. Observation CSV is the only upload; site, climate, soil, application-rate inference, model execution, assessment summaries, maps, plots, and exports are separate testable modules. Repository and checkout renaming occur only after all scientific and UI verification passes.

**Tech Stack:** Streamlit, pydeck, pandas, matplotlib, Python `cltf`, pytest, GitHub CLI

---

Every new or revised Python script and module must use the workspace-standard
header with `Last updated: 2026-06-24`.

## File Map

- Delete `apps/herbicide_workbench/workbench/adapters.py`.
- Replace `workbench/contracts.py`, `validation.py`, `plots.py`, and `exports.py`.
- Create `site_registry.py`, `data_services.py`, `assessment.py`, and `maps.py`.
- Replace `apps/herbicide_workbench/app.py`.
- Replace legacy sample data with links/readers for `examples/data/`.
- Replace tests under `apps/herbicide_workbench/tests/`.
- Replace Python-specific logo and repository branding.
- Rename remote repository and local checkout last.

### Task 1: Replace app contracts and remove the adapter boundary

**Files:**
- Delete: `apps/herbicide_workbench/workbench/adapters.py`
- Modify: `apps/herbicide_workbench/workbench/contracts.py`
- Modify: `apps/herbicide_workbench/workbench/config.py`
- Modify: `apps/herbicide_workbench/workbench/__init__.py`
- Delete: `apps/herbicide_workbench/tests/test_adapter.py`
- Create: `apps/herbicide_workbench/tests/test_contracts.py`
- Replace: `apps/herbicide_workbench/tests/test_config.py`

- [ ] **Step 1: Write new contract tests**

```python
from workbench.contracts import (
    AssessmentResult,
    CaseSelection,
    ExternalInputs,
    PreparedInputs,
    RunResult,
)


def test_case_selection_contains_site_soil_and_herbicide() -> None:
    case = CaseSelection("NSW_Griffith", "Heavy", "Imazapic")
    assert case.site_id == "NSW_Griffith"


def test_config_points_to_python_src() -> None:
    from workbench.config import CLTF_SRC, REPO_ROOT

    assert CLTF_SRC == REPO_ROOT / "python" / "src"
    assert (CLTF_SRC / "cltf" / "__init__.py").exists()
```

- [ ] **Step 2: Run and verify failure**

```bash
python -m pytest \
  apps/herbicide_workbench/tests/test_contracts.py \
  apps/herbicide_workbench/tests/test_config.py -q
```

Expected: FAIL because new contracts and `CLTF_SRC` do not exist.

- [ ] **Step 3: Define app contracts**

`contracts.py`:

```python
@dataclass(frozen=True)
class CaseSelection:
    site_id: str
    soil_group: str
    herbicide: str


@dataclass(frozen=True)
class ExternalInputs:
    forcing: pd.DataFrame
    bulk_density: pd.DataFrame
    top_bulk_density_g_cm3: float
    bottom_bulk_density_g_cm3: float
    warnings: list[str]
    metadata: dict[str, object]


@dataclass(frozen=True)
class PreparedInputs:
    case: CaseSelection
    site: dict[str, object]
    observations: pd.DataFrame
    forcing: pd.DataFrame
    bulk_density: pd.DataFrame
    application_date: pd.Timestamp
    application_rate_g_ha: float
    top_bulk_density_g_cm3: float
    bottom_bulk_density_g_cm3: float


@dataclass(frozen=True)
class AssessmentResult:
    date: pd.Timestamp
    time_days: int
    concentration_top_ug_kg: float
    concentration_bottom_ug_kg: float
    resident_profile_fraction: float


@dataclass
class RunResult:
    parameters: dict[str, float]
    predictions: pd.DataFrame
    fit: CLTFFit | None
    assessment: AssessmentResult
    warnings: list[str]
    metadata: dict[str, object]
```

`config.py`:

```python
REPO_ROOT = Path(__file__).resolve().parents[3]
CLTF_SRC = REPO_ROOT / "python" / "src"


def ensure_cltf_path() -> None:
    if not (CLTF_SRC / "cltf" / "__init__.py").exists():
        raise FileNotFoundError(f"Python CLTF source was not found at {CLTF_SRC}")
    if str(CLTF_SRC) not in sys.path:
        sys.path.insert(0, str(CLTF_SRC))
```

- [ ] **Step 4: Delete the legacy adapter**

```bash
git rm apps/herbicide_workbench/workbench/adapters.py
git rm apps/herbicide_workbench/tests/test_adapter.py
```

The app will call `simulate_cltf()` and `fit_cltf()` directly.

- [ ] **Step 5: Run and commit**

```bash
python -m pytest \
  apps/herbicide_workbench/tests/test_contracts.py \
  apps/herbicide_workbench/tests/test_config.py -q
git add apps/herbicide_workbench
git commit -m "refactor: replace legacy app model adapter"
```

### Task 2: Add the two-site registry

**Files:**
- Create: `apps/herbicide_workbench/workbench/site_registry.py`
- Create: `apps/herbicide_workbench/tests/test_site_registry.py`

- [ ] **Step 1: Write registry tests**

```python
def test_default_showcase_is_nsw_griffith() -> None:
    registry = load_site_registry()
    default = default_case(registry)
    assert default == CaseSelection("NSW_Griffith", "Heavy", "Imazapic")


def test_registry_exposes_site_geometry() -> None:
    site = get_site("SA_Minnipa")
    assert site["latitude"] == -32.831016
    assert site["top_depth_mm"] == 100
```

- [ ] **Step 2: Implement registry readers**

Read `examples/data/sites.json` and case directories. Export:

```python
load_site_registry() -> list[dict[str, object]]
get_site(site_id: str) -> dict[str, object]
available_soils(site_id: str) -> list[str]
available_herbicides(site_id: str, soil_group: str) -> list[str]
default_case(...) -> CaseSelection
case_input_dir(case: CaseSelection) -> Path
```

- [ ] **Step 3: Run and commit**

```bash
python -m pytest apps/herbicide_workbench/tests/test_site_registry.py -q
git add apps/herbicide_workbench
git commit -m "feat: add CLTF app site registry"
```

### Task 3: Replace observation validation with the shared resident-concentration schema

**Files:**
- Replace: `apps/herbicide_workbench/workbench/validation.py`
- Replace: `apps/herbicide_workbench/tests/test_validation.py`

- [ ] **Step 1: Write valid and invalid schema tests**

```python
def test_observation_csv_is_the_only_uploaded_table() -> None:
    raw = pd.DataFrame(
        {
            "sample_date": ["2024-04-26", "2024-05-06"],
            "depth_top_mm": [0, 0],
            "depth_bottom_mm": [150, 150],
            "concentration_ug_kg": [10.9, 5.1],
            "is_t0": [True, False],
        }
    )
    prepared = prepare_uploaded_observations(raw, get_site("NSW_Griffith"))
    assert "analysis_concentration_ug_kg" in prepared.columns
    assert prepared["days_since_application"].tolist() == [0, 10]


def test_relative_concentration_schema_is_rejected() -> None:
    raw = pd.DataFrame({"relative_concentration": [1.0]})
    with pytest.raises(ValidationError, match="concentration_ug_kg"):
        prepare_uploaded_observations(raw, get_site("NSW_Griffith"))
```

- [ ] **Step 2: Implement validation**

Required input columns:

```text
sample_date
depth_top_mm
depth_bottom_mm
concentration_ug_kg
```

Require either `application_date` or `is_t0`/`timepoint`. Optional:

```text
replicate_id
is_non_detect
detection_limit_ug_kg
site_id
soil_group
herbicide
```

Call Python `cltf.prepare_non_detects()` and validate intervals match the
selected site. Reject legacy `depth_mm`, `relative_concentration`, and
`concentration` aliases with a clear migration message.

- [ ] **Step 3: Run and commit**

```bash
python -m pytest apps/herbicide_workbench/tests/test_validation.py -q
git add apps/herbicide_workbench
git commit -m "feat: validate CLTF observation uploads"
```

### Task 4: Add cache-first climate and soil preparation

**Files:**
- Create: `apps/herbicide_workbench/workbench/data_services.py`
- Create: `apps/herbicide_workbench/tests/test_data_services.py`

- [ ] **Step 1: Write cached and live-path tests**

```python
def test_showcase_uses_committed_cache_without_credentials() -> None:
    result = prepare_external_inputs(
        CaseSelection("NSW_Griffith", "Heavy", "Imazapic"),
        environment={},
    )
    assert len(result.forcing) == 147
    assert len(result.bulk_density) == 3
    assert result.metadata["climate_source"] == "committed_cache"


def test_api_failure_falls_back_to_cache(monkeypatch) -> None:
    monkeypatch.setattr(
        "cltf.silo.fetch_silo_point",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    result = prepare_external_inputs(
        CaseSelection("SA_Minnipa", "Heavy", "Imazapic"),
        environment={"SILO_USERNAME": "x", "SILO_PASSWORD": "y"},
    )
    assert "fallback" in result.warnings[0].lower()
```

- [ ] **Step 2: Implement service orchestration**

`prepare_external_inputs() -> ExternalInputs`:

1. Resolve selected case and dates.
2. Prefer a live SILO request only when credentials exist and refresh is
   requested.
3. Otherwise parse the committed shared SILO file.
4. Prefer live SLGA only when `TERN_API_KEY` exists and refresh is requested.
5. Otherwise parse committed case bulk density.
6. Calculate PET, daily infiltration, cumulative infiltration, and
   depth-weighted model-layer density.
7. Return source metadata and explicit fallback warnings.

- [ ] **Step 3: Run and commit**

```bash
python -m pytest apps/herbicide_workbench/tests/test_data_services.py -q
git add apps/herbicide_workbench
git commit -m "feat: add app climate and soil services"
```

### Task 5: Add residue assessment logic

**Files:**
- Create: `apps/herbicide_workbench/workbench/assessment.py`
- Create: `apps/herbicide_workbench/tests/test_assessment.py`

- [ ] **Step 1: Write date-control tests**

```python
def test_default_assessment_is_90_days_after_application() -> None:
    application = pd.Timestamp("2024-04-26")
    available = pd.date_range(application, "2024-09-19")
    assert default_assessment_date(application, available) == pd.Timestamp(
        "2024-07-25"
    )


def test_assessment_cannot_exceed_observed_forcing() -> None:
    with pytest.raises(ValueError, match="observed climate"):
        validate_assessment_date(
            pd.Timestamp("2025-06-01"),
            pd.Timestamp("2024-04-26"),
            pd.Timestamp("2024-09-19"),
        )


def test_assessment_summary_selects_exact_prediction_row() -> None:
    result = summarize_assessment(predictions, pd.Timestamp("2024-07-25"))
    assert result.time_days == 90
```

- [ ] **Step 2: Implement**

Export:

```python
default_assessment_date(application_date, available_dates)
assessment_date_from_preset(application_date, days, final_date)
validate_assessment_date(date, application_date, final_date)
summarize_assessment(predictions, date)
```

`resident_profile_fraction` is:

```python
mass_top + mass_bottom
```

- [ ] **Step 3: Run and commit**

```bash
python -m pytest apps/herbicide_workbench/tests/test_assessment.py -q
git add apps/herbicide_workbench
git commit -m "feat: add residue assessment date logic"
```

### Task 6: Add interactive site maps

**Files:**
- Create: `apps/herbicide_workbench/workbench/maps.py`
- Create: `apps/herbicide_workbench/tests/test_maps.py`
- Modify: `apps/herbicide_workbench/requirements.txt`

- [ ] **Step 1: Write satellite and fallback tests**

```python
def test_map_uses_satellite_style_when_token_exists() -> None:
    deck = build_site_map(get_site("NSW_Griffith"), mapbox_token="token")
    assert deck.map_style == "mapbox://styles/mapbox/satellite-streets-v12"


def test_map_uses_attributed_fallback_without_token() -> None:
    deck = build_site_map(get_site("SA_Minnipa"), mapbox_token="")
    assert deck.map_style != "mapbox://styles/mapbox/satellite-streets-v12"
    assert len(deck.layers) >= 2
```

- [ ] **Step 2: Implement map builder**

Use `pydeck.Deck` with:

- site marker;
- SILO grid marker in a distinct colour;
- initial zoom 12;
- site tooltip;
- Mapbox satellite streets when `MAPBOX_API_KEY` exists;
- Carto Positron fallback otherwise.

Add `pydeck>=0.9` explicitly to app requirements.

- [ ] **Step 3: Run and commit**

```bash
python -m pytest apps/herbicide_workbench/tests/test_maps.py -q
git add apps/herbicide_workbench
git commit -m "feat: add interactive CLTF site map"
```

### Task 7: Replace plots with CLTF diagnostics and assessment markers

**Files:**
- Replace: `apps/herbicide_workbench/workbench/plots.py`
- Create/replace: plot tests

- [ ] **Step 1: Write plot tests**

For each figure assert a vertical line at assessment day 90:

```python
figure = plot_observed_fitted(observations, predictions, assessment_day=90)
assessment_lines = [
    line for axis in figure.axes for line in axis.lines
    if line.get_label() == "Residue assessment"
]
assert assessment_lines
assert assessment_lines[0].get_xdata()[0] == 90
```

Test:

```text
plot_climate_forcing
plot_observed_fitted
plot_residuals
plot_mass_fractions
plot_mass_balance
plot_objective_profiles
plot_bulk_density
```

- [ ] **Step 2: Implement app plot wrappers**

Use Python `cltf.plotting` as the base and add the assessment marker through a
shared helper:

```python
def add_assessment_line(axis, assessment_value, x_is_date=False):
    axis.axvline(
        assessment_value,
        color="#7A0177",
        linestyle="--",
        linewidth=1.8,
        label="Residue assessment",
    )
```

- [ ] **Step 3: Run and commit**

```bash
MPLBACKEND=Agg python -m pytest \
  apps/herbicide_workbench/tests/test_plots.py -q
git add apps/herbicide_workbench
git commit -m "feat: add CLTF app diagnostics"
```

### Task 8: Replace run orchestration and exports

**Files:**
- Create: `apps/herbicide_workbench/workbench/model_service.py`
- Replace: `apps/herbicide_workbench/workbench/exports.py`
- Replace: `apps/herbicide_workbench/tests/test_exports.py`
- Create: `apps/herbicide_workbench/tests/test_model_service.py`

- [ ] **Step 1: Write service and export tests**

```python
def test_fit_uses_replicate_log_objective() -> None:
    result = fit_case(prepared_inputs, default_parameters())
    assert result.fit is not None
    assert result.fit.objective < 1e6
    assert "transport_scales" in result.metadata


def test_exports_include_provenance_and_assessment() -> None:
    artifacts = build_export_artifacts(run_result, prepared_inputs, "0.2.0")
    assert {
        "observations_prepared.csv",
        "climate_forcing.csv",
        "bulk_density.csv",
        "predictions.csv",
        "fit_parameters.csv",
        "fit_diagnostics.csv",
        "run_metadata.json",
    } <= artifacts.keys()
    metadata = json.loads(artifacts["run_metadata.json"])
    assert metadata["residue_assessment"]["time_days"] == 90
```

- [ ] **Step 2: Implement direct CLTF orchestration**

`model_service.py` calls:

```python
simulate_cltf(...)
fit_cltf(...)
profile_cltf_parameter(...)
```

Default parameter bounds match shared references. Application rate is inferred
from positive top-layer T0 replicates unless the advanced user input supplies
an explicit value.

- [ ] **Step 3: Implement shared-schema exports**

Use the same filenames and columns as the reference runners. Metadata includes:

- selected site/soil/herbicide;
- package and app versions;
- climate and soil source;
- application rate and source;
- effective porosity;
- parameters, bounds, convergence, transport scales, and identifiability note;
- residue assessment date and results;
- input checksums.

- [ ] **Step 4: Run and commit**

```bash
python -m pytest \
  apps/herbicide_workbench/tests/test_model_service.py \
  apps/herbicide_workbench/tests/test_exports.py -q
git add apps/herbicide_workbench
git commit -m "feat: add CLTF app run and export services"
```

### Task 9: Rebuild the Streamlit interface

**Files:**
- Replace: `apps/herbicide_workbench/app.py`
- Modify: `apps/herbicide_workbench/workbench/__init__.py`
- Create: `apps/herbicide_workbench/tests/test_app_smoke.py`

- [ ] **Step 1: Add an AppTest smoke test**

```python
from streamlit.testing.v1 import AppTest


def test_default_app_loads_nsw_showcase() -> None:
    app = AppTest.from_file("apps/herbicide_workbench/app.py").run(timeout=30)
    assert not app.exception
    assert app.selectbox[0].value == "NSW Griffith"
    assert "Residue assessment date" in [widget.label for widget in app.date_input]
```

- [ ] **Step 2: Implement the approved page flow**

Page order:

1. Exact project title.
2. Site, soil, and herbicide selectors.
3. Interactive map.
4. Bundled example/upload choice and one observation uploader.
5. Input provenance and inferred application settings.
6. Residue assessment presets and date control.
7. Advanced overrides for application rate, layer bulk density, effective
   porosity, and refresh flags.
8. Run simulation and fit buttons.
9. Summary cards at assessment.
10. Diagnostic plots and tables.
11. Download artifacts.

Default selection:

```text
NSW Griffith / Heavy / Imazapic
```

Default assessment:

```text
application date + 90 days
```

- [ ] **Step 3: Run smoke and complete app tests**

```bash
python -m pytest apps/herbicide_workbench/tests -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add apps/herbicide_workbench
git commit -m "feat: rebuild herbicide workbench on Python CLTF"
```

### Task 10: Remove legacy app data and documentation

**Files:**
- Delete: `apps/herbicide_workbench/sample_data/observed_rel.csv`
- Delete: `apps/herbicide_workbench/sample_data/site_config.csv`
- Delete: `apps/herbicide_workbench/sample_data/daily_climate.csv`
- Replace: `apps/herbicide_workbench/README.md`
- Modify: app requirements and root requirements

- [ ] **Step 1: Prove shared data replaced app-local data**

```bash
rg -n 'sample_data|relative_concentration|top_rel_conc|subsoil_rel_conc' \
  apps/herbicide_workbench
```

Expected: only legacy files match.

- [ ] **Step 2: Delete legacy samples**

```bash
git rm -r apps/herbicide_workbench/sample_data
```

- [ ] **Step 3: Document operation**

App README covers:

- one observation CSV;
- two-site selector;
- automatic cached/API climate and bulk density;
- historical-only limitation;
- residue assessment date;
- Mapbox token and fallback;
- environment variables;
- local run and Streamlit deployment;
- future climatology forecasting.

- [ ] **Step 4: Run and commit**

```bash
python -m pytest apps/herbicide_workbench/tests -q
git add apps/herbicide_workbench requirements*.txt
git commit -m "docs: remove legacy workbench schemas"
```

### Task 11: Complete branding and naming audit

**Files:**
- Replace: `PyCLT_logo.png` → `cltf_logo.png`
- Modify: root `README.md`
- Modify: all active text files
- Modify: historical docs where legacy terms remain unintentionally

- [ ] **Step 1: Generate a language-neutral logo**

Use the `imagegen` skill to create a CLTF logo that:

- contains `CLTF`, not `pyCLT`;
- depicts rainfall/infiltration and two soil layers;
- contains no Python or R logo;
- remains readable at 180 px;
- has a transparent or plain light background.

Save as `cltf_logo.png` and delete `PyCLT_logo.png`.

- [ ] **Step 2: Replace root README**

The first lines are:

```markdown
<img src="cltf_logo.png" alt="CLTF logo" align="right" width="180" />

# Herbicide Dynamics Simulated by the Convective Lognormal Transfer Function (CLTF) in Python and R
```

Document:

- monorepo layout;
- R and Python installation;
- shared NSW example;
- SA regression case;
- app launch;
- model units and assumptions;
- identifiability warning;
- historical-analysis limitation and forecast roadmap.

- [ ] **Step 3: Run a strict legacy-name audit**

```bash
rg -n -i --hidden --glob '!.git/**' \
  'rclt|pyclt|PyCLT|simulate_rclt|fit_rclt|rclt_objective|TwoLayerCLT|CLTParameters'
```

Expected matches are allowed only in:

- the 2026-06-24 migration specification and implementation plans when
  describing removed names;
- Git history, which is outside the search.

All active code, data, metadata, scripts, docs, paths, and environment variables
must otherwise be clean.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "docs: complete language-neutral CLTF branding"
```

### Task 12: Final scientific and application verification

**Files:**
- Verify all repository files

- [ ] **Step 1: Run R verification**

```bash
Rscript -e 'testthat::test_local("R")'
R CMD build R
mkdir -p /tmp/cltf-final-r-check
R CMD check cltf_0.1.0.tar.gz --no-manual --output=/tmp/cltf-final-r-check
rm cltf_0.1.0.tar.gz
```

Expected: tests PASS and `Status: OK`.

- [ ] **Step 2: Run Python and app verification**

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider \
  python/tests apps/herbicide_workbench/tests
```

Expected: all tests PASS.

- [ ] **Step 3: Run both language showcase workflows offline**

```bash
env -u SILO_USERNAME -u SILO_PASSWORD -u TERN_API_KEY \
  Rscript examples/R/run_reference_case.R \
  --case nsw_griffith_heavy_imazapic \
  --input-dir examples/data/nsw_griffith_heavy_imazapic \
  --output-dir /tmp/nsw-final-r

env -u SILO_USERNAME -u SILO_PASSWORD -u TERN_API_KEY \
  python examples/python/run_reference_case.py \
  --case nsw_griffith_heavy_imazapic \
  --input-dir examples/data/nsw_griffith_heavy_imazapic \
  --output-dir /tmp/nsw-final-python
```

Expected: both succeed and conformance tests pass.

- [ ] **Step 4: Launch Streamlit headlessly**

```bash
timeout 30s streamlit run apps/herbicide_workbench/app.py \
  --server.headless true \
  --server.port 8510
```

Expected: startup reaches a healthy server without an import exception.

- [ ] **Step 5: Inspect repository state**

```bash
git diff --check
git status --short
```

Expected: clean.

### Task 13: Merge the feature branch

**Files:**
- Git history only

- [ ] **Step 1: Use the finishing-development-branch workflow**

Select local merge after all verification passes.

- [ ] **Step 2: Verify merged main**

Repeat Task 12 tests from the main checkout.

### Task 14: Rename GitHub repository and local checkout

**Files:**
- External GitHub repository settings
- Local directory name
- Git remote configuration

- [ ] **Step 1: Verify GitHub authentication and name availability**

```bash
gh auth status
gh api repos/PAHGISL/cltf
```

Expected: authentication succeeds and the second command returns HTTP 404. If
authentication fails or `PAHGISL/cltf` exists, stop and report the blocker.

- [ ] **Step 2: Push verified main before rename**

```bash
git push origin main
```

- [ ] **Step 3: Rename the GitHub repository**

```bash
gh api \
  --method PATCH \
  repos/PAHGISL/PyCLT \
  -f name=cltf
```

Expected response includes:

```json
"full_name": "PAHGISL/cltf"
```

- [ ] **Step 4: Update remote**

```bash
git remote set-url origin https://github.com/PAHGISL/cltf.git
git remote -v
git ls-remote origin HEAD
```

Expected: fetch and push URLs use `PAHGISL/cltf.git`.

- [ ] **Step 5: Ensure no linked worktrees remain**

```bash
git worktree list
```

Remove completed feature worktrees before renaming the checkout.

- [ ] **Step 6: Rename the local checkout**

From `/g/data/ym05/github/yuyi13`:

```bash
mv PyCLT cltf
cd /g/data/ym05/github/yuyi13/cltf
```

- [ ] **Step 7: Final path and remote verification**

```bash
pwd
git status --short
git remote -v
rg -n '/PyCLT|PAHGISL/PyCLT' --hidden --glob '!.git/**' .
```

Expected:

- path is `/g/data/ym05/github/yuyi13/cltf`;
- worktree is clean;
- origin is `https://github.com/PAHGISL/cltf.git`;
- no old repository paths or URLs remain.

## Completion Gate

- The app uses only Python `cltf` and the new resident-concentration schema.
- Observation CSV is the only upload.
- NSW and SA are selected from the internal registry.
- Climate and soil are cache-first with explicit source/fallback metadata.
- Satellite map and attributed fallback both work.
- Residue assessment defaults to day 90, remains within observed forcing, and
  appears in summaries, plots, and exports.
- Legacy app schemas, adapter, sample data, and relative-concentration outputs
  are gone.
- Naming and branding audits pass.
- R, Python, conformance, and app suites pass.
- GitHub repository, local checkout, and origin are renamed to `cltf`.
