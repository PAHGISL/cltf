# CLTF Shared NSW and SA Reference Workflows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish language-neutral NSW Griffith and SA Minnipa inputs, generate authoritative R reference outputs, and prove the Python implementation reproduces both cases.

**Architecture:** Store normalized observations, forcing, soil bands, site configuration, and case configuration under `examples/data/`. A shared case runner in each language consumes the same files and writes the same output schemas. The R outputs are committed as the initial references, while conformance tests compare Python outputs using explicit tolerances and ridge-aware calibration diagnostics.

**Tech Stack:** R `cltf`, Python `cltf`, CSV, JSON, testthat, pytest

---

All new R and Python entry scripts must use the workspace-standard script
header with `Last updated: 2026-06-24`.

## File Map

- Create `examples/data/sites.json`.
- Create `examples/data/nsw_griffith_heavy_imazapic/`.
- Complete `examples/data/sa_minnipa_heavy_imazapic/`.
- Create `examples/R/run_reference_case.R`.
- Create `examples/python/run_reference_case.py`.
- Create `reference/nsw_griffith_heavy_imazapic/`.
- Retain and normalize `reference/sa_minnipa_heavy_imazapic/`.
- Create R and Python case-regression tests.

### Task 1: Define the shared site and case schemas

**Files:**
- Create: `examples/data/sites.json`
- Create: `examples/data/nsw_griffith_heavy_imazapic/case.json`
- Create: `examples/data/sa_minnipa_heavy_imazapic/case.json`
- Create: `R/tests/testthat/test-shared-cases.R`
- Create: `python/tests/test_shared_cases.py`

- [ ] **Step 1: Write schema tests**

R:

```r
test_that("shared case registry defines both approved sites", {
  sites <- jsonlite::fromJSON(
    testthat::test_path("..", "..", "..", "examples", "data", "sites.json")
  )
  expect_equal(sites$site_id, c("NSW_Griffith", "SA_Minnipa"))
  expect_equal(sites$top_depth_mm, c(150, 100))
  expect_equal(sites$bottom_depth_mm, c(300, 300))
})
```

Python:

```python
def test_site_registry_defines_approved_sites() -> None:
    sites = json.loads(Path("examples/data/sites.json").read_text())
    assert [site["site_id"] for site in sites] == ["NSW_Griffith", "SA_Minnipa"]
    assert [site["top_depth_mm"] for site in sites] == [150, 100]
```

- [ ] **Step 2: Create the registry**

`examples/data/sites.json`:

```json
[
  {
    "site_id": "NSW_Griffith",
    "display_name": "NSW Griffith",
    "latitude": -34.194974,
    "longitude": 146.08877,
    "silo_latitude": -34.2,
    "silo_longitude": 146.1,
    "top_depth_mm": 150,
    "bottom_depth_mm": 300,
    "soil_groups": ["Heavy", "Light"],
    "default_soil_group": "Heavy",
    "default_herbicide": "Imazapic"
  },
  {
    "site_id": "SA_Minnipa",
    "display_name": "SA Minnipa",
    "latitude": -32.831016,
    "longitude": 135.14494,
    "silo_latitude": -32.85,
    "silo_longitude": 135.15,
    "top_depth_mm": 100,
    "bottom_depth_mm": 300,
    "soil_groups": ["Heavy", "Light"],
    "default_soil_group": "Heavy",
    "default_herbicide": "Imazapic"
  }
]
```

Each `case.json` contains:

```json
{
  "site_id": "NSW_Griffith",
  "soil_group": "Heavy",
  "herbicide": "Imazapic",
  "application_date": "2024-04-26",
  "final_date": "2024-09-19",
  "top_depth_mm": 150,
  "bottom_depth_mm": 300,
  "effective_porosity": 0.2,
  "et_factor": 1.0,
  "irrigation_mm": 0.0,
  "convolution_method": "trapezoid",
  "convolution_steps": 2001,
  "concentration_unit": "ug/kg dry soil",
  "unit_status": "provisional; inferred from the sampled-data structure"
}
```

Use the corresponding SA values and dates `2024-06-12` to `2024-10-28`.

- [ ] **Step 3: Run tests and commit**

