# Mexico cartogram pipeline

Rebuilds `src/assets/cartogram/mexico.topo.json` (both maps, one topology) and `metrics.json` (measured accuracy) from INEGI's official files.

```bash
python3 -m venv ~/.cache/martinme-cartogram/venv
~/.cache/martinme-cartogram/venv/bin/pip install -r scripts/cartogram/requirements.txt
scripts/cartogram/setup_engine.sh                                # one-time C++ build
~/.cache/martinme-cartogram/venv/bin/python scripts/cartogram/fetch.py
~/.cache/martinme-cartogram/venv/bin/python scripts/cartogram/build.py
```

## Sources

- **Boundaries:** INEGI, *Marco Geoestadistico. Censo de Poblacion y Vivienda 2020*, layer `00mun` (2,469 municipios). Using the census-year boundaries means every municipio matches its census count exactly. `fetch.py` reads the 3.1 GB national package in place with HTTP Range requests and downloads only the municipal layer (~40 MB).
- **Population:** INEGI, *Censo 2020, ITER*, municipal totals (`POBTOT`, `LOC = 0000`). Total: 126,014,024.
- **State attributes** (`src/assets/cartogram/states.json`): 2024 winning party and HDI per state, carried over from the original version of this map; their original sources were not recorded.

## Method

1. **Topology** (mapshaper): project to Albers equal-area (INEGI's own parallels, 17.5° and 29.5°), `-clean` the source slivers, and simplify each shared border once. Neighbours share every border point, so they cannot overlap.
2. **Densify** long straight edges, so borders can bend smoothly when the map deforms.
3. **Cartogram** (cartogram-cpp, Gastner, Seguy & More 2018): runs on exactly these points (`-S`, `--skip_projection`), so every point keeps a twin in the normal map. That one-to-one match is what makes the morph possible.
4. **One file, two coordinate sets:** standard TopoJSON plus a `cartogram` member with its own arcs and transform.
5. **Checks:** total population, municipio count, area error per municipio, invalid polygons, and overlap, written to `metrics.json`. The cartogram page reads its numbers from there.

## Engine notes

`setup_engine.sh` applies three local changes to cartogram-cpp (AGPL-3.0, used offline only):

- **Minimum target area:** the engine floors target areas at 0.01% of the total, which would inflate 1,184 of 2,469 municipios (11% of the map instead of their true 4.67%). The patch lowers the floor to 1e-7 (~13 people), below the smallest municipio (81 people).
- **Integration rounds:** raised from 100 to 400. At municipio level the engine hit the cap while still converging (each round cut the worst error by about a third).
- **Compiler:** Conan 2.16 predates Apple Clang 21, so the script registers that version.

The default grid cap (2,048) cannot resolve Mexico's density range (some municipios hold thousands of times more people per km² than others), so `build.py` runs with `-N 8192`.
