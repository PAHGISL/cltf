# rclt

Reference R implementation of the layered Convective Lognormal Transfer model.

## Units

- time: days
- cumulative infiltration and layer thickness: mm
- application rate: g/ha
- bulk density: g/cm³
- output concentration: µg/kg dry soil

## Core example

```r
library(rclt)

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

result <- simulate_rclt(
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
