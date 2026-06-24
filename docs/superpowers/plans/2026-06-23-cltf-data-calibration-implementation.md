# CLTF Data, Calibration, and Reference Workflow Implementation Plan

> Naming note: paths and APIs were updated on 2026-06-24 to the approved
> language-neutral CLTF monorepo convention. Git history preserves the original
> implementation terminology.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the verified CLTF numerical package with observation preparation, SILO and SLGA cached access, calibration, base-R diagnostics, and a reproducible SA Minnipa Imazapic reference case.

**Architecture:** External data retrieval is isolated behind cache-first functions so model tests and reference runs require no network access. Observation preparation preserves replicates and explicit depth intervals, while calibration consumes only tidy tables and the numerical simulator. The SA workflow writes versioned forcing, soil, observation, prediction, parameter, metadata, and plot artifacts that later become Python-equivalence fixtures.

**Tech Stack:** R 4.5, `testthat`, `readxl`, `jsonlite`, `terra`, `withr`, base `optim`, base graphics, SILO Data Drill API, SLGA Raster Products API/TERN COGs

---

**Execution prerequisite:** Complete the numerical-core plan first, then execute this plan in the same isolated feature worktree.

## File Map

- Modify `R/DESCRIPTION`: add optional data/geospatial dependencies.
- Create `R/R/observations.R`: workbook import, depth mapping, non-detect handling, geometric summaries, application-rate inference.
- Create `R/R/climate.R`: Priestley–Taylor temperature PET.
- Create `R/R/silo.R`: cache-first SILO request and parser.
- Create `R/R/slga.R`: cache-first SLGA metadata, point extraction and depth weighting.
- Create `R/R/calibration.R`: replicate-level log objective, multistart fitting, bound and profile diagnostics.
- Create `R/R/plots.R`: required base-R plots with Arial.
- Create `R/inst/extdata/`: small review-safe fixtures and data-service responses.
- Create `R/examples/run_sa_reference.R`: end-to-end reference workflow.
- Create `R/tests/testthat/test-observations.R`.
- Create `R/tests/testthat/test-climate.R`.
- Create `R/tests/testthat/test-silo.R`.
- Create `R/tests/testthat/test-slga.R`.
- Create `R/tests/testthat/test-calibration.R`.
- Create `R/tests/testthat/test-plots.R`.
- Create `R/tests/testthat/test-sa-regression.R`.
- Create `R/reference/sa_minnipa_heavy_imazapic/`: versioned reference outputs.

All new or revised R files must comply with the workspace script-header standard.

### Task 1: Add data dependencies and review-safe fixtures

**Files:**
- Modify: `R/DESCRIPTION`
- Create: `R/inst/extdata/sa_observations.csv`
- Create: `R/inst/extdata/sa_silo.csv`
- Create: `R/inst/extdata/slga_bulk_density_response.json`

- [ ] **Step 1: Install the one currently missing workbook dependency**

Run:

```bash
Rscript -e 'if (!requireNamespace("readxl", quietly = TRUE)) install.packages("readxl", repos = "https://cloud.r-project.org")'
```

Expected: `readxl` installs successfully.

- [ ] **Step 2: Extend package dependencies**

Update `R/DESCRIPTION`:

```text
Imports:
    jsonlite,
    stats,
    utils
Suggests:
    readxl,
    terra,
    testthat (>= 3.0.0),
    withr
```

- [ ] **Step 3: Create a minimal observation fixture**

Create `R/inst/extdata/sa_observations.csv`:

```csv
site_id,soil_group,herbicide,application_date,sample_date,days_since_application,depth_top_mm,depth_bottom_mm,replicate_id,concentration_ug_kg,is_non_detect,detection_limit_ug_kg,is_t0
SA_Minnipa,Heavy,Imazapic,2024-06-12,2024-06-12,0,0,100,1,16.4,FALSE,,TRUE
SA_Minnipa,Heavy,Imazapic,2024-06-12,2024-06-27,15,0,100,1,5.8,FALSE,,FALSE
SA_Minnipa,Heavy,Imazapic,2024-06-12,2024-07-10,28,100,300,1,4.2,FALSE,,FALSE
```

