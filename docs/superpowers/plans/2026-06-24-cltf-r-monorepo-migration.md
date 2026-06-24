# CLTF R Package and Monorepo Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the verified R implementation from `rclt` to `cltf`, establish the approved monorepo layout, and preserve all R numerical behaviour before Python translation begins.

**Architecture:** Move the R package to top-level `R/`, move language-neutral examples and reference artifacts out of the package, and perform a clean API/class rename with no compatibility aliases. Generated R documentation is rebuilt from renamed source functions, and numerical regression tests prove the move is structural rather than scientific.

**Tech Stack:** R 4.5, testthat, roxygen2, base R, git

---

All new or revised R scripts and test files must retain the workspace-standard
header with `Last updated: 2026-06-24`.

## File Map

- Move `rclt/` to `R/`.
- Move `R/reference/` to top-level `reference/`.
- Move `R/examples/run_sa_reference.R` to `examples/R/run_sa_reference.R`.
- Create `examples/data/sa_minnipa_heavy_imazapic/README.md`.
- Modify all files under `R/R/`, `R/tests/`, and `R/README.md`.
- Regenerate `R/NAMESPACE` and all `R/man/*.Rd`.
- Modify root `README.md`.
- Modify historical files under `docs/superpowers/specs/` and `docs/superpowers/plans/`.
- Delete tracked Python and pytest cache directories.

### Task 1: Create an isolated migration worktree and baseline

**Files:**
- Inspect: repository root
- Test: existing R and Python suites

- [ ] **Step 1: Create the worktree**

```bash
git status --short
git worktree add \
  /home/603/yy4778/.config/superpowers/worktrees/PyCLT/cltf-monorepo \
  -b feature/cltf-monorepo
```

Expected: the main worktree is clean and the new worktree is on
`feature/cltf-monorepo`.

- [ ] **Step 2: Record the baseline**

```bash
Rscript -e 'testthat::test_local("rclt")'
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider \
  apps/herbicide_workbench/tests
```

Expected: 112 R tests and 14 Python workbench tests pass.

- [ ] **Step 3: Commit no files**

This task establishes the baseline only.

### Task 2: Move the R package and shared artifacts

**Files:**
- Create before move: `rclt/tests/testthat/test-repository-layout.R`
- Move: `rclt/` → `R/`
- Move: `R/reference/` → `reference/`
- Move: `R/examples/run_sa_reference.R` → `examples/R/run_sa_reference.R`
- Create: `examples/data/sa_minnipa_heavy_imazapic/README.md`

- [ ] **Step 1: Write a failing layout test**

Create `rclt/tests/testthat/test-repository-layout.R`:

```r
#!/usr/bin/env Rscript
# Script: test-repository-layout.R
# Objective: Verify the CLTF monorepo uses the approved R and shared-data layout.
# Author: Yi Yu
# Created: 2026-06-24
# Last updated: 2026-06-24
# Inputs: Repository-relative directories and package metadata.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("R", filter = "repository-layout").
# Dependencies: testthat, cltf

test_that("R package and shared references use approved paths", {
  repository_root <- normalizePath(
    testthat::test_path("..", "..", ".."),
    mustWork = TRUE
  )

  expect_true(file.exists(file.path(repository_root, "R", "DESCRIPTION")))
  expect_true(file.exists(file.path(repository_root, "reference")))
  expect_true(file.exists(file.path(
    repository_root,
    "examples",
    "R",
    "run_sa_reference.R"
  )))
  expect_false(file.exists(file.path(repository_root, "rclt")))
})
```

- [ ] **Step 2: Run the test and verify the old layout fails**

```bash
Rscript -e 'testthat::test_local("rclt", filter = "repository-layout")'
```

Expected: FAIL because `R/`, `reference/`, and `examples/R/` do not exist.

- [ ] **Step 3: Move files with history**

```bash
git mv rclt R
mkdir -p examples/R examples/data/sa_minnipa_heavy_imazapic
git mv R/reference reference
git mv R/examples/run_sa_reference.R examples/R/run_sa_reference.R
rmdir R/examples
```

Create `examples/data/sa_minnipa_heavy_imazapic/README.md`:

```markdown
# SA Minnipa Heavy/Imazapic shared inputs

The normalized observations, climate forcing, and soil inputs for this case
are prepared by `examples/R/run_sa_reference.R` and consumed by both language
implementations. Expected outputs are stored under
`reference/sa_minnipa_heavy_imazapic/`.
```

