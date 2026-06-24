# SA Minnipa Heavy/Imazapic reference case

This directory is the first reproducible CLTF calibration case and will be the
numerical fixture for the later Python translation.

The target is layer-average resident concentration for 0–100 mm and 100–300 mm.
The workbook does not declare the analytical unit, so the reference records the
concentration as provisionally µg/kg dry soil. The application rate is inferred
from the geometric mean of the three positive 0–100 mm T0 replicates. All six T0
rows are excluded from calibration.

The climate forcing covers June 12 through October 28, 2024 at the SILO grid
cell centred on -32.85, 135.15. The committed cache was normalized from the
existing 2024 SILO gridded-archive extraction. A future
credentialed SILO Data Drill request should be compared against this cache
before replacing it.

Bulk density uses the SLGA v2 whole-earth 0–5, 5–15, and 15–30 cm band schema.
The current values are an explicitly labelled offline fixture because no TERN
API key was available during generation. They give depth-weighted densities of
1.35 g/cm³ for 0–100 mm and 1.4175 g/cm³ for 100–300 mm. Replace this fixture
with a credentialed point extraction before treating the case as final.

Effective porosity is fixed at 0.2 and only scales concentration. Degradation
uses total elapsed time. Daily infiltration is
`max(rain + irrigation - PET, 0)`, with no irrigation in this case.
Non-detect substitution is available in the preparation layer, but this case
contains no declared non-detects. Three reported zero values occur in the
bottom-layer T0 rows and are excluded.

## Calibration interpretation

Calibration uses all 25 positive non-T0 replicates in log space. Replicates are
not averaged for fitting; geometric means are shown only in the plots.

The current equations depend on `mu * R_top` and `mu * R_bottom`. Consequently,
`mu`, `R_top`, and `R_bottom` are not separately identifiable without an
external constraint or reparameterization. The multistart table and profiles
show this ridge. In addition, `sigma` reaches its current upper bound. Therefore
the fitted five-parameter vector is a diagnostic reference, not a defensible
set of independently estimated physical parameters.

The next scientific decision should be either:

1. fix `mu` or one retardation factor from independent information; or
2. calibrate the two identifiable transport scales directly.

## Artifacts

- `observations_prepared.csv`: replicate-level observations and inclusion flags.
- `climate_forcing.csv`: daily rain, PET, infiltration, and cumulative infiltration.
- `bulk_density.csv`: three standard SLGA depth bands.
- `predictions.csv`: daily mass fractions and resident concentrations.
- `fit_parameters.csv`: estimates, bounds, and bound-hit flags.
- `fit_diagnostics.csv`: all deterministic optimization starts and transport scales.
- `objective_profiles.csv`: one-dimensional re-optimized profiles.
- `metadata.json`: assumptions, provenance, checksums, bounds, and convergence.
- `plot_*.png`: seven base-R diagnostic plots.

## Rebuild

From the repository root:

```bash
Rscript examples/R/run_sa_reference.R \
  --workbook "/g/data/ym05/herbicide/context/Herbicide Dissipation 2024.xlsx" \
  --cache-dir "reference/cache" \
  --output-dir "reference/sa_minnipa_heavy_imazapic"
```

With the committed caches present, no SILO or TERN credentials are required.
