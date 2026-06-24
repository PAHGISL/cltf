# CLTF Model Design

> Naming note: paths and APIs were updated on 2026-06-24 to the approved
> language-neutral CLTF monorepo convention. Git history preserves the original
> implementation terminology.

Date: 2026-06-23
Status: Approved design, pending written-spec review

## Objective

Develop a tested R implementation of the two-layer Convective Lognormal Transfer Function (CLTF) herbicide model before translating the verified model into Python and updating the web demonstration.

The primary prediction target is layer-average total resident herbicide concentration in dry soil. The R implementation will be the scientific reference implementation.

## Scope

This phase includes:

- a standalone R package under `R/`;
- two-layer CLTF transport driven by cumulative infiltration;
- a single herbicide-specific first-order degradation rate;
- layer-average concentration predictions;
- SILO point-climate retrieval and caching;
- SLGA bulk-density retrieval and caching;
- observation preparation from the current herbicide workbook;
- bounded calibration in log concentration space;
- base-R scientific plots;
- numerical, mass-balance, data-ingestion and regression tests.

This phase excludes:

- Python model changes;
- web-workbench changes;
- the advection-dispersion equation prototype;
- stochastic rainfall ensembles;
- preferential flow;
- a formal censored-data likelihood.

Those extensions should only be considered after the R reference cases are verified.

## Repository Structure

```text
Python CLTF/
├── cltf/
├── R/
│   ├── DESCRIPTION
│   ├── NAMESPACE
│   ├── R/
│   │   ├── cltf.R
│   │   ├── water_balance.R
│   │   ├── observations.R
│   │   ├── silo.R
│   │   ├── slga.R
│   │   ├── calibration.R
│   │   └── plots.R
│   ├── tests/
│   │   └── testthat/
│   ├── inst/
│   │   └── extdata/
│   ├── examples/
│   └── README.md
├── apps/
└── docs/
```

`R/` is a separate R package. A top-level `R/` directory is not used because it would conventionally imply that the entire repository is one R package.

## Scientific Definitions

### Coordinates and units

- Time, \(t\): days since application.
- Cumulative infiltration, \(Y(t)\): mm.
- Layer boundaries: mm below the soil surface.
- Applied herbicide mass, \(M_0\): g/ha.
- Bulk density, \(\rho_b\): g/cm³ or equivalently Mg/m³.
- Predicted resident concentration: µg/kg dry soil.

The source workbook does not state a concentration unit. Workbook values and plausible application-rate calculations strongly support µg/kg, equivalent to ng/g. The implementation will use the explicit field name `concentration_ug_kg`, while recording that the unit is inferred until confirmed by the laboratory or data provider.

### Observation layers

Observations represent intervals rather than point depths. Prepared data must contain:

- `depth_top_mm`;
- `depth_bottom_mm`.

Examples:

- SA `10cm` means 0–100 mm;
- SA `30cm` means 100–300 mm;
- NSW `15cm` means 0–150 mm;
- NSW `30cm` means 150–300 mm.

The import layer will make these mappings explicit and test them. It will not pass a single nominal depth to the model.

## CLTF Transport Model

### Single-layer transfer distribution

For layer \(j\), let the infiltration requirement \(Y_j\) follow a lognormal distribution:

\[
f_j(y)=
\frac{1}{y\sigma_j\sqrt{2\pi}}
\exp\left[
-\frac{
\left\{\log\left(y/(R_jL_j)\right)-\log(\mu_j)\right\}^2
}{2\sigma_j^2}
\right],
\qquad y>0
\]

where:

- \(L_j\) is travel distance through the layer;
- \(R_j\) is the retardation factor;
- \(\mu_j>0\) is the lognormal scale term;
- \(\sigma_j>0\) is lognormal spread.

This corresponds to:

\[
\log Y_j \sim
N\left(\log(\mu_jR_jL_j),\sigma_j^2\right)
\]

and implements the agreed retardation form \(y/R\).

The initial calibration model will share \(\mu\) and \(\sigma\) across both layers while allowing `R_top` and `R_bottom` to differ. The internal API will accept layer-specific values so the model can be extended without changing its mathematical interface.

### Sequential two-layer transfer

Let:

- \(G_1(y)\) be the CDF for crossing the lower boundary of the top layer;
- \(G_2(y)\) be the CDF for crossing the lower layer after entering it;
- \(G_{12}(y)\) be the CDF of \(Y_1+Y_2\).

The sequential CDF is:

\[
G_{12}(y)=
\int_0^y f_1(u)G_2(y-u)\,du
\]