- [ ] **Step 4: Update moved script paths**

In `examples/R/run_sa_reference.R`, replace package and repository path setup
with:

```r
package_dir <- normalizePath(
  file.path(dirname(script_path()), "..", "..", "R"),
  mustWork = TRUE
)
repository_dir <- normalizePath(
  file.path(package_dir, ".."),
  mustWork = TRUE
)
```

Change default paths to:

```r
cache_dir <- file.path(repository_dir, "reference", "cache")
output_dir <- file.path(
  repository_dir,
  "reference",
  "sa_minnipa_heavy_imazapic"
)
climate_source <- file.path(
  repository_dir,
  "apps",
  "herbicide_workbench",
  "sample_data",
  "daily_climate.csv"
)
```

- [ ] **Step 5: Commit the structural move**

```bash
git add R reference examples
git commit -m "refactor: establish CLTF monorepo layout"
```

### Task 3: Rename R package metadata and package tests

**Files:**
- Modify: `R/DESCRIPTION`
- Modify: `R/tests/testthat.R`
- Modify: `R/tests/testthat/test-package.R`
- Modify: every header under `R/tests/testthat/`

- [ ] **Step 1: Change the package test first**

Update `R/tests/testthat/test-package.R`:

```r
test_that("package metadata is available", {
  expect_equal(as.character(utils::packageVersion("cltf")), "0.1.0")
})
```

Update `R/tests/testthat.R`:

```r
library(testthat)
library(cltf)

test_check("cltf")
```

- [ ] **Step 2: Run and verify the package-name failure**

```bash
Rscript -e 'testthat::test_local("R", filter = "package")'
```

Expected: FAIL because `DESCRIPTION` still declares `Package: rclt`.

- [ ] **Step 3: Rename package metadata**

Set the following fields in `R/DESCRIPTION`:

```text
Package: cltf
Title: Convective Lognormal Transfer Function for Herbicide Dynamics
Description: Independent R implementation of the two-layer convective
    lognormal transfer function for layer-average resident herbicide
    concentration.
```

Replace package references in test headers:

```text
testthat::test_local("R")
Dependencies: testthat, cltf
```

- [ ] **Step 4: Run the package test**

```bash
Rscript -e 'testthat::test_local("R", filter = "package")'
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add R/DESCRIPTION R/tests
git commit -m "refactor: rename R package to cltf"
```

### Task 4: Rename the R simulation and calibration API

**Files:**
- Modify: `R/R/simulate.R`
- Modify: `R/R/calibration.R`
- Modify: `R/R/plots.R`
- Modify: `R/R/cltf.R`
- Modify: `R/tests/testthat/helper-fixtures.R`
- Modify: affected R tests

- [ ] **Step 1: Rename test calls before production functions**

Apply these exact public-name substitutions in tests:

```text
simulate_rclt              → simulate_cltf
rclt_objective             → cltf_objective
fit_rclt                   → fit_cltf
profile_rclt_parameter     → profile_cltf_parameter
expect_rclt_plot           → expect_cltf_plot
rclt:::validate_layer_probabilities → cltf:::validate_layer_probabilities
```

Add class assertions:

```r
test_that("CLTF layers and fits use CLTF classes", {
  expect_s3_class(top_layer_fixture(), "cltf_layer")

  case <- synthetic_calibration_case()
  fit <- fit_cltf(
    observations               = case$observations,
    forcing                    = case$forcing,
    application_rate_g_ha      = 30,
    top_bulk_density_g_cm3     = 1.35,
    bottom_bulk_density_g_cm3  = 1.42,
    n_starts                   = 1,
    method                     = "trapezoid",
    n_steps                    = 301,
    control                    = list(maxit = 10)
  )
  expect_s3_class(fit, "cltf_fit")
})
```

- [ ] **Step 2: Run focused tests and verify missing functions**

```bash
Rscript -e 'testthat::test_local("R", filter = "simulate|calibration|plots|cltf")'
```

Expected: FAIL with missing `simulate_cltf()`, `fit_cltf()`, and related names.

- [ ] **Step 3: Rename production functions and internal helpers**

Apply this complete mapping:

