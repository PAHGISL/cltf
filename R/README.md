# cltf

Reference R implementation of the layered Convective Lognormal Transfer
Function (CLTF) model. This package is the scientific reference for subsequent
Python and web-demo updates.

## Units

- time: days
- cumulative infiltration and layer thickness: mm
- application rate: g/ha
- bulk density: g/cm³
- output concentration: µg/kg dry soil

## Core example

```r
library(cltf)

top <- cltf_layer(
  mu           = 1,
  sigma        = 0.5,
  retardation  = 2,
  thickness_mm = 100
)
bottom <- cltf_layer(
  mu           = 1.2,
  sigma        = 0.6,
  retardation  = 3,
  thickness_mm = 200
)

result <- simulate_cltf(
  time_days                   = 0:30,
  cumulative_infiltration_mm = seq(0, 150, length.out = 31),
  top_layer                  = top,
  bottom_layer               = bottom,
  decay_rate_day             = 0.005,
  application_rate_g_ha      = 20,
  top_bulk_density_g_cm3     = 1.3,
  bottom_bulk_density_g_cm3  = 1.4
)
```

Mass balance is evaluated before the normalized effective-porosity concentration
scale is applied.

## Data services and offline operation

Credentialed cache misses use:

```text
SILO_USERNAME=<email address>
SILO_PASSWORD=<alphanumeric API password>
TERN_API_KEY=<TERN data API key>
```

`fetch_silo_point()` rounds requests to the 0.05-degree SILO grid and retains
the raw CSV plus request metadata. `fetch_slga_bulk_density()` retrieves SLGA
v2 whole-earth bulk-density bands and normalizes them to 0–5, 5–15, and
15–30 cm. Manual SLGA overrides bypass network access.

The committed SA reference caches require none of these environment variables.

## Observation and forcing schemas

Prepared observations retain replicate rows and include:

- `days_since_application`;
- explicit `depth_top_mm` and `depth_bottom_mm`;
- `analysis_concentration_ug_kg`;
- non-detect, substituted-value, excluded-zero, and T0 flags.

The concentration unit is provisionally µg/kg dry soil because the source
workbook does not declare it. Calibration uses positive replicate-level values
in log space. Geometric means are used only for visualization.

Daily forcing includes date, elapsed time, rain, maximum/minimum temperature,
temperature-derived PET, daily thresholded infiltration, and cumulative
infiltration.

## Calibration interpretation

`fit_cltf()` fits shared `mu` and `sigma`, layer-specific `R_top` and
`R_bottom`, and one elapsed-time degradation rate `k`. It reports all starts,
convergence, bound hits, fitted replicate predictions, and objective profiles.

The present CLTF equations depend on `mu * R_top` and `mu * R_bottom`.
Therefore these two products are identifiable, but `mu` and both retardation
factors are not separately identifiable without an external constraint. The fit
object exposes the two transport scales and an explicit identifiability note.

## SA reference workflow

Run from the repository root:

```bash
Rscript examples/R/run_sa_reference.R \
  --workbook "/g/data/ym05/herbicide/context/Herbicide Dissipation 2024.xlsx" \
  --cache-dir "reference/cache" \
  --output-dir "reference/sa_minnipa_heavy_imazapic"
```

The workflow writes prepared observations, climate forcing, bulk density,
daily predictions, fit tables, metadata, objective profiles, and seven base-R
diagnostic plots. See
`reference/sa_minnipa_heavy_imazapic/README.md` for the current assumptions and
known limitations.