```bash
Rscript -e 'testthat::test_local("R", filter = "shared-cases")'
python -m pytest python/tests/test_shared_cases.py -q
git add examples/data R/tests python/tests
git commit -m "feat: define shared CLTF site registry"
```

### Task 2: Prepare normalized shared observations

**Files:**
- Create: `examples/data/nsw_griffith_heavy_imazapic/observations.csv`
- Create: `examples/data/sa_minnipa_heavy_imazapic/observations.csv`
- Create: `examples/R/prepare_shared_observations.R`
- Test: shared case tests

- [ ] **Step 1: Add expected observation assertions**

```r
test_that("shared showcase observations preserve replicate rows", {
  nsw <- utils::read.csv(testthat::test_path(
    "..", "..", "..", "examples", "data",
    "nsw_griffith_heavy_imazapic", "observations.csv"
  ))
  sa <- utils::read.csv(testthat::test_path(
    "..", "..", "..", "examples", "data",
    "sa_minnipa_heavy_imazapic", "observations.csv"
  ))

  expect_equal(nrow(nsw), 30)
  expect_equal(sum(nsw$used_for_calibration), 24)
  expect_equal(sort(unique(nsw$depth_bottom_mm)), c(150, 300))
  expect_equal(nrow(sa), 31)
  expect_equal(sum(sa$used_for_calibration), 25)
})
```

- [ ] **Step 2: Create the preparation script**

`examples/R/prepare_shared_observations.R` must:

```r
observations <- read_herbicide_workbook(
  workbook_path,
  sheets = c("NSW", "SA")
)

write_case <- function(site_id, soil_group, herbicide, output_path) {
  selected <- observations$site_id == site_id &
    observations$soil_group == soil_group &
    observations$herbicide == herbicide
  case <- observations[selected, ]
  case$used_for_calibration <- !case$is_t0 &
    is.finite(case$analysis_concentration_ug_kg) &
    case$analysis_concentration_ug_kg > 0
  utils::write.csv(case, output_path, row.names = FALSE, na = "")
}
```

Call it for NSW Griffith Heavy/Imazapic and SA Minnipa Heavy/Imazapic.

- [ ] **Step 3: Generate and verify**

```bash
Rscript examples/R/prepare_shared_observations.R \
  --workbook "/g/data/ym05/herbicide/context/Herbicide Dissipation 2024.xlsx"
Rscript -e 'testthat::test_local("R", filter = "shared-cases")'
```

Expected: 30 NSW rows, 24 positive post-T0 calibration rows; 31 SA rows,
25 calibration rows.

- [ ] **Step 4: Commit**

```bash
git add examples/data examples/R/prepare_shared_observations.R R/tests
git commit -m "data: add shared NSW and SA observations"
```

### Task 3: Prepare shared climate forcing

**Files:**
- Create: `examples/data/nsw_griffith_heavy_imazapic/silo.csv`
- Create: `examples/data/nsw_griffith_heavy_imazapic/silo_metadata.json`
- Create: `examples/data/sa_minnipa_heavy_imazapic/silo.csv`
- Create: `examples/data/sa_minnipa_heavy_imazapic/silo_metadata.json`
- Create: `examples/R/prepare_shared_climate.R`

- [ ] **Step 1: Add forcing assertions**

```r
test_that("shared SILO forcing covers each observation period", {
  nsw <- parse_silo_csv(testthat::test_path(
    "..", "..", "..", "examples", "data",
    "nsw_griffith_heavy_imazapic", "silo.csv"
  ))
  sa <- parse_silo_csv(testthat::test_path(
    "..", "..", "..", "examples", "data",
    "sa_minnipa_heavy_imazapic", "silo.csv"
  ))

  expect_equal(nrow(nsw), 147)
  expect_equal(range(nsw$date), as.Date(c("2024-04-26", "2024-09-19")))
  expect_equal(nrow(sa), 139)
  expect_equal(range(sa$date), as.Date(c("2024-06-12", "2024-10-28")))
})
```

- [ ] **Step 2: Normalize existing SILO-derived climate**