- [ ] **Step 4: Create deterministic SILO and SLGA parser fixtures**

Create `R/inst/extdata/sa_silo.csv`:

```csv
Date,T.Max,T.Min,Rain
20240612,18.4,7.1,0.0
20240613,19.2,6.8,3.4
```

Create `R/inst/extdata/slga_bulk_density_response.json`:

```json
{
  "latitude": -32.831016,
  "longitude": 135.14494,
  "values": [
    {"depth_top_cm": 0, "depth_bottom_cm": 5, "estimate_g_cm3": 1.32, "lower_g_cm3": 1.18, "upper_g_cm3": 1.46},
    {"depth_top_cm": 5, "depth_bottom_cm": 15, "estimate_g_cm3": 1.38, "lower_g_cm3": 1.22, "upper_g_cm3": 1.54},
    {"depth_top_cm": 15, "depth_bottom_cm": 30, "estimate_g_cm3": 1.43, "lower_g_cm3": 1.28, "upper_g_cm3": 1.58}
  ]
}
```

- [ ] **Step 5: Verify package loading**

Run:

```bash
Rscript -e 'roxygen2::roxygenise("cltf"); testthat::test_local("R")'
```

Expected: package loads without an error.

- [ ] **Step 6: Commit**

```bash
git add R/DESCRIPTION R/inst/extdata
git commit -m "build: add CLTF data integration dependencies"
```

### Task 2: Implement observation preparation

**Files:**
- Create: `R/R/observations.R`
- Create: `R/tests/testthat/test-observations.R`

- [ ] **Step 1: Write failing depth and non-detect tests**

Create `R/tests/testthat/test-observations.R` with tests that assert:

```r
expect_equal(depth_interval_mm("SA", "10cm"), c(0, 100))
expect_equal(depth_interval_mm("SA", "30cm"), c(100, 300))
expect_equal(depth_interval_mm("NSW", "15cm"), c(0, 150))
expect_equal(depth_interval_mm("NSW", "30cm"), c(150, 300))

prepared <- prepare_non_detects(
  concentration_ug_kg   = c(2, 0, 0),
  is_non_detect         = c(FALSE, TRUE, FALSE),
  detection_limit_ug_kg = c(NA, 0.2, NA)
)
expect_equal(prepared$analysis_concentration_ug_kg, c(2, 0.1, NA))
expect_true(prepared$excluded_zero[3])

summary <- geometric_concentration(
  data.frame(
    group = c("a", "a", "a"),
    analysis_concentration_ug_kg = c(1, 2, 4)
  ),
  group_columns = "group"
)
expect_equal(summary$geometric_mean_ug_kg, 2)
```

- [ ] **Step 2: Run tests and confirm missing-function failures**

Run:

```bash
Rscript -e 'testthat::test_local("R", filter = "observations")'
```

Expected: FAIL because observation functions do not exist.

- [ ] **Step 3: Implement explicit interval mapping**

In `R/R/observations.R`, implement:

```r
depth_interval_mm <- function(sheet, depth_label) {
  key <- paste(toupper(sheet), gsub("\\s+", "", tolower(depth_label)), sep = ":")
  intervals <- list(
    "SA:10cm"  = c(0, 100),
    "SA:30cm"  = c(100, 300),
    "NSW:15cm" = c(0, 150),
    "NSW:30cm" = c(150, 300),
    "QLD:10cm" = c(0, 100),
    "QLD:30cm" = c(100, 300)
  )
  result <- intervals[[key]]
  if (is.null(result)) {
    stop("Unsupported sheet/depth combination: ", key, call. = FALSE)
  }
  result
}
```

Add the standard R header and export the function.

- [ ] **Step 4: Implement non-detect and geometric-summary functions**

Implement:

```r
prepare_non_detects <- function(
  concentration_ug_kg,
  is_non_detect,
  detection_limit_ug_kg
) {
  substituted <- is_non_detect & is.finite(detection_limit_ug_kg)
  excluded_zero <- concentration_ug_kg <= 0 & !substituted
  analysis <- concentration_ug_kg
  analysis[substituted] <- detection_limit_ug_kg[substituted] / 2
  analysis[excluded_zero] <- NA_real_
  data.frame(
    analysis_concentration_ug_kg = analysis,
    lod_substituted              = substituted,
    excluded_zero                = excluded_zero
  )
}

geometric_concentration <- function(data, group_columns) {
  key <- interaction(data[group_columns], drop = TRUE, lex.order = TRUE)
  split_data <- split(data, key)
  rows <- lapply(split_data, function(group) {
    values <- group$analysis_concentration_ug_kg
    values <- values[is.finite(values) & values > 0]
    first <- group[1, group_columns, drop = FALSE]
    first$n <- length(values)
    first$geometric_mean_ug_kg <- if (length(values)) exp(mean(log(values))) else NA_real_
    first$geometric_sd <- if (length(values) > 1L) exp(stats::sd(log(values))) else NA_real_
    first
  })
  do.call(rbind, rows)
}
```

- [ ] **Step 5: Implement workbook import**

Implement `read_herbicide_workbook(path, sheets = c("SA", "NSW", "Qld"))` using `readxl::read_excel()`. It must:

- preserve the `Soil`, `Irrigation`, `Timepoint`, `Crop_2024`, `Depth`, and `Sample_date` identifiers when present;
- pivot herbicide columns with base `stack()`;
- convert Excel dates with `as.Date(value, origin = "1899-12-30")` when numeric;
- assign site IDs `SA_Minnipa`, `NSW_Griffith`, and `QLD_Wellcamp`;
- group T0 dates by site, soil and irrigation treatment;
- calculate replicate IDs within site, soil, treatment, herbicide, interval and date;
- name the concentration field `concentration_ug_kg`;
- set `unit_status = "inferred_from_application_rate"`.

- [ ] **Step 6: Add application-rate inference**

Implement:

```r
infer_application_rate_g_ha <- function(
  t0_concentration_ug_kg,
  depth_top_mm,
  depth_bottom_mm,
  bulk_density_g_cm3
) {
  soil_mass <- soil_mass_kg_ha(
    depth_top_mm,
    depth_bottom_mm,
    bulk_density_g_cm3
  )
  exp(mean(log(t0_concentration_ug_kg))) * soil_mass / 1e6
}
```

- [ ] **Step 7: Run tests and commit**

Run:

```bash
Rscript -e 'roxygen2::roxygenise("cltf"); testthat::test_local("R", filter = "observations")'
```

Expected: all observation tests PASS.

Commit:

```bash
git add R/R/observations.R R/tests/testthat/test-observations.R R/NAMESPACE R/man
git commit -m "feat: prepare herbicide observations and non-detects"
```

### Task 3: Implement temperature-based PET

**Files:**
- Create: `R/R/climate.R`
- Create: `R/tests/testthat/test-climate.R`

- [ ] **Step 1: Write R/Python reference-value tests**

Generate a five-day reference vector once from the current Python implementation:

```bash
python - <<'PY'
import sys
import pandas as pd
sys.path.insert(0, ".")
from cltf.climate import calc_et
data = pd.DataFrame({
    "jdays": [164, 165, 166, 167, 168],
    "Tmax": [18.4, 19.2, 20.1, 17.8, 16.5],
    "Tmin": [7.1, 6.8, 8.0, 5.6, 4.9],
})
print(calc_et(-32.85, data).tolist())
PY
```

Record the printed values in `test-climate.R` and assert `expect_equal(..., tolerance = 1e-6)`.

- [ ] **Step 2: Verify missing-function failure**

Run:

```bash
Rscript -e 'testthat::test_local("R", filter = "climate")'
```

