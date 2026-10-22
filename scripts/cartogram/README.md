# Mexico cartogram pipeline

Rebuilds `src/assets/cartogram/mexico.topo.json` (both maps, one topology) and `metrics.json` (measured accuracy) from INEGI's official files.

```bash
python3 -m venv ~/.cache/martinme-cartogram/venv
~/.cache/martinme-cartogram/venv/bin/pip install -r scripts/cartogram/requirements.txt
scripts/cartogram/setup_engine.sh                                # one-time C++ build
~/.cache/martinme-cartogram/venv/bin/python scripts/cartogram/fetch.py
~/.cache/martinme-cartogram/venv/bin/python scripts/cartogram/build.py      # population map
~/.cache/martinme-cartogram/venv/bin/python scripts/cartogram/variables.py  # color-by rates
SIZE_VAR=P3YM_HLI ~/.cache/martinme-cartogram/venv/bin/python scripts/cartogram/build.py  # a size-by map
```

## Sources

- **Boundaries:** INEGI, *Marco Geoestadistico. Censo de Poblacion y Vivienda 2020*, layer `00mun` (2,469 municipios). Using the census-year boundaries means every municipio matches its census count exactly. `fetch.py` reads the 3.1 GB national package in place with HTTP Range requests and downloads only the municipal layer (~40 MB).
- **Population:** INEGI, *Censo 2020, ITER*, municipal totals (`POBTOT`, `LOC = 0000`). Total: 126,014,024.
- **State names** (`src/assets/cartogram/states.json`). The v2 map's HDI and 2024 winning party per state had no recorded source, so they now live in `legacy/state_attributes_unsourced.json` and are not shown on the site.

## Method

1. **Topology** (mapshaper): project to Albers equal-area (INEGI's own parallels, 17.5° and 29.5°), `-clean` the source slivers, and simplify each shared border once. Neighbours share every border point, so they cannot overlap.
2. **Densify** long straight edges, so borders can bend smoothly when the map deforms.
3. **Cartogram** (cartogram-cpp, Gastner, Seguy & More 2018): runs on exactly these points (`-S`, `--skip_projection`), so every point keeps a twin in the normal map. That one-to-one match is what makes the morph possible.
4. **One file, two coordinate sets:** standard TopoJSON plus a `cartogram` member with its own arcs and transform.
5. **Checks:** total population, municipio count, area error per municipio, invalid polygons, and overlap, written to `metrics.json`. The cartogram page reads its numbers from there.

## Variables

`variables.py` holds one catalog of census rates, each with INEGI's own denominator (people aged 3+ for languages, aged 15+ for literacy, occupied homes with captured characteristics for housing). State and national values are INEGI's official rows, never averages of municipios, and the build fails unless every count sums exactly from municipios to states to the nation.

**Size by counts, color by rates.** Area can only mean "how many," so only counts get their own cartogram (`SIZE_VAR`), and only when they are distinct: at least 25% of the population map must double or halve. Indigenous-language speakers (87%), homes without any communication technology (74%), homes without electricity (66%), illiterate people (57%), and Afro-Mexican people (29%) qualify; people 65+ (5%) and without health coverage (4%) stay color-only. A size-by map ships only if it meets thresholds set before seeing results: median area error ≤ 2%, 90th percentile ≤ 5%, count-weighted ≤ 3%, overlap ≤ 0.5%, self-crossing area ≤ 0.1%.

## Monterrey

```bash
~/.cache/martinme-cartogram/venv/bin/python scripts/cartogram/metro.py    # tracts: land, people, empty homes
~/.cache/martinme-cartogram/venv/bin/python -I scripts/cartogram/basemap.py  # terrain, rivers, avenues, names
```

`metro.py` builds the metro's 2,185 urban tracts (INEGI layer `19a` and the census by tract and block) into `src/assets/monterrey-cartogram/`. `basemap.py` adds the city references and carries them into every shape through the tracts' own vertices: INEGI's arteries (layer `19e`), OpenStreetMap's rivers (INEGI's miss most of the Santa Catarina inside the city), Wikidata's peaks and landmarks, and Copernicus DEM GLO-90 terrain. Its gates (vertex accuracy, folds where terrain shows, places where they belong) are in its docstring; terrain appears only in shapes whose warp passes them.

## Engine notes

`setup_engine.sh` applies three local changes to cartogram-cpp (AGPL-3.0, used offline only):

- **Minimum target area:** the engine floors target areas at 0.01% of the total, which would inflate 1,184 of 2,469 municipios (11% of the map instead of their true 4.67%). The patch lowers the floor to 1e-7 (~13 people), below the smallest municipio (81 people).
- **Integration rounds:** raised from 100 to 400. At municipio level the engine hit the cap while still converging (each round cut the worst error by about a third).
- **Compiler:** Conan 2.16 predates Apple Clang 21, so the script registers that version.

The default grid cap (2,048) cannot resolve Mexico's density range (some municipios hold thousands of times more people per km² than others), so `build.py` runs with `-N 8192`.
