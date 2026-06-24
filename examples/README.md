# Shared CLTF examples

The shared examples use normalized inputs under `examples/data/` and can run
offline. Climate forcing and bulk density are already materialized as committed
CSV/JSON files; the runners do not call SILO or SLGA.

## NSW Griffith Heavy/Imazapic

```bash
Rscript examples/R/run_reference_case.R \
  --case nsw_griffith_heavy_imazapic \
  --input-dir examples/data/nsw_griffith_heavy_imazapic \
  --output-dir /tmp/nsw-r

python examples/python/run_reference_case.py \
  --case nsw_griffith_heavy_imazapic \
  --input-dir examples/data/nsw_griffith_heavy_imazapic \
  --output-dir /tmp/nsw-python
```

## SA Minnipa Heavy/Imazapic

```bash
Rscript examples/R/run_reference_case.R \
  --case sa_minnipa_heavy_imazapic \
  --input-dir examples/data/sa_minnipa_heavy_imazapic \
  --output-dir /tmp/sa-r

python examples/python/run_reference_case.py \
  --case sa_minnipa_heavy_imazapic \
  --input-dir examples/data/sa_minnipa_heavy_imazapic \
  --output-dir /tmp/sa-python
```

NSW Griffith is the primary showcase case. SA Minnipa is retained as a
secondary regression case and still uses an explicitly labelled provisional
bulk-density fixture.
