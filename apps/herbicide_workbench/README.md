# CLTF Herbicide Workbench

Streamlit app for running the Python `cltf` implementation against shared
resident-concentration herbicide examples or a single uploaded observation CSV.
The app selects a site/soil/herbicide case, prepares cached or API-refreshed
SILO climate and SLGA bulk density inputs, fits CLTF, and reports residue
concentrations at an assessment date.

## Run locally

From the repository root:

```bash
pip install -r requirements-workbench.txt
streamlit run apps/herbicide_workbench/app.py
```

On Gadi, from the current checkout:

```bash
cd /g/data/ym05/github/yuyi13/cltf
streamlit run apps/herbicide_workbench/app.py --server.address 0.0.0.0 --server.port 8501
```

The app imports the in-repository Python source from `python/src/cltf`.

## Demo sites

The app currently exposes two shared demo cases:

- NSW Griffith / Heavy / Imazapic
- SA Minnipa / Heavy / Imazapic

The default showcase is NSW Griffith. Shared inputs live under
`examples/data/`, so the app no longer carries a separate legacy sample-data
directory.

## Observation input

The only uploaded file is an observation CSV. Required columns are:

```text
sample_date
depth_top_mm
depth_bottom_mm
concentration_ug_kg
```

The file must also provide either `application_date` or enough T0 information
through `is_t0` or `timepoint`. Optional columns include:

```text
replicate_id
is_non_detect
detection_limit_ug_kg
site_id
soil_group
herbicide
```

Concentration units follow the shared sampled-data structure:
`µg/kg dry soil`. Non-detects are handled through half-detection-limit
substitution when a positive `detection_limit_ug_kg` is supplied.

## Climate and soil inputs

Climate and bulk density are not uploaded by the user.

- SILO climate is read from the committed shared cache by default.
- SLGA whole-earth bulk density is read from the committed shared cache by
  default.
- If refresh is enabled and credentials are available, the app attempts live API
  retrieval and records the source in the run metadata.
- If live retrieval fails or credentials are absent, the app falls back to the
  committed cache and displays a warning.

Environment variables:

```text
SILO_USERNAME
SILO_PASSWORD
TERN_API_KEY
MAPBOX_API_KEY
CLTF_WORKBENCH_CACHE_DIR
```

`MAPBOX_API_KEY` enables a satellite-streets map. Without it, the app uses an
attributed Carto fallback basemap.

## Residue assessment date

The default residue assessment date is 90 days beyond application, capped by the
observed SILO forcing period. The date is adjustable in the app and is shown as
a vertical marker on time-axis diagnostics.

At this stage the app is historical-analysis only: assessment dates cannot
extend beyond observed climate data. Forecasting via historical climatology is
kept as a future development item.

## Outputs

After a run, the app provides:

- fitted parameters and diagnostics;
- assessment concentration summary;
- observed/fitted, mass-fraction, mass-balance, residual, objective-profile,
  climate, and bulk-density plots;
- downloadable CSV/JSON artifacts with provenance metadata.