This CDF convolution, rather than a pointwise product of PDFs, is the primary calculation required for layer mass.

### Layer resident-mass fractions

Before degradation:

\[
P_{\mathrm{top}}(y)=1-G_1(y)
\]

\[
P_{\mathrm{bottom}}(y)=G_1(y)-G_{12}(y)
\]

\[
P_{\mathrm{below}}(y)=G_{12}(y)
\]

These quantities must be non-negative within numerical tolerance and satisfy:

\[
P_{\mathrm{top}}+
P_{\mathrm{bottom}}+
P_{\mathrm{below}}=1
\]

### Degradation

Degradation occurs over total elapsed time using one herbicide-specific rate:

\[
D(t)=\exp(-kt)
\]

Remaining mass fractions are:

\[
m_j(t)=D(t)P_j(Y(t))
\]

and the degraded fraction is:

\[
m_{\mathrm{degraded}}(t)=1-D(t)
\]

The complete balance is:

\[
m_{\mathrm{top}}+
m_{\mathrm{bottom}}+
m_{\mathrm{below}}+
m_{\mathrm{degraded}}=1
\]

### Initial and limiting conditions

At \(t=0\) or \(Y(t)=0\):

- top-layer transport fraction is 1;
- lower-layer transport fraction is 0;
- below-profile fraction is 0;
- degradation is applied according to elapsed time.

At very large infiltration:

- top and bottom transport fractions approach 0;
- below-profile transport fraction approaches 1.

The implementation will handle these limits analytically rather than evaluating `log(0)`.

## Layer-Average Resident Concentration

For an observation layer from \(z_a\) to \(z_b\), dry soil mass per hectare is:

\[
B_j =
10{,}000\,(z_b-z_a)\,\rho_{b,j}
\]

when depth is expressed in metres and bulk density in kg/m³.

Layer-average concentration is:

\[
\bar C_j(t)=
\frac{M_0\,10^6\,m_j(t)}{B_j}
\frac{0.2}{\theta_e}
\]

where:

- \(10^6\) converts g to µg;
- \(\theta_e\) is effective porosity;
- \(0.2/\theta_e\) is the agreed normalized empirical concentration scaling.

Effective porosity does not alter travel or mass partitioning. Mass conservation is assessed before applying this concentration scaling.

The default is \(\theta_e=0.2\). Effective porosity will remain fixed during initial calibration and will be varied only in sensitivity analysis because it is confounded with application mass and bulk density.

### Applied mass

Absolute predictions require `application_rate_g_ha`.

Source priority is:

1. explicit recorded application rate;
2. application rate supplied in site configuration;
3. provisional inference from the geometric mean top-layer T0 concentration and selected bulk density.

Any inferred application rate will be flagged in outputs. T0 observations used to infer application mass will not simultaneously contribute independent information to calibration.

## Infiltration and the Generalized Inverse

### Water balance

Daily infiltration is:

\[
I_d =
\max\left(
R_d + Q_d - \alpha E_d,
0
\right)
\]

where:

- \(R_d\) is rainfall;
- \(Q_d\) is irrigation;
- \(E_d\) is potential evapotranspiration;
- \(\alpha\) is the ET factor.

Cumulative infiltration is:

\[
Y(t)=\sum_{d\le t}I_d
\]

Uploaded or cached ET may be used directly. Otherwise, the package will reproduce the existing temperature-based Priestley–Taylor calculation so the R and later Python implementations can be compared.

### Generalized inverse

The utility inverse is the first-passage time:

\[
\tau(y)=\inf\{t:Y(t)\ge y\}
\]

For daily data it will return the first date or day index whose cumulative infiltration reaches or exceeds \(y\). It will not linearly interpolate across a zero-infiltration plateau.

This inverse is retained for diagnostics and future residence-time extensions. It is not used by the primary model because degradation depends on total elapsed time.

## Climate Data

### SILO

The package will retrieve point data from the official SILO Data Drill API using:

- latitude and longitude;
- start and finish dates;
- rainfall;
- maximum temperature;
- minimum temperature.

Design requirements:

- credentials come from `SILO_USERNAME` and `SILO_PASSWORD`;
- raw API responses are cached;
- tests use cached fixtures and never require network access;
- request coordinates, returned grid coordinates, request date and source metadata are retained;
- local CSV input is supported as an alternative;
- irrigation remains a separate forcing field.

The Queensland rainfall and irrigation workbook can be integrated after the initial SA reference case.

## Bulk Density

### SLGA source

Bulk Density—Whole Earth will be retrieved from current SLGA products hosted by TERN.

