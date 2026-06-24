# CLTF Monorepo, Python Equivalence, and Web Application Design

## Status

Approved on 2026-06-24.

## Objective

Rename and restructure the repository around one language-neutral model identity,
implement a complete Python equivalent of the verified R model, establish shared
cross-language examples and reference outputs, and replace the legacy web
application with a Python CLTF application.

The project title is:

> Herbicide Dynamics Simulated by the Convective Lognormal Transfer Function
> (CLTF) in Python and R

The work is a clean breaking migration. No aliases, compatibility imports,
legacy adapters, or legacy relative-concentration schemas will remain.

## Naming

### Repository

- GitHub repository: `PAHGISL/cltf`
- Final local checkout: `/g/data/ym05/github/yuyi13/cltf`
- README heading: the exact title stated above
- Language-neutral model name: CLTF

The existing `PyCLT_logo.png` contains Python-specific branding. It will be
replaced by a language-neutral CLTF asset and all README and application
references will use the new asset.

### Packages

Both language ecosystems use the package name `cltf`:

```r
library(cltf)
```

```python
import cltf
```

R and Python package registries are independent, so the shared package name
does not create a technical collision. The shared name communicates that the
packages are independent implementations of one scientific model.

As checked on 2026-06-24, `cltf` was not present on CRAN or PyPI and
`PAHGISL/cltf` was not an existing GitHub repository. Availability is not a
reservation and will be rechecked before any future registry publication.

### Public model API

The public concepts will use CLTF consistently:

| Concept | R | Python |
|---|---|---|
| Layer definition | `cltf_layer()` | `CLTFLayer` |
| Single-layer density | `cltf_pdf()` | `cltf_pdf()` |
| Single-layer CDF | `cltf_cdf()` | `cltf_cdf()` |
| Sequential two-layer CDF | `cltf_two_layer_cdf()` | `cltf_two_layer_cdf()` |
| Layer probabilities | `cltf_layer_probabilities()` | `cltf_layer_probabilities()` |
| Simulation | `simulate_cltf()` | `simulate_cltf()` |
| Calibration objective | `cltf_objective()` | `cltf_objective()` |
| Calibration | `fit_cltf()` | `fit_cltf()` |
| Objective profile | `profile_cltf_parameter()` | `profile_cltf_parameter()` |

R result classes become `cltf_layer` and `cltf_fit`. Python uses explicit data
classes for layers, configuration, fits, and result tables where this improves
validation and typing.

All occurrences of `rclt`, `RCLT`, `pyclt`, `PyCLT`, and obsolete CLT-only
class names such as `CLTParameters` and `TwoLayerCLT` will be removed from the
active repository. The only permitted uses of `CLT` are historical or
scientific statements that intentionally distinguish the broader transfer
function concept from this CLTF implementation.

## Repository Structure

The final structure is:

```text
cltf/
├── R/                         # Independent R package: library(cltf)
│   ├── DESCRIPTION
│   ├── R/
│   ├── man/
│   ├── tests/
│   └── examples/
├── python/                    # Independent Python distribution
│   ├── pyproject.toml
│   ├── src/
│   │   └── cltf/
│   └── tests/
├── examples/
│   ├── data/                  # Shared language-neutral model inputs
│   ├── R/                     # R entry scripts
│   └── python/                # Python entry scripts
├── reference/                 # Shared outputs and tolerance declarations
├── apps/
│   └── herbicide_workbench/
├── docs/
├── README.md
└── cltf_logo.png
```

`R/` follows the normal convention for an R package directory. `python/` and
the Python import package remain lowercase according to Python conventions.

The R and Python packages are independently installable. Neither package calls
the other at runtime.

## Scientific Model Contract

The current verified R equations are the reference contract for both
implementations.

Both packages will provide:

- temperature-based Priestley–Taylor PET;
- daily threshold water balance and cumulative infiltration;
- generalized first-passage time for cumulative infiltration;
- validated single-layer lognormal transfer distributions;
- conservative sequential two-layer CLTF convolution;
- top, bottom, below-profile, and degraded mass fractions;
- one global first-order degradation rate over total elapsed time;
- layer-average resident concentration in provisionally µg/kg dry soil;
- effective porosity as a normalized concentration scale;
- soil mass from explicit layer intervals and whole-earth bulk density;
- observation preparation with explicit intervals and non-detect handling;
- replicate-level log-space calibration;
- deterministic multistart fitting, bound diagnostics, and objective profiles;
- cache-first SILO point climate retrieval;
- cache-first SLGA whole-earth bulk-density retrieval and depth weighting.

The canonical fitted parameter labels remain:

- `mu`;
- `sigma`;
- `R_top`;
- `R_bottom`;
- `k`.