```text
simulate_rclt                  → simulate_cltf
rclt_parameter_names           → cltf_parameter_names
normalize_rclt_parameters      → normalize_cltf_parameters
rclt_predict_concentrations    → cltf_predict_concentrations
rclt_objective                 → cltf_objective
generate_rclt_starts           → generate_cltf_starts
rclt_fit_predictions           → cltf_fit_predictions
rclt_bound_hits                → cltf_bound_hits
fit_rclt                       → fit_cltf
profile_rclt_parameter         → profile_cltf_parameter
rclt_plot_family               → cltf_plot_family
with_rclt_par                  → with_cltf_par
rclt_layer_label               → cltf_layer_label
class = "rclt_layer"           → class = "cltf_layer"
inherits(layer, "rclt_layer")  → inherits(layer, "cltf_layer")
class(fit) <- "rclt_fit"       → class(fit) <- "cltf_fit"
inherits(fit, "rclt_fit")      → inherits(fit, "cltf_fit")
```

Update all roxygen titles and prose from “RCLT” to “CLTF”.

- [ ] **Step 4: Run focused tests**

```bash
Rscript -e 'testthat::test_local("R", filter = "simulate|calibration|plots|cltf")'
```

Expected: all focused tests PASS.

- [ ] **Step 5: Commit**

```bash
git add R/R R/tests
git commit -m "refactor: standardize R CLTF API names"
```

### Task 5: Rename R headers, scripts, metadata, and reference prose

**Files:**
- Modify: all `R/R/*.R`
- Modify: all `R/tests/**/*.R`
- Modify: `examples/R/run_sa_reference.R`
- Modify: `R/README.md`
- Modify: `reference/**/*.md`
- Modify: `reference/**/*.json`

- [ ] **Step 1: Add a naming audit test**

Create `R/tests/testthat/test-naming.R`:

```r
#!/usr/bin/env Rscript
# Script: test-naming.R
# Objective: Prevent legacy RCLT and PyCLT names from returning to active R files.
# Author: Yi Yu
# Created: 2026-06-24
# Last updated: 2026-06-24
# Inputs: Active R package and shared reference text files.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("R", filter = "naming").
# Dependencies: testthat, cltf

test_that("active R text files contain no legacy branding", {
  repository_root <- normalizePath(
    testthat::test_path("..", "..", ".."),
    mustWork = TRUE
  )
  files <- c(
    list.files(file.path(repository_root, "R"), recursive = TRUE, full.names = TRUE),
    list.files(
      file.path(repository_root, "examples", "R"),
      recursive = TRUE,
      full.names = TRUE
    ),
    list.files(
      file.path(repository_root, "reference"),
      recursive = TRUE,
      full.names = TRUE
    )
  )
  files <- files[grepl("\\.(R|md|json|Rd)$", files)]
  text <- unlist(lapply(files, readLines, warn = FALSE), use.names = FALSE)

  expect_false(any(grepl("rclt|RCLT|pyclt|PyCLT", text)))
})
```

- [ ] **Step 2: Run and verify failure**

```bash
Rscript -e 'testthat::test_local("R", filter = "naming")'
```

Expected: FAIL while legacy names remain in headers and reference prose.

- [ ] **Step 3: Update active text**

Use these terms consistently:

```text
RCLT model       → CLTF model
RCLT package     → R CLTF package
PyCLT demo       → previous Python demo
RCLT reference   → CLTF reference
```

Update script usage examples to `Rscript examples/R/run_sa_reference.R` and
package usage to `library(cltf)`.

- [ ] **Step 4: Run naming and full R tests**

```bash
Rscript -e 'testthat::test_local("R", filter = "naming")'
Rscript -e 'testthat::test_local("R")'
```

Expected: naming test and full R suite PASS.

- [ ] **Step 5: Commit**

```bash
git add R examples/R reference
git commit -m "docs: remove legacy R package terminology"
```

### Task 6: Regenerate R package documentation

**Files:**
- Regenerate: `R/NAMESPACE`
- Regenerate: `R/man/*.Rd`

- [ ] **Step 1: Remove obsolete generated files**

```bash
git rm R/man/fit_rclt.Rd \
  R/man/profile_rclt_parameter.Rd \
  R/man/rclt_objective.Rd \
  R/man/simulate_rclt.Rd
```

- [ ] **Step 2: Run roxygen**

```bash
Rscript -e 'roxygen2::roxygenise("R")'
```

Expected exports include:

```text
export(cltf_objective)
export(fit_cltf)
export(profile_cltf_parameter)
export(simulate_cltf)
```

- [ ] **Step 3: Verify no obsolete exports**