Expected: FAIL because `pet_from_temperature()` is undefined.

- [ ] **Step 3: Port the current climate formulas**

Implement `pet_from_temperature(jday, tmax_c, tmin_c, latitude_deg, albedo = 0.18, surface_emissivity = 0.97, pt_constant = 1.26)` in `R/R/climate.R`.

The formulas and rounding must match:

- `cltf/climate.py::declination`;
- `potential_solar`;
- `transmissivity`;
- `atmospheric_emissivity`;
- `longwave`;
- `sat_vap_pressure_slope`;
- `pt_pet`;
- `calc_et`.

Return millimetres per day and reject `Tmax < Tmin`.

- [ ] **Step 4: Run climate tests and commit**

Run:

```bash
Rscript -e 'roxygen2::roxygenise("cltf"); testthat::test_local("R", filter = "climate")'
```

Expected: all tests PASS against the recorded Python values.

Commit:

```bash
git add R/R/climate.R R/tests/testthat/test-climate.R R/NAMESPACE R/man
git commit -m "feat: add temperature-based PET forcing"
```

### Task 4: Implement cache-first SILO access

**Files:**
- Create: `R/R/silo.R`
- Create: `R/tests/testthat/test-silo.R`

- [ ] **Step 1: Write parser and request-construction tests**

Test that `parse_silo_csv()` converts the fixture to:

```text
date        jdays rain_mm Tmax Tmin
2024-06-12  164   0.0     18.4 7.1
2024-06-13  165   3.4     19.2 6.8
```

Test that `round_silo_coordinate(-32.831016)` returns `-32.85`, and that a cache hit does not invoke a supplied downloader function.

- [ ] **Step 2: Implement request and parser functions**

Implement in `R/R/silo.R`:

```r
round_silo_coordinate <- function(value) round(value / 0.05) * 0.05

parse_silo_csv <- function(path) {
  raw <- utils::read.csv(path, check.names = FALSE)
  required <- c("Date", "T.Max", "T.Min", "Rain")
  if (!all(required %in% names(raw))) {
    stop("SILO CSV is missing required columns.", call. = FALSE)
  }
  date <- as.Date(as.character(raw$Date), format = "%Y%m%d")
  data.frame(
    date    = date,
    jdays   = as.integer(format(date, "%j")),
    rain_mm = as.numeric(raw$Rain),
    Tmax    = as.numeric(raw$T.Max),
    Tmin    = as.numeric(raw$T.Min)
  )
}
```

Implement `fetch_silo_point()` with:

- `SILO_USERNAME` and `SILO_PASSWORD`;
- `format=csv`;
- `comment=RXN`;
- coordinates rounded to 0.05°;
- `utils::download.file()` injected as a `downloader` argument;
- atomic download to a temporary file followed by `file.rename()`;
- a sidecar JSON metadata file;
- immediate return from existing cache unless `refresh = TRUE`.

- [ ] **Step 3: Run offline SILO tests**

Run:

```bash
Rscript -e 'roxygen2::roxygenise("cltf"); testthat::test_local("R", filter = "silo")'
```

Expected: all tests PASS without network access.

- [ ] **Step 4: Perform one credential-gated smoke test**

Run only when credentials are present:

```bash
Rscript -e 'if (nzchar(Sys.getenv("SILO_USERNAME")) && nzchar(Sys.getenv("SILO_PASSWORD"))) cltf::fetch_silo_point(-32.831016, 135.14494, as.Date("2024-06-12"), as.Date("2024-06-13"), tempfile())'
```

Expected: two daily rows and a cache metadata file.

- [ ] **Step 5: Commit**

```bash
git add R/R/silo.R R/tests/testthat/test-silo.R R/NAMESPACE R/man
git commit -m "feat: add cached SILO point retrieval"
```

### Task 5: Implement SLGA bulk-density access and depth weighting

**Files:**
- Create: `R/R/slga.R`
- Create: `R/tests/testthat/test-slga.R`

- [ ] **Step 1: Write fixture parsing and weighting tests**