The packages must expose the current identifiability limitation: the equations
identify `mu * R_top` and `mu * R_bottom`, rather than all three quantities
independently. Fit results must report these transport scales, bound hits, and
the identifiability note.

## Python Package Design

The Python package will be a full numerical translation, not a wrapper around
R. Its source modules will mirror scientific responsibilities rather than the
old package layout:

```text
python/src/cltf/
├── __init__.py
├── calibration.py
├── climate.py
├── concentration.py
├── observations.py
├── plotting.py
├── silo.py
├── simulation.py
├── slga.py
├── transport.py
└── water_balance.py
```

The translation will preserve equations, validation rules, units, limiting
conditions, cache schemas, and deterministic test fixtures. Python interfaces
will follow standard type hints, dataclasses, and lowercase module naming while
retaining the approved public CLTF function names.

The old `pyclt/` package and its relative-concentration model will be deleted
after the new package and tests are operational.

## Shared Examples and Reference Cases

### Primary showcase

The primary showcase is:

- Site: NSW Griffith
- Soil: Heavy
- Herbicide: Imazapic
- Observation layers: 0–150 mm and 150–300 mm
- Observation coverage: T0 plus four post-application dates through day 146
- Positive post-T0 observations: 24

This case is selected because it has complete two-layer coverage, a long
observation period, and relatively few zero values.

### Secondary regression case

SA Minnipa Heavy/Imazapic remains a secondary cross-site regression fixture. It
will not be discarded.

### Layout

```text
examples/
├── data/
│   ├── nsw_griffith_heavy_imazapic/
│   └── sa_minnipa_heavy_imazapic/
├── R/
└── python/

reference/
├── tolerances.json
├── nsw_griffith_heavy_imazapic/
└── sa_minnipa_heavy_imazapic/
```

Shared input files are language-neutral CSV or JSON. Language entry scripts
read the same inputs. Reference directories contain expected numerical outputs,
metadata, provenance, and plots needed for review.

Legacy BCG01 and synthetic examples may only remain if rewritten against the
new resident-concentration model and shared schemas. Incompatible legacy
relative-concentration examples and generated outputs will be removed.

## Cross-Language Conformance

The R package remains the initial scientific reference, but equivalence is
asserted through language-neutral fixtures rather than by calling R from
Python.

Conformance tests will compare:

- PET;
- daily and cumulative infiltration;
- first-passage times;
- single-layer PDF and CDF values;
- sequential two-layer CDF values;
- layer probabilities;
- degradation and complete mass balance;
- dry-soil mass and resident concentrations;
- NSW and SA daily predictions;
- prepared observations and application-rate inference;
- calibration objective values and fitted predictions.

Forward-model outputs will use strict absolute and relative tolerances declared
in `reference/tolerances.json`. Calibration parameter vectors will not require
exact equality because the model has a known scaling ridge. Calibration tests
will instead compare:

- objective values;
- fitted predictions;
- transport scales;
- convergence status;
- declared bounds and bound hits;
- reproducibility from fixed starts and seeds.

Both implementations must pass their native unit tests and the shared
conformance suite before the migration is complete.

## Observation Input Contract

The web application accepts one observation CSV as its only uploaded file.
Site-specific climate and soil inputs are retrieved or selected internally.

The normalized observation schema contains:

- `sample_date`;
- `depth_top_mm`;
- `depth_bottom_mm`;
- `concentration_ug_kg`;
- `is_t0` or a timepoint field that can unambiguously identify T0;
- optional `replicate_id`;
- optional `is_non_detect`;
- optional `detection_limit_ug_kg`;
- optional `application_date`.

The app infers the application date from T0 rows when `application_date` is not
provided. If neither an application date nor valid T0 rows are available, the
app requires the user to enter an application date before simulation.

The site, soil group, and herbicide are selected in the interface. They need
not be repeated in the CSV, although matching optional columns are validated
when supplied.

## Site Registry and External Data

The initial internal site registry contains only:

- NSW Griffith;
- SA Minnipa.

For each site it stores:

- display name and stable identifier;
- representative latitude and longitude;
- sampling layer intervals;
- expected SILO grid coordinates;
- default soil groups and available showcase herbicides;
- provenance notes.

The app uses server-side credentials and cache-first retrieval:

- `SILO_USERNAME`;
- `SILO_PASSWORD`;
- `TERN_API_KEY`;
- `MAPBOX_API_KEY` for satellite tiles.

Users do not enter API credentials. Cached showcase inputs keep both sites
operational when SILO or SLGA is temporarily unavailable. API failure messages
must distinguish cached fallback from live retrieval.

Bulk density is retrieved from SLGA and depth-weighted to model layers. An
advanced manual override remains available because the committed showcase
fixture is provisional and external services can fail.

## Web Application