Use `apps/herbicide_workbench/sample_data/daily_climate.csv` as the source
because it already contains the exact 2024 SILO grid-cell extraction for both
sites. Write Data Drill-compatible columns:

```text
Date,T.Max,T.Min,Rain
```

Metadata must state:

```json
{
  "source": "Existing 2024 SILO gridded-archive extraction normalized to the shared CLTF cache schema",
  "request_latitude": -34.194974,
  "request_longitude": 146.08877,
  "grid_latitude": -34.2,
  "grid_longitude": 146.1,
  "start_date": "2024-04-26",
  "end_date": "2024-09-19",
  "raw_cache_file": "silo.csv"
}
```

Use corresponding SA coordinates and dates.

- [ ] **Step 3: Verify and commit**

```bash
Rscript examples/R/prepare_shared_climate.R
Rscript -e 'testthat::test_local("R", filter = "shared-cases")'
git add examples/data examples/R/prepare_shared_climate.R R/tests
git commit -m "data: add shared NSW and SA climate forcing"
```

### Task 4: Retrieve and cache NSW SLGA bulk density

**Files:**
- Create: `examples/data/nsw_griffith_heavy_imazapic/bulk_density.json`
- Move/copy normalized SA cache to `examples/data/sa_minnipa_heavy_imazapic/bulk_density.json`
- Modify: shared case tests

- [ ] **Step 1: Require a credentialed NSW extraction**

```bash
test -n "$TERN_API_KEY"
```

Expected: success. If this fails, stop this task and request a TERN API key.
Do not fabricate NSW bulk-density values or reuse the SA values.

- [ ] **Step 2: Retrieve NSW bands**

```bash
Rscript - <<'RS'
pkgload::load_all("R", quiet = TRUE)
bands <- fetch_slga_bulk_density(
  latitude  = -34.194974,
  longitude = 146.08877,
  cache_dir = tempfile("nsw-slga-"),
  refresh   = TRUE
)
cache_path <- attr(bands, "cache_path")
file.copy(
  cache_path,
  "examples/data/nsw_griffith_heavy_imazapic/bulk_density.json",
  overwrite = TRUE
)
RS
```

- [ ] **Step 3: Normalize the existing SA cache**

Copy the current normalized SA SLGA JSON into:

```text
examples/data/sa_minnipa_heavy_imazapic/bulk_density.json
```

Retain its explicit provisional-source label until a credentialed SA extraction
replaces it.

- [ ] **Step 4: Add validation assertions**

Both JSON files must parse to three bands:

```text
0–50 mm
50–150 mm
150–300 mm
```

NSW metadata must identify a credentialed SLGA v2 whole-earth retrieval.

- [ ] **Step 5: Remove the superseded internal cache directory**

After both site inputs exist under `examples/data/`, remove the old cache:

```bash
git rm -r reference/cache
```

- [ ] **Step 6: Commit**

```bash
git add examples/data R/tests
git commit -m "data: add shared SLGA bulk-density inputs"
```

### Task 5: Generalize the R reference runner

**Files:**
- Create: `examples/R/run_reference_case.R`
- Delete: `examples/R/run_sa_reference.R`
- Create: `R/tests/testthat/test-reference-runner.R`

- [ ] **Step 1: Write CLI smoke tests**

```r
test_that("reference runner accepts both case identifiers", {
  script <- testthat::test_path(
    "..", "..", "..", "examples", "R", "run_reference_case.R"
  )
  help <- system2("Rscript", c(script, "--help"), stdout = TRUE)
  expect_true(any(grepl("--case", help, fixed = TRUE)))
})
```

- [ ] **Step 2: Implement a case-driven runner**

Accepted CLI:

```text
--case nsw_griffith_heavy_imazapic|sa_minnipa_heavy_imazapic
--input-dir DIR
--output-dir DIR
```

The script reads:

```text
case.json
observations.csv
silo.csv
silo_metadata.json
bulk_density.json
```

It calculates PET and cumulative infiltration, depth-weights density, infers
application rate from positive top-layer T0 replicates, excludes all T0 rows
from calibration, fits `mu`, `sigma`, `R_top`, `R_bottom`, and `k`, and writes
the same CSV/JSON/PNG schema currently produced for SA.