Assert that the fixture produces:

```r
expect_equal(weight_bulk_density(bands, 0, 100)$estimate_g_cm3, 1.35)
expect_equal(weight_bulk_density(bands, 100, 300)$estimate_g_cm3, 1.4175)
```

Also test that a manual override returns `source = "manual_override"` without calling the network layer.

- [ ] **Step 2: Implement response parsing and overlap weighting**

Implement:

```r
parse_slga_bulk_density <- function(path) {
  payload <- jsonlite::fromJSON(path)
  bands <- payload$values
  data.frame(
    depth_top_mm     = bands$depth_top_cm * 10,
    depth_bottom_mm  = bands$depth_bottom_cm * 10,
    estimate_g_cm3   = bands$estimate_g_cm3,
    lower_g_cm3      = bands$lower_g_cm3,
    upper_g_cm3      = bands$upper_g_cm3
  )
}

weight_bulk_density <- function(bands, depth_top_mm, depth_bottom_mm) {
  overlap <- pmax(
    0,
    pmin(bands$depth_bottom_mm, depth_bottom_mm) -
      pmax(bands$depth_top_mm, depth_top_mm)
  )
  if (sum(overlap) != depth_bottom_mm - depth_top_mm) {
    stop("SLGA bands do not fully cover the requested interval.", call. = FALSE)
  }
  data.frame(
    estimate_g_cm3 = weighted.mean(bands$estimate_g_cm3, overlap),
    lower_g_cm3    = weighted.mean(bands$lower_g_cm3, overlap),
    upper_g_cm3    = weighted.mean(bands$upper_g_cm3, overlap)
  )
}
```

- [ ] **Step 3: Implement cache-first point access**

Implement `fetch_slga_bulk_density()` to:

- return an explicit manual value before any network work;
- discover current Bulk Density—Whole Earth products from the Raster Products API;
- select estimated, lower and upper products for 0–5, 5–15 and 15–30 cm;
- drill the requested point;
- store raw responses and a normalized JSON cache;
- fall back to `terra::rast("/vsicurl/...")` and `terra::extract()` when the point API fails;
- use `TERN_API_KEY` only in memory or a temporary header file;
- delete temporary authentication files with `on.exit(unlink(...), add = TRUE)`.

- [ ] **Step 4: Run offline tests**

Run:

```bash
Rscript -e 'roxygen2::roxygenise("cltf"); testthat::test_local("R", filter = "slga")'
```

Expected: all fixture and manual-override tests PASS.

- [ ] **Step 5: Commit**

```bash
git add R/R/slga.R R/tests/testthat/test-slga.R R/NAMESPACE R/man
git commit -m "feat: add cached SLGA bulk-density retrieval"
```

### Task 6: Implement replicate-level calibration

**Files:**
- Create: `R/R/calibration.R`
- Create: `R/tests/testthat/test-calibration.R`

- [ ] **Step 1: Write synthetic recovery tests**

Generate synthetic observations with known:

```r
truth <- c(mu = 1.0, sigma = 0.5, R_top = 2.0, R_bottom = 3.0, k = 0.005)
```

Use at least 12 times spanning both layer breakthrough phases and add deterministic lognormal perturbations with `set.seed(42)`. Assert:

- the returned objective is finite;
- all fitted parameters lie within bounds;
- the fitted objective is lower than the initial objective;
- repeated calls with the same seed produce identical results;
- `bound_hit` is reported for every parameter.

- [ ] **Step 2: Implement parameter unpacking and objective**

Implement `cltf_objective()` to:

- construct shared `mu` and `sigma` layers;
- run `simulate_cltf()`;
- join predictions by `days_since_application` and depth interval;
- use `analysis_concentration_ug_kg`;
- return `sqrt(mean((log(observed) - log(predicted))^2))`;
- return a finite penalty of `1e6` for invalid or non-finite predictions.

- [ ] **Step 3: Implement deterministic multistart fitting**

