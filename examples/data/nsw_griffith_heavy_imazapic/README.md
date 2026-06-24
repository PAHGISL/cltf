# NSW Griffith Heavy/Imazapic shared inputs

This is the primary CLTF showcase case. The normalized observations, climate
forcing, and soil inputs are consumed by `examples/R/run_reference_case.R`,
`examples/python/run_reference_case.py`, and later web-app workflows.

The case uses:

- 0–150 mm as the top layer and 150–300 mm as the bottom layer;
- application date `2024-04-26`;
- observed forcing through `2024-09-19`;
- credentialed SLGA v2 whole-earth bulk density at the Griffith point;
- concentration unit recorded as provisionally inferred `ug/kg dry soil`.

Expected R reference outputs are stored under
`reference/nsw_griffith_heavy_imazapic/`.