- [ ] **Step 3: Remove the case-specific runner**

```bash
git rm examples/R/run_sa_reference.R
```

- [ ] **Step 4: Run both cases**

```bash
Rscript examples/R/run_reference_case.R \
  --case nsw_griffith_heavy_imazapic \
  --input-dir examples/data/nsw_griffith_heavy_imazapic \
  --output-dir /tmp/cltf-nsw-r

Rscript examples/R/run_reference_case.R \
  --case sa_minnipa_heavy_imazapic \
  --input-dir examples/data/sa_minnipa_heavy_imazapic \
  --output-dir /tmp/cltf-sa-r
```

Expected: both output directories contain complete artifacts and exact mass
balance within `1e-8`.

- [ ] **Step 5: Commit**

```bash
git add examples/R R/tests
git commit -m "feat: generalize R CLTF reference runner"
```

### Task 6: Commit authoritative R reference outputs

**Files:**
- Create: `reference/nsw_griffith_heavy_imazapic/*`
- Replace normalized files under `reference/sa_minnipa_heavy_imazapic/`
- Create: `reference/README.md`

- [ ] **Step 1: Generate references**

```bash
rm -rf reference/nsw_griffith_heavy_imazapic
Rscript examples/R/run_reference_case.R \
  --case nsw_griffith_heavy_imazapic \
  --input-dir examples/data/nsw_griffith_heavy_imazapic \
  --output-dir reference/nsw_griffith_heavy_imazapic

Rscript examples/R/run_reference_case.R \
  --case sa_minnipa_heavy_imazapic \
  --input-dir examples/data/sa_minnipa_heavy_imazapic \
  --output-dir reference/sa_minnipa_heavy_imazapic
```

- [ ] **Step 2: Add reference documentation**

`reference/README.md` explains:

- R is the initial reference implementation;
- NSW is the primary showcase;
- SA is the secondary regression;
- concentration unit and SA density remain provisional where applicable;
- calibration parameter equality is not required because of the scaling ridge;
- `reference/tolerances.json` governs comparisons.

- [ ] **Step 3: Add regression tests**

For each case assert:

```r
expect_equal(rowSums(predictions[mass_columns]), rep(1, nrow(predictions)),
             tolerance = 1e-8)
expect_true(all(parameters$estimate >= parameters$lower))
expect_true(all(parameters$estimate <= parameters$upper))
expect_true(all(is.finite(predictions$concentration_top_ug_kg)))
expect_true(all(is.finite(predictions$concentration_bottom_ug_kg)))
```

- [ ] **Step 4: Commit**

```bash
git add reference R/tests
git commit -m "feat: add NSW and SA R reference outputs"
```

### Task 7: Add the Python shared-case runner

**Files:**
- Create: `examples/python/run_reference_case.py`
- Create: `python/tests/test_reference_runner.py`

- [ ] **Step 1: Write CLI and output tests**

```python
def test_python_runner_writes_expected_schema(tmp_path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "examples/python/run_reference_case.py",
            "--case",
            "nsw_griffith_heavy_imazapic",
            "--input-dir",
            "examples/data/nsw_griffith_heavy_imazapic",
            "--output-dir",
            str(tmp_path),
        ],
        check=True,
    )
    expected = {
        "bulk_density.csv",
        "climate_forcing.csv",
        "fit_diagnostics.csv",
        "fit_parameters.csv",
        "metadata.json",
        "objective_profiles.csv",
        "observations_prepared.csv",
        "predictions.csv",
    }
    assert expected <= {path.name for path in tmp_path.iterdir()}
```

- [ ] **Step 2: Implement the same workflow**

Use only public Python `cltf` APIs. Match R output column names and JSON field
names. Timestamp fields may differ; deterministic numerical CSVs must not.

- [ ] **Step 3: Run both cases**

```bash
python examples/python/run_reference_case.py \
  --case nsw_griffith_heavy_imazapic \
  --input-dir examples/data/nsw_griffith_heavy_imazapic \
  --output-dir /tmp/cltf-nsw-python

python examples/python/run_reference_case.py \
  --case sa_minnipa_heavy_imazapic \
  --input-dir examples/data/sa_minnipa_heavy_imazapic \
  --output-dir /tmp/cltf-sa-python
```