Implement `fit_cltf()` using `stats::optim(method = "L-BFGS-B")`, explicit lower/upper vectors, and a matrix of starts. Return:

- fitted parameters;
- objective;
- convergence code and message;
- start index;
- bound-hit flags using a relative tolerance;
- fitted predictions;
- all start results.

- [ ] **Step 4: Implement one-dimensional objective profiles**

Implement `profile_cltf_parameter(fit, parameter, grid, ...)` by fixing one parameter over `grid` and optimizing the remaining four parameters at each point.

- [ ] **Step 5: Run tests and commit**

Run:

```bash
Rscript -e 'roxygen2::roxygenise("cltf"); testthat::test_local("R", filter = "calibration")'
```

Expected: all calibration tests PASS.

Commit:

```bash
git add R/R/calibration.R R/tests/testthat/test-calibration.R R/NAMESPACE R/man
git commit -m "feat: add multistart CLTF calibration"
```

### Task 7: Implement base-R diagnostic plots

**Files:**
- Create: `R/R/plots.R`
- Create: `R/tests/testthat/test-plots.R`

- [ ] **Step 1: Write plot smoke tests**

For each plot function, open a temporary PNG device, call the function, close the device with `on.exit()`, and assert the file exists with non-zero size.

Required functions:

- `plot_climate_forcing()`;
- `plot_observed_fitted()`;
- `plot_residuals()`;
- `plot_mass_fractions()`;
- `plot_mass_balance()`;
- `plot_objective_profile()`;
- `plot_bulk_density()`.

- [ ] **Step 2: Implement shared graphics configuration**

Implement:

```r
cltf_plot_family <- function() {
  fonts <- names(grDevices::pdfFonts())
  if ("Arial" %in% fonts) "Arial" else "sans"
}

with_cltf_par <- function(code) {
  old <- graphics::par(
    family = cltf_plot_family(),
    mar    = c(4.2, 4.5, 1.2, 1.0),
    las    = 1
  )
  on.exit(graphics::par(old), add = TRUE)
  force(code)
}
```

Implement all seven plots with base graphics. Observed/fitted and residual plots use logarithmic concentration axes. Observed/fitted plots show replicate points and geometric means separately.

- [ ] **Step 3: Run plot tests and commit**

Run:

```bash
Rscript -e 'roxygen2::roxygenise("cltf"); testthat::test_local("R", filter = "plots")'
```

Expected: all plot files are generated successfully.

Commit:

```bash
git add R/R/plots.R R/tests/testthat/test-plots.R R/NAMESPACE R/man
git commit -m "feat: add CLTF diagnostic plots"
```

### Task 8: Build the SA Minnipa reference workflow

**Files:**
- Create: `R/examples/run_sa_reference.R`
- Create: `R/tests/testthat/test-sa-regression.R`
- Create: `R/reference/sa_minnipa_heavy_imazapic/README.md`
- Create: generated CSV, JSON and PNG files under the reference directory.

- [ ] **Step 1: Create the executable reference script with a compliant header**

The script must:

1. accept `--workbook`, `--cache-dir`, and `--output-dir`;
2. import SA Heavy Imazapic observations;
3. read cached SILO data or retrieve it when credentials exist;
4. read cached SLGA bulk density or use supplied overrides;
5. calculate ET and cumulative infiltration;
6. infer application rate from top-layer T0 if no explicit rate is supplied;
7. exclude those T0 rows from calibration;
8. fit `mu`, `sigma`, `R_top`, `R_bottom`, and `k`;
9. write prepared observations, forcing, bulk density, predictions, fitted parameters, fit diagnostics and metadata;
10. generate all required plots.

The metadata JSON must include:

- package version and R version;
- `tools::md5sum()` checksums for prepared observations, forcing, and soil inputs;
- application-rate value and source;
- concentration unit and its provisional status;
- SILO request/returned coordinates and cache filename;
- SLGA product version, coordinates, depth bands and cache filename;
- parameter bounds, starts, convergence result, and objective value;
- effective porosity and water-balance settings.