Primary point access will use the official SLGA Raster Products API. Authenticated
TERN Cloud Optimised GeoTIFF access through `terra` will be the fallback when the
point API cannot supply the required current product or uncertainty layer.

`SLGACloud` may be used for product and URL discovery, but the model will not depend exclusively on it because the package describes itself as alpha.

TERN authentication will use `TERN_API_KEY`. The key will be passed in memory or
through a temporary GDAL header file outside the repository.

The implementation must retain:

- requested coordinates;
- returned cell coordinates;
- SLGA product and version;
- depth band;
- estimated value;
- available lower and upper confidence limits;
- retrieval date;
- whether a manual override was used.

Manual bulk-density values override SLGA values.

### Depth weighting

Bulk density for an arbitrary observation interval is the overlap-weighted mean of SLGA depth bands.

For example:

\[
\rho_{0-10}=
\frac{
5\rho_{0-5}+5\rho_{5-15}
}{10}
\]

\[
\rho_{10-30}=
\frac{
5\rho_{5-15}+15\rho_{15-30}
}{20}
\]

The same overlap calculation will be used for uncertainty limits.

## Observation Preparation

Prepared replicate data will contain at least:

- site and soil identifiers;
- herbicide;
- application date;
- sample date;
- days since application;
- depth interval;
- replicate identifier;
- `concentration_ug_kg`;
- `is_non_detect`;
- `detection_limit_ug_kg`;
- application-rate source.

Replicates will be retained for calibration and plotted individually.

### Geometric summaries

Geometric means are:

\[
C_{\mathrm{geo}}=
\exp\left(
\operatorname{mean}(\log C_i)
\right)
\]

They are used for descriptive plots, not as a replacement for replicate-level calibration data.

For the initial implementation, confirmed non-detects use LOD/2 for geometric summaries and the calibration objective. Substitution is only allowed when an explicit detection limit is available. A numerical zero without detection-limit metadata is flagged and excluded from log calculations rather than silently replaced.

A censored lognormal likelihood is a later extension.

## Calibration

### Initial fitted parameters

The initial calibration fits:

- `mu`;
- `sigma`;
- `R_top`;
- `R_bottom`;
- `k`.

Fixed inputs include:

- effective porosity;
- bulk density;
- layer geometry;
- application rate;
- water-balance settings.

### Objective

Calibration uses replicate-level log residuals:

\[
r_i=
\log C_{i,\mathrm{obs}}-
\log C_{i,\mathrm{pred}}
\]

The primary objective is RMSE in log concentration:

\[
\operatorname{RMSE}_{\log}=
\sqrt{
\frac{1}{n}\sum_i r_i^2
}
\]

No `log1p` transformation is used because the concentration unit and detection-limit treatment are explicit.

### Optimisation

- bounded optimisation;
- multiple dispersed starting points;
- deterministic seed where stochastic starts are generated;
- convergence status retained;
- parameter-bound hits reported;
- failed or non-finite evaluations return a controlled penalty;
- objective profiles are generated for key parameters.

Initial calibration is site-, soil- and herbicide-specific. Pooling or hierarchical calibration is outside this phase.

## Numerical Methods

The package will implement:

1. an adaptive integration method for \(G_{12}(y)\);
2. a fixed-grid trapezoidal method as an independent numerical check.

The two methods must agree within documented tolerances across representative and difficult parameter sets.

The fixed grid will be preallocated. No vectors will be grown inside performance-critical loops.

Numerical outputs will be clipped only within a small tolerance around valid probability bounds. Materially negative probabilities, sums materially different from one or integration failures will raise informative errors.

## Plots

Plots will use base R and explicitly request Arial where available.

Required plots are:

1. rainfall, irrigation, ET and cumulative infiltration;
2. observed replicates, geometric means and fitted layer curves;
3. log-scale residual diagnostics;
4. top, bottom and below-profile mass fractions through time;
5. remaining, degraded and below-profile mass balance;
6. parameter objective profiles or sensitivity curves;
7. SLGA bulk-density estimates and uncertainty intervals by depth.

Plotting functions will return plot-ready data invisibly where practical so numerical content can be tested separately from rendering.

## Package Boundaries

### `cltf.R`

- single-layer PDF and CDF;
- two-layer convolution CDF;
- layer mass fractions;
- concentration conversion;
- time-series simulation.

### `water_balance.R`

- ET calculation;
- rainfall and irrigation combination;
- daily and cumulative infiltration;
- first-passage generalized inverse.

### `observations.R`

- workbook import;
- depth-interval mapping;
- unit and non-detect validation;
- replicate and geometric summaries;
- application-rate preparation.