- [ ] **Step 4: Commit**

```bash
git add examples/python python/tests
git commit -m "feat: add Python CLTF reference runner"
```

### Task 8: Add cross-language case conformance tests

**Files:**
- Create: `python/tests/test_case_conformance.py`
- Create: `R/tests/testthat/test-case-conformance.R`

- [ ] **Step 1: Compare deterministic forward outputs**

For both cases compare Python-generated output to committed R reference:

```python
MASS_COLUMNS = ["mass_top", "mass_bottom", "mass_below", "mass_degraded"]
CONCENTRATION_COLUMNS = [
    "concentration_top_ug_kg",
    "concentration_bottom_ug_kg",
]

np.testing.assert_allclose(
    python_predictions[MASS_COLUMNS],
    r_predictions[MASS_COLUMNS],
    atol=tolerances["absolute"],
    rtol=tolerances["relative"],
)
np.testing.assert_allclose(
    python_predictions[CONCENTRATION_COLUMNS],
    r_predictions[CONCENTRATION_COLUMNS],
    atol=tolerances["absolute"],
    rtol=tolerances["relative"],
)
```

- [ ] **Step 2: Compare calibration diagnostics ridge-aware**

Assert:

```python
assert abs(python_objective - r_objective) <= objective_tolerance
np.testing.assert_allclose(
    python_transport_scales,
    r_transport_scales,
    atol=transport_scale_tolerance,
    rtol=transport_scale_tolerance,
)
```

Compare fitted predictions rather than requiring identical `mu`, `R_top`, and
`R_bottom`.

- [ ] **Step 3: Run all conformance tests**

```bash
Rscript -e 'testthat::test_local("R", filter = "conformance")'
python -m pytest \
  python/tests/test_r_conformance.py \
  python/tests/test_case_conformance.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add R/tests python/tests
git commit -m "test: verify NSW and SA cross-language equivalence"
```

### Task 9: Document and verify shared examples

**Files:**
- Create: `examples/README.md`
- Create: `examples/data/nsw_griffith_heavy_imazapic/README.md`
- Update: SA shared-input README
- Update: root `README.md`

- [ ] **Step 1: Document exact commands**

Include paired commands:

```bash
Rscript examples/R/run_reference_case.R \
  --case nsw_griffith_heavy_imazapic \
  --input-dir examples/data/nsw_griffith_heavy_imazapic \
  --output-dir /tmp/nsw-r

python examples/python/run_reference_case.py \
  --case nsw_griffith_heavy_imazapic \
  --input-dir examples/data/nsw_griffith_heavy_imazapic \
  --output-dir /tmp/nsw-python
```

- [ ] **Step 2: Verify offline operation**

```bash
env -u SILO_USERNAME -u SILO_PASSWORD -u TERN_API_KEY \
  Rscript examples/R/run_reference_case.R \
  --case nsw_griffith_heavy_imazapic \
  --input-dir examples/data/nsw_griffith_heavy_imazapic \
  --output-dir /tmp/nsw-r-offline

env -u SILO_USERNAME -u SILO_PASSWORD -u TERN_API_KEY \
  python examples/python/run_reference_case.py \
  --case nsw_griffith_heavy_imazapic \
  --input-dir examples/data/nsw_griffith_heavy_imazapic \
  --output-dir /tmp/nsw-python-offline
```

Expected: both succeed without network access.

- [ ] **Step 3: Run complete suites and commit**

```bash
Rscript -e 'testthat::test_local("R")'
python -m pytest python/tests -q
git add README.md examples reference
git commit -m "docs: document shared CLTF reference cases"
```

## Completion Gate

- NSW Griffith Heavy/Imazapic is the primary shared showcase.
- SA Minnipa Heavy/Imazapic remains a secondary regression.
- Both cases have shared observations, forcing, soil, and case configuration.
- NSW bulk density comes from a credentialed SLGA extraction, not an invented fallback.
- R and Python runners consume identical inputs and produce identical schemas.
- Forward predictions match within strict tolerances.
- Calibration comparisons account for the known scaling ridge.
- Both cases run offline from committed inputs.
