# Herbicide Research Workbench

Streamlit app for research collaborators to upload herbicide persistence CSVs, adjust PyCLT parameters, run simulations, fit one selected case, visualise observed-versus-model curves, and download reproducible outputs.

## Run Locally

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-workbench.txt
streamlit run apps/herbicide_workbench/app.py
```

If you are on Gadi using the shared `geo_env`, install the requirements there or use the already configured environment:

```bash
cd /g/data/ym05/github/yuyi13/PyCLT
streamlit run apps/herbicide_workbench/app.py --server.address 0.0.0.0 --server.port 8501
```

## Streamlit Community Cloud

Deploy this repository from GitHub and set the app entrypoint to:

```text
apps/herbicide_workbench/app.py
```

The root `requirements.txt` includes the runtime packages needed by the app.

## Sample Data

Use the CSVs in `apps/herbicide_workbench/sample_data/` for a quick review run:

- Climate CSV: `daily_climate.csv`
- Observations CSV: `observed_rel.csv`
- Site config CSV: `site_config.csv`

After uploading them, select:

```text
SA_Minnipa / Heavy / Imazapic
```

## Expected Input Columns

Climate CSV requires:

```text
date,rain_mm,Tmax,Tmin
```

Recommended climate columns:

```text
site_id,date,jdays,days_since_application,rain_mm,Tmax,Tmin,et0_mm,cumulative_infiltration_mm
```

Observation CSV requires:

```text
site_id,soil_group,herbicide,depth_mm,days_since_application,relative_concentration
```

Alternatively, upload `sample_date` instead of `days_since_application`, and `concentration` instead of `relative_concentration` when top-layer T0 rows are available.

Site config CSV should include:

```text
site_id,soil_group,representative_lat,representative_lon,application_date,top_thickness_mm,reference_depth_mm,bottom_depth_mm
```

## Data Note

Only include review-safe sample data in the public repository. For collaborator-specific or sensitive datasets, use the upload controls at runtime rather than committing the data to GitHub.