The existing Streamlit application will be rebuilt around the Python `cltf`
package. It will not retain the old adapter, old parameterization, old
relative-concentration schema, or `C/C0` plots.

### Main workflow

1. Select NSW Griffith or SA Minnipa.
2. Select soil group and herbicide.
3. Load the bundled showcase observations or upload one observation CSV.
4. Review inferred application date, application rate, layer definitions, and
   bulk density.
5. Retrieve or reuse cached SILO and SLGA inputs.
6. Run a manual simulation or fit the CLTF model.
7. Review concentration, mass, residual, bound, and profile diagnostics.
8. Export normalized inputs, forcing, soil data, predictions, parameters,
   diagnostics, and metadata.

The NSW Griffith Heavy/Imazapic case is selected by default.

### Interactive map

The app shows a Google-map-like interactive landscape view:

- satellite imagery when a restricted Mapbox token is configured;
- pan and zoom;
- selected-site marker;
- coordinates and site label;
- SILO grid-cell marker;
- correctly attributed non-satellite fallback when a satellite token is not
  configured.

The map is informational and does not permit arbitrary site creation in this
phase.

### Residue assessment date

The interface uses the term **Residue assessment date**, not target sowing
date.

Behaviour:

- default to 90 days after application;
- provide 30-, 60-, and 90-day presets;
- allow a custom calendar date;
- constrain the date to the observed-climate simulation period;
- reject or explain dates before application;
- never extrapolate without climate forcing;
- draw a labelled vertical assessment line on relevant concentration, climate,
  infiltration, and mass plots;
- display top-layer concentration, bottom-layer concentration, and resident
  profile mass at the assessment date;
- include the selected date and results in exported metadata.

Helper text may state that the date can be set to a planned sowing date when
appropriate, but the default is a scenario date and not an agronomic
recommendation.

### Diagnostics

The app displays:

- climate and cumulative infiltration;
- replicate observations and geometric means;
- fitted layer-average resident concentrations;
- log residuals;
- top, bottom, below-profile, and degraded mass fractions;
- numerical mass-balance error;
- convergence and parameter-bound status;
- objective profiles;
- identifiability warnings and transport scales.

## Historical Analysis and Future Forecasting

This release supports historical analysis only. Climate forcing must be
available from observed SILO data or an existing cache.

Future work will add:

- historical SILO climatology construction;
- precomputed and cached site climatologies;
- multiple climate realizations;
- uncertainty intervals;
- future residue and planned-sowing-date scenarios.

These items will be documented as planned work but are outside this
implementation. The initial app must not silently extrapolate or present a
future climate projection.

## Migration Scope

The rename is thorough and includes:

- repository and checkout names;
- R package metadata and directory;
- Python distribution, import package, and directory;
- exported functions and classes;
- internal helper prefixes;
- tests, fixtures, snapshots, and test filters;
- script headers and usage examples;
- Streamlit labels, services, metadata, and exports;
- environment-variable names containing legacy branding;
- README files and package documentation;
- generated R documentation;
- shared reference metadata and cache provenance;
- historical specifications and implementation plans under
  `docs/superpowers/`;
- logos and image references;
- remote URL and local path documentation.

Generated caches such as `__pycache__` and `.pytest_cache` will not be retained
in version control.

The GitHub repository and local checkout are renamed last, after code,
documentation, application, and test verification. GitHub redirects from the
old repository URL are expected but will not be relied upon in active
documentation.

## Verification Gates

The migration is complete only when:

1. `rg` finds no unintended `rclt`, `RCLT`, `pyclt`, `PyCLT`, old import
   paths, or legacy API names.
2. The R package installs, its full test suite passes, and `R CMD check`
   reports `Status: OK`.
3. The Python package installs from `python/` and its complete unit suite
   passes.
4. Shared conformance tests pass for numerical primitives and both reference
   cases.
5. Every predicted mass-balance row sums to one within the declared tolerance.
6. The offline showcase runs from committed caches without credentials.
7. The credentialed data-service paths have injected or mocked tests that do
   not expose credentials.
8. The Streamlit application tests cover site selection, CSV validation,
   cached/API retrieval, map fallback, residue-assessment controls, fitting,
   plots, and exports.
9. The NSW Griffith showcase runs end to end in both languages.
10. The SA Minnipa secondary regression remains reproducible.
11. The GitHub repository is renamed to `PAHGISL/cltf`, the local checkout is
    `/g/data/ym05/github/yuyi13/cltf`, and the configured `origin` points to the
    new URL.

## Out of Scope

- Backward-compatible package aliases or import shims.
- Support for the legacy relative-concentration CSV schema.
- Runtime dependence between R and Python.
- Arbitrary user-selected map locations.
- Future weather forecasts or climatology scenarios.
- Claiming that the provisional workbook concentration unit or offline bulk
  density values have been externally confirmed.
