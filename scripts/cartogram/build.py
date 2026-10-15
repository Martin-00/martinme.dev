"""Build the Mexico population cartogram from the official INEGI inputs (run fetch.py first).

1. Topology: project municipios to an equal-area projection, clean, and simplify each
   shared border once (mapshaper), so neighbours can never overlap.
2. Densify long straight edges so they can bend smoothly when the map deforms.
3. Cartogram: run cartogram-cpp on exactly these vertices (-S), with Census 2020 population.
4. Map every vertex to its cartogram position, so both maps share one topology (morph-ready).
5. Write one TopoJSON with both coordinate sets, plus metrics. Fail loudly if a check fails.
"""
import csv
import glob
import json
import math
import os
import subprocess
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import Polygon, shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(os.environ.get('CACHE_DIR', Path.home() / '.cache/martinme-cartogram'))
DATA, WORK = CACHE / 'data', CACHE / 'work'
ENGINE = Path(os.environ.get('CARTOGRAM_BIN', CACHE / 'cartogram-cpp/build/Release/cartogram'))
OUT = Path(os.environ.get('OUT_DIR', ROOT / 'src/assets/cartogram'))

# Albers equal-area with INEGI's own parallels and origin: areas on screen stay true.
ALBERS = ('+proj=aea +lat_0=12 +lon_0=-102 +lat_1=17.5 +lat_2=29.5 '
          '+x_0=2500000 +y_0=0 +ellps=GRS80 +units=m +no_defs')
SIMPLIFY_INTERVAL_M = int(os.environ.get('SIMPLIFY_INTERVAL_M', 100))
DENSIFY_MAX_SEGMENT_M = int(os.environ.get('DENSIFY_MAX_SEGMENT_M', 2000))
ENGINE_ARGS = os.environ.get('ENGINE_ARGS', '-N 8192').split()
QUANTIZATION = 100_000  # ~30 m per step: far below a pixel even zoomed in 20x
CENSUS_TOTAL = 126_014_024  # INEGI, Censo de Poblacion y Vivienda 2020


def census_population():
    path = glob.glob(str(DATA / 'iter/**/conjunto_de_datos_iter_00CSV20.csv'), recursive=True)[0]
    population = {}
    with open(path, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if row['LOC'] == '0000' and row['MUN'] != '000' and row['ENTIDAD'] != '00':
                population[row['ENTIDAD'] + row['MUN']] = int(row['POBTOT'])
    assert sum(population.values()) == CENSUS_TOTAL, 'census total mismatch'
    return population


def build_topology():
    """Equal-area, cleaned, topologically simplified municipios as unquantized TopoJSON."""
    target = WORK / f'normal_{SIMPLIFY_INTERVAL_M}m.json'
    subprocess.run([
        'npx', '-y', 'mapshaper@0.6', str(DATA / 'mg2020/00mun.shp'), 'encoding=utf-8',
        '-proj', ALBERS, '-clean',
        '-simplify', f'interval={SIMPLIFY_INTERVAL_M}', 'planar', 'keep-shapes',
        '-o', str(target), 'format=topojson', 'no-quantization',
    ], check=True, capture_output=True)
    return json.loads(target.read_text())


def densify(arc, max_len):
    out = [arc[0]]
    for (x0, y0), (x1, y1) in zip(arc, arc[1:]):
        steps = max(1, math.ceil(math.hypot(x1 - x0, y1 - y0) / max_len))
        out += [[x0 + (x1 - x0) * k / steps, y0 + (y1 - y0) * k / steps] for k in range(1, steps + 1)]
    return out


def arc_coords(arcs, index):
    return arcs[index] if index >= 0 else arcs[~index][::-1]


def ring_coords(arcs, ring):
    coords = []
    for index in ring:
        part = arc_coords(arcs, index)
        coords += part if not coords else part[1:]
    return coords


def polygons(arcs, geometry):
    rings = [geometry['arcs']] if geometry['type'] == 'Polygon' else geometry['arcs']
    return [[ring_coords(arcs, r) for r in poly] for poly in rings]


def run_engine(topology, population):
    """Feed the engine the exact topology vertices; return {input vertex: cartogram vertex}."""
    features = []
    for g in topology['objects']['00mun']['geometries']:
        features.append({'type': 'Feature', 'properties': {'CVEGEO': g['properties']['CVEGEO']},
                         'geometry': {'type': 'MultiPolygon', 'coordinates': polygons(topology['arcs'], g)}})
    # Keep every run's input, output, and log: a run takes minutes, and REUSE_ENGINE=1 skips it.
    run_dir = WORK / f'engine_{SIMPLIFY_INTERVAL_M}m_{DENSIFY_MAX_SEGMENT_M}m'
    run_dir.mkdir(exist_ok=True)
    out_file = run_dir / 'pop_cartogram.geojson'
    if not (os.environ.get('REUSE_ENGINE') and out_file.exists()):
        (run_dir / 'in.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': features}))
        with open(run_dir / 'pop.csv', 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['CVEGEO', 'POBTOT'])
            w.writerows(sorted(population.items()))
        log = subprocess.run([str(ENGINE), 'in.geojson', 'pop.csv', '--skip_projection', '-S',
                              '--id', 'CVEGEO', '--area', 'POBTOT', *ENGINE_ARGS],
                             cwd=run_dir, capture_output=True, text=True)
        (run_dir / 'engine.log').write_text(log.stdout + log.stderr)
    result = json.loads(out_file.read_text())
    moved = {}
    by_id = {f['properties']['CVEGEO']: f for f in features}
    for f in result['features']:
        before = [r for p in by_id[f['properties']['CVEGEO']]['geometry']['coordinates'] for r in p]
        after = [r for p in f['geometry']['coordinates'] for r in p]
        assert [len(r) for r in before] == [len(r) for r in after], 'engine changed the vertex structure'
        for ring_before, ring_after in zip(before, after):
            for a, b in zip(ring_before, ring_after):
                key = (a[0], a[1])
                assert key not in moved or np.allclose(moved[key], b), 'shared vertex moved inconsistently'
                moved[key] = b
    return moved