### `silo.R`

- SILO request construction;
- credential handling;
- caching;
- response parsing;
- local-file fallback.

### `slga.R`

- product discovery;
- point extraction;
- caching;
- depth-overlap weighting;
- manual overrides.

### `calibration.R`

- parameter transformations and bounds;
- objective calculation;
- multistart optimisation;
- sensitivity and objective profiles.

### `plots.R`

- base-R plotting functions;
- shared Arial graphics configuration;
- plot-data preparation.

## Engineering Standards

- Every new R source, test and executable example will follow the workspace script-header standard.
- R code will use base-R style, `<-` assignment, two-space indentation, braces for all control flow and `snake_case` names.
- Paths will be explicit and constructed with `file.path()`; package code will not call `setwd()`.
- Base plotting is preferred; plotted text will explicitly request Arial and report when the font is unavailable.
- Numerical loops will preallocate known-size objects.
- Graphics devices, file connections and temporary authentication files will be closed or removed explicitly.
- Core package dependencies will remain minimal. Network and geospatial dependencies will be isolated so the transport model can run and test without them.

## Error Handling and Reproducibility

- Model functions reject missing, non-finite or physically invalid parameters.
- Dates must be ordered and unique after site-level aggregation.
- Cumulative infiltration must be non-decreasing.
- Network functions clearly distinguish authentication, service and parsing errors.
- Cached source files are immutable inputs; derived tidy files are written separately.
- Every fitted output records model version, input checksums, parameter bounds, software versions and data-source metadata.
- Credentials and API keys are never written to outputs or committed.

## Testing

### Mathematical tests

- lognormal PDF normalization;
- CDF monotonicity and limits;
- agreement with `plnorm`;
- layer fractions sum to one;
- zero-infiltration and \(t=0\) behavior;
- large-infiltration limiting behavior;
- degradation balance;
- non-negative fractions;
- known bulk-density concentration conversion;
- normalized effective-porosity scaling.

### Numerical tests

- adaptive and trapezoidal convolution agreement;
- narrow and wide lognormal distributions;
- high retardation;
- very small and large cumulative infiltration;
- controlled handling of integration failures.

### Water-balance tests

- rainfall-only events;
- irrigation events;
- ET thresholding;
- non-decreasing cumulative infiltration;
- first-passage inverse on plateaus.

### Data tests

- SA and NSW depth-interval mappings;
- concentration-unit field naming;
- replicate retention;
- non-detect rules;
- SILO cached-response parsing;
- SLGA cached-response parsing;
- depth-weighted bulk density.

### Calibration tests

- recovery from synthetic data;
- multistart determinism;
- bound-hit reporting;
- finite penalty behavior;
- exclusion of T0 data used to infer application mass.

### Regression test

One SA herbicide case will be stored as the initial R reference case. Expected forcing, layer fractions, concentrations and fitted parameters will be versioned with explicit tolerances. These outputs will later define Python-equivalence tests.

## Initial Reference Workflow

The first end-to-end case will be:

- site: SA Minnipa;
- soil: Heavy;
- herbicide: Imazapic;
- layers: 0–100 mm and 100–300 mm;
- climate: cached SILO point data;
- bulk density: SLGA Whole Earth with manual override support;
- concentration unit: provisionally µg/kg;
- effective porosity: fixed at 0.2.

After the SA case passes mathematical and regression validation, the workflow will be exercised for:

- SA Light;
- NSW Heavy and Light;
- additional herbicides;
- Queensland rainfall and irrigation treatments.

## Success Criteria

The R phase is complete when:

- all package tests pass;
- the two convolution methods agree within declared tolerances;
- every simulation satisfies mass balance;
- the SA reference case runs from cached inputs without network access;
- layer-average predictions use explicit dry-soil mass and depth intervals;
- calibration outputs convergence, bound and sensitivity diagnostics;
- required base-R plots are generated;
- all data-source assumptions, especially the provisional concentration unit, are visible in exported metadata;
- reference outputs are sufficient to implement independent Python-equivalence tests.

## Data-Service References

- SILO API reference: https://www.longpaddock.qld.gov.au/silo/api-documentation/reference
- SLGA developer utilities and Raster Products API: https://esoil.io/TERNLandscapes/Public/Pages/SLGA/GetData-Utils.html
- TERN SLGA Cloud Optimised GeoTIFF access: https://esoil.io/TERNLandscapes/Public/Pages/SLGA/GetData-COGSDataStore.html
- SLGACloud: https://github.com/AusSoilsDSM/SLGACloud