```bash
rg -n 'rclt|RCLT|simulate_rclt|fit_rclt' R/NAMESPACE R/man
```

Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git add R/NAMESPACE R/man
git commit -m "docs: regenerate CLTF R package reference"
```

### Task 7: Update historical design and implementation documents

**Files:**
- Move: `docs/superpowers/specs/2026-06-23-rclt-model-design.md` →
  `docs/superpowers/specs/2026-06-23-cltf-model-design.md`
- Move: `docs/superpowers/plans/2026-06-23-rclt-core-implementation.md` →
  `docs/superpowers/plans/2026-06-23-cltf-core-implementation.md`
- Move: `docs/superpowers/plans/2026-06-23-rclt-data-calibration-implementation.md` →
  `docs/superpowers/plans/2026-06-23-cltf-data-calibration-implementation.md`

- [ ] **Step 1: Rename historical document paths**

```bash
git mv \
  docs/superpowers/specs/2026-06-23-rclt-model-design.md \
  docs/superpowers/specs/2026-06-23-cltf-model-design.md
git mv \
  docs/superpowers/plans/2026-06-23-rclt-core-implementation.md \
  docs/superpowers/plans/2026-06-23-cltf-core-implementation.md
git mv \
  docs/superpowers/plans/2026-06-23-rclt-data-calibration-implementation.md \
  docs/superpowers/plans/2026-06-23-cltf-data-calibration-implementation.md
```

- [ ] **Step 2: Apply the approved path and name mapping**

```text
rclt/                    → R/
library(rclt)            → library(cltf)
testthat::test_local("rclt") → testthat::test_local("R")
RCLT                     → CLTF
simulate_rclt            → simulate_cltf
fit_rclt                 → fit_cltf
rclt_objective           → cltf_objective
profile_rclt_parameter   → profile_cltf_parameter
```

Add a note at the top of each historical document:

```markdown
> Naming note: paths and APIs were updated on 2026-06-24 to the approved
> language-neutral CLTF monorepo convention. Git history preserves the original
> implementation terminology.
```

- [ ] **Step 3: Audit historical docs**

```bash
rg -n 'rclt|RCLT|pyclt|PyCLT' docs/superpowers
```

Expected: matches remain only in the 2026-06-24 migration specification and
implementation plans where removed names are explicitly discussed.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers
git commit -m "docs: align historical plans with CLTF naming"
```

### Task 8: Verify the renamed R package and clean generated caches

**Files:**
- Delete: tracked `pyclt/__pycache__/`
- Delete: root `.pytest_cache/`

- [ ] **Step 1: Remove generated caches**

```bash
git rm -r pyclt/__pycache__
rm -rf .pytest_cache
```

- [ ] **Step 2: Run the full R suite**

```bash
Rscript -e 'testthat::test_local("R")'
```

Expected: all tests PASS.

- [ ] **Step 3: Run package build and check**

```bash
R CMD build R
mkdir -p /tmp/cltf-r-check
R CMD check cltf_0.1.0.tar.gz --no-manual --output=/tmp/cltf-r-check
rm cltf_0.1.0.tar.gz
```

Expected: `Status: OK`.

- [ ] **Step 4: Run the SA reference offline**

```bash
rm -rf /tmp/cltf-sa-r
env -u SILO_USERNAME -u SILO_PASSWORD -u TERN_API_KEY \
  Rscript examples/R/run_sa_reference.R \
  --workbook "/g/data/ym05/herbicide/context/Herbicide Dissipation 2024.xlsx" \
  --cache-dir "reference/cache" \
  --output-dir "/tmp/cltf-sa-r"
```

Compare deterministic CSV outputs:

```bash
for file in observations_prepared.csv climate_forcing.csv bulk_density.csv \
  predictions.csv fit_parameters.csv fit_diagnostics.csv objective_profiles.csv
do
  cmp "reference/sa_minnipa_heavy_imazapic/$file" "/tmp/cltf-sa-r/$file"
done
```

Expected: all comparisons succeed.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test: verify renamed R CLTF package"
```

## Completion Gate

- `R/` is an installable package named `cltf`.
- R public APIs and classes use only approved CLTF names.
- Shared SA references are outside the R package.
- Historical documents use current paths and APIs.
- Full R tests pass and `R CMD check` reports `Status: OK`.
- The offline SA output is numerically unchanged.
- The feature worktree is clean.