def quantize(arcs):
    """Standard TopoJSON quantization + delta encoding."""
    pts = np.array([p for a in arcs for p in a])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    scale = (hi - lo) / (QUANTIZATION - 1)
    encoded = []
    for a in arcs:
        q = np.round((np.array(a) - lo) / scale).astype(np.int64)
        d = np.vstack([q[:1], np.diff(q, axis=0)])
        encoded.append(d.tolist())
    return encoded, {'scale': scale.tolist(), 'translate': lo.tolist()}


def decode(arcs, transform):
    sx, sy = transform['scale']
    tx, ty = transform['translate']
    return [(np.cumsum(np.array(a), axis=0) * [sx, sy] + [tx, ty]).tolist() for a in arcs]


def metrics(topology, arcs, population):
    geoms, pops, crossing_area = [], [], 0.0
    for g in topology['objects']['municipios']['geometries']:
        coords = polygons(arcs, g)
        geoms.append(shape({'type': 'MultiPolygon', 'coordinates': coords}))
        pops.append(population[g['properties']['id']])
        for ring in (r for p in coords for r in p if len(r) >= 4):
            poly = Polygon(ring)
            if not poly.is_valid:
                # A self-crossing ring counts each reversed loop negatively in its signed area;
                # the repaired shape counts it positively. Half the gap is the loops' area.
                crossing_area += (shapely.make_valid(poly).area - abs(shapely.area(poly))) / 2
    pops = np.array(pops, float)
    invalid = int(sum(not g.is_valid for g in geoms))
    geoms = [shapely.make_valid(g) for g in geoms]  # measure repaired shapes; report the raw count above
    areas = np.array([g.area for g in geoms])
    target = pops / pops.sum() * areas.sum()
    rel = np.abs(areas - target) / target
    tree = STRtree(geoms)
    overlap = sum(geoms[i].intersection(geoms[j]).area
                  for i in range(len(geoms)) for j in tree.query(geoms[i]) if j > i)
    return {
        'municipios': len(geoms),
        'population': int(pops.sum()),
        'area_error_median_pct': round(float(np.median(rel)) * 100, 2),
        'area_error_p90_pct': round(float(np.percentile(rel, 90)) * 100, 2),
        'area_error_max_pct': round(float(rel.max()) * 100, 2),
        'area_error_pop_weighted_pct': round(float((rel * pops / pops.sum()).sum()) * 100, 3),
        'invalid_polygons': invalid,
        'self_crossing_pct_of_area': round(crossing_area / areas.sum() * 100, 4),
        'overlap_pct_of_area': round(overlap / areas.sum() * 100, 4),
    }


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    population = census_population()
    topology = build_topology()
    topology['arcs'] = [densify(a, DENSIFY_MAX_SEGMENT_M) for a in topology['arcs']]
    moved = run_engine(topology, population)
    cartogram_arcs = [[moved[(x, y)] for x, y in a] for a in topology['arcs']]

    normal_q, normal_t = quantize(topology['arcs'])
    carto_q, carto_t = quantize(cartogram_arcs)
    geometries = []
    for g in topology['objects']['00mun']['geometries']:
        p = g['properties']
        geometries.append({'type': g['type'], 'arcs': g['arcs'], 'properties': {
            'id': p['CVEGEO'], 'name': p['NOMGEO'], 'state': p['CVE_ENT'],
            'population': population[p['CVEGEO']]}})
    result = {'type': 'Topology', 'transform': normal_t, 'arcs': normal_q,
              'cartogram': {'transform': carto_t, 'arcs': carto_q},
              'objects': {'municipios': {'type': 'GeometryCollection', 'geometries': geometries}}}

    checks = {'normal': metrics(result, decode(normal_q, normal_t), population),
              'cartogram': metrics(result, decode(carto_q, carto_t), population),
              'settings': {'simplify_interval_m': SIMPLIFY_INTERVAL_M,
                           'densify_max_segment_m': DENSIFY_MAX_SEGMENT_M,
                           'engine_args': ENGINE_ARGS,
                           'points': sum(len(a) for a in normal_q)}}
    c = checks['cartogram']
    assert c['population'] == CENSUS_TOTAL and c['municipios'] == 2469
    (OUT / 'mexico.topo.json').write_text(json.dumps(result, separators=(',', ':')))
    (OUT / 'metrics.json').write_text(json.dumps(checks, indent=2) + '\n')
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