- [ ] **Step 2: Run the reference workflow**

Run:

```bash
Rscript R/examples/run_sa_reference.R \
  --workbook "/g/data/ym05/herbicide/context/Herbicide Dissipation 2024.xlsx" \
  --cache-dir "R/reference/cache" \
  --output-dir "R/reference/sa_minnipa_heavy_imazapic"
```

Expected: the reference directory contains:

```text
bulk_density.csv
climate_forcing.csv
fit_diagnostics.csv
fit_parameters.csv
metadata.json
observations_prepared.csv
predictions.csv
plot_bulk_density.png
plot_climate.png
plot_mass_balance.png
plot_mass_fractions.png
plot_observed_fitted.png
plot_profiles.png
plot_residuals.png
```

- [ ] **Step 3: Add regression assertions**

In `test-sa-regression.R`, load the committed reference outputs and assert:

- all expected columns and row counts;
- every mass-balance row equals one within `1e-8`;
- all concentrations are finite and non-negative;
- fitted parameters remain within a declared absolute or relative tolerance;
- rerunning from committed cached fixtures reproduces predictions within `1e-8`.

- [ ] **Step 4: Document assumptions**

In the reference README state:

- concentration unit is provisionally µg/kg;
- source application rate is explicit or inferred;
- T0 rows used for inference are excluded from calibration;
- bulk-density product/version and coordinates;
- SILO grid coordinates;
- effective porosity fixed at 0.2;
- non-detect handling and any excluded zeros.

- [ ] **Step 5: Commit**

```bash
git add R/examples R/reference R/tests/testthat/test-sa-regression.R
git commit -m "feat: add SA Minnipa CLTF reference workflow"
```

### Task 9: Final documentation and verification

**Files:**
- Modify: `R/README.md`
- Modify: `README.md`

- [ ] **Step 1: Document credentials and offline operation**

Add:

```text
SILO_USERNAME=<email address>
SILO_PASSWORD=<alphanumeric API password>
TERN_API_KEY=<TERN data API key>
```

Document that cached reference runs require none of these variables.

- [ ] **Step 2: Document input and output schemas**

Document observation intervals, concentration units, forcing fields, SLGA metadata, fitted parameters, and reference artifacts.

- [ ] **Step 3: Regenerate documentation**

Run:

```bash
Rscript -e 'roxygen2::roxygenise("cltf")'
```

- [ ] **Step 4: Run the complete R suite**

Run:

```bash
Rscript -e 'testthat::test_local("R")'
R CMD build cltf
R CMD check cltf_0.1.0.tar.gz --no-manual
```

Expected: all tests PASS and `R CMD check` reports OK.

- [ ] **Step 5: Re-run the SA workflow offline**

Run with credentials unset:

```bash
env -u SILO_USERNAME -u SILO_PASSWORD -u TERN_API_KEY \
  Rscript R/examples/run_sa_reference.R \
  --workbook "/g/data/ym05/herbicide/context/Herbicide Dissipation 2024.xlsx" \
  --cache-dir "R/reference/cache" \
  --output-dir "/tmp/cltf-sa-verification"
```

Expected: successful completion using only cached external data.

- [ ] **Step 6: Verify the Python suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider apps/herbicide_workbench/tests
```

Expected: 14 tests PASS.

- [ ] **Step 7: Inspect repository state**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors and only intended documentation/source changes.

- [ ] **Step 8: Commit**

```bash
git add cltf README.md
git commit -m "docs: complete CLTF reference workflow documentation"
```

## Completion Gate

The R-first implementation is ready for Python translation only when:

- the numerical-core completion gate has passed;
- the full R package check reports OK;
- the SA case reruns without network access;
- mass balance holds for every output day;
- calibration diagnostics expose convergence, parameter bounds and objective profiles;
- concentration-unit and application-rate assumptions appear in metadata;
- committed reference outputs are stable enough to define Python-equivalence tests;
- the repository worktree is clean.
