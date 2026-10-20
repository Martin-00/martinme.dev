"""Metro Monterrey by urban census tract (AGEB): the land, its people, and its empty homes.

Inputs (INEGI, Censo de Poblacion y Vivienda 2020): urban tract boundaries (Marco Geoestadistico
2020, Nuevo Leon layer 19a) and the census by urban tract and block for Nuevo Leon.
Writes src/assets/monterrey-cartogram/{monterrey.topo.json, variables.json, metrics.json}.

Like the national map: one topology for every shape (so the page can morph between them), our own
vertices fed to the engine (-S), and quality gates written down before any result is seen. Tracts
with no or few residents get a small, disclosed minimum size, because shrinking them to nothing
makes their borders cross.
"""
import csv
import json
import os
import struct
import subprocess
import zipfile
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import Polygon, shape
from shapely.strtree import STRtree

from build import ALBERS, ENGINE, QUANTIZATION, densify, polygons, quantize, decode
from fetch import MG_URL, RemoteWindow, http_range, open_remote_zip

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(os.environ.get('CACHE_DIR', Path.home() / '.cache/martinme-cartogram'))
NL = CACHE / 'data/nl'
WORK = CACHE / 'work/metro'
OUT = Path(os.environ.get('OUT_DIR', ROOT / 'src/assets/monterrey-cartogram'))
CENSUS_URL = ('https://www.inegi.org.mx/contenidos/programas/ccpv/2020/datosabiertos/ageb_manzana/'
              'ageb_mza_urbana_19_cpv2020_csv.zip')
CENSUS_CSV = NL / 'census/ageb_mza_urbana_19_cpv2020/conjunto_de_datos/conjunto_de_datos_ageb_urbana_19_cpv2020.csv'

# Zona Metropolitana de Monterrey, Metropolis de Mexico 2020 (SEDATU, CONAPO, INEGI): 18 municipios.
# Their ITER populations sum to 5,341,177; the published total is 5,341,171.
METRO = ['001', '006', '009', '010', '012', '018', '019', '021', '025', '026',
         '031', '039', '041', '045', '046', '047', '048', '049']
SIMPLIFY_M, DENSIFY_M = 10, 150
ENGINE_ARGS = ['-N', '8192']
FLOOR_FRAC = 2e-5  # minimum target as a share of each shape's total
GATES = {'median_pct': 2, 'p90_pct': 5, 'weighted_pct': 3, 'overlap_pct': 0.5,
         'self_crossing_pct': 0.1, 'floor_extra_map_share_pct': 1}
SHAPES = {'people': 'POBTOT', 'empty': 'VIVPAR_DES'}

# id, group, label, description, numerator, denominator (None = INEGI's own average), unit
CATALOG = [
    ('empty', 'Housing', 'Empty homes', 'Share of private homes that are uninhabited', 'VIVPAR_DES', 'TVIVPAR', '%'),
    ('temporary', 'Housing', 'Homes for occasional use', 'Share of private homes used only part of the time', 'VIVPAR_UT', 'TVIVPAR', '%'),
    ('crowding', 'Housing', 'People per room', 'Average occupants per room in occupied homes', 'PRO_OCUP_C', None, 'per room'),
    ('household', 'Housing', 'People per home', 'Average occupants per occupied home', 'PROM_OCUP', None, 'per home'),
    ('car', 'Market', 'Homes with a car', 'Share of occupied homes with a car or pickup truck', 'VPH_AUTOM', 'VIVPARH_CV', '%'),
    ('computer', 'Market', 'Homes with a computer', 'Share of occupied homes with a computer, laptop, or tablet', 'VPH_PC', 'VIVPARH_CV', '%'),
    ('internet', 'Market', 'Homes with internet', 'Share of occupied homes with internet access', 'VPH_INTER', 'VIVPARH_CV', '%'),
    ('formal', 'Market', 'Covered by IMSS', 'Share of people affiliated with IMSS, mainly formal private-sector workers and their families', 'PDER_IMSS', 'POBTOT', '%'),
    ('highschool', 'People', 'Adults with high school or more', 'Share of people aged 18+ with at least some high school or beyond', 'P18YM_PB', 'P_18YMAS', '%'),
    ('schooling', 'People', 'Average years of schooling', 'Average grades completed by people aged 15+', 'GRAPROES', None, 'years'),
    ('children', 'People', 'Children under 15', 'Share of people aged 0 to 14', 'POB0_14', 'POBTOT', '%'),
    ('age65', 'People', 'Aged 65 and over', 'Share of people aged 65 or older', 'POB65_MAS', 'POBTOT', '%'),
    ('uninsured', 'People', 'No health coverage', 'Share of people not affiliated with any health service', 'PSINDER', 'POBTOT', '%'),
]


def ensure_inputs():
    """Download the census by tract (12 MB) and read only layer 19a from INEGI's state package."""
    if not CENSUS_CSV.exists():
        NL.mkdir(parents=True, exist_ok=True)
        target = NL / 'ageb_mza_urbana_19_cpv2020_csv.zip'
        if not target.exists():
            import urllib.request
            urllib.request.urlretrieve(CENSUS_URL, target)
        with zipfile.ZipFile(target) as z:
            z.extractall(NL / 'census')
    layer = NL / 'mg2020'
    if (layer / '19a.shp').exists():
        return
    layer.mkdir(parents=True, exist_ok=True)
    info = open_remote_zip(RemoteWindow(MG_URL)).getinfo('19_nuevoleon.zip')
    assert info.compress_type == zipfile.ZIP_STORED
    n, e = struct.unpack('<HH', http_range(MG_URL, info.header_offset, info.header_offset + 29)[26:30])
    inner = open_remote_zip(RemoteWindow(MG_URL, info.header_offset + 30 + n + e, info.compress_size))
    for m in inner.infolist():
        name = m.filename.split('/')[-1]
        if name.startswith('19a.'):
            (layer / name).write_bytes(inner.read(m))


def number(text):
    """INEGI marks suppressed or unavailable cells with '*' or 'N/D'; those are unknown, never zero."""
    try:
        return float(text)
    except ValueError:
        return None


def census():
    tracts, municipios = {}, {}
    with open(CENSUS_CSV, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if r['MUN'] not in METRO:
                continue
            if r['LOC'] == '0000' and r['AGEB'] == '0000' and r['MZA'] == '000':
                municipios[r['MUN']] = r  # the municipio's official total row (all its tracts and blocks)
            elif r['AGEB'] != '0000' and r['MZA'] == '000':
                tracts[r['ENTIDAD'] + r['MUN'] + r['LOC'] + r['AGEB']] = r
    return tracts, municipios


def rate(row, numerator, denominator):
    num = number(row[numerator])
    if denominator is None:
        return num
    den = number(row[denominator])
    return None if num is None or not den else round(100 * num / den, 2)


def build_topology():
    target = WORK / 'normal.json'
    subprocess.run([
        'npx', '-y', 'mapshaper@0.6', str(NL / 'mg2020/19a.shp'), 'encoding=latin1',
        '-filter', f'{json.dumps(METRO)}.indexOf(CVE_MUN) > -1', '-proj', ALBERS, '-clean',
        '-simplify', f'interval={SIMPLIFY_M}', 'planar', 'keep-shapes',
        '-o', str(target), 'format=topojson', 'no-quantization'], check=True, capture_output=True)
    topology = json.loads(target.read_text())
    topology['objects'] = {'tracts': next(iter(topology['objects'].values()))}
    topology['arcs'] = [densify(a, DENSIFY_M) for a in topology['arcs']]
    return topology


def targets_for(column, ids, tracts):
    raw = {i: number(tracts[i][column]) for i in ids}
    known = {i: v for i, v in raw.items() if v is not None}
    floor = sum(known.values()) * FLOOR_FRAC
    return {i: max(raw[i] or 0.0, floor) for i in ids}, raw, floor


def start_engine(name, topology, targets):
    """Start one engine run (or reuse an identical cached one); returns (process or None, run dir)."""
    features = [{'type': 'Feature', 'properties': {'CVEGEO': g['properties']['CVEGEO']},
                 'geometry': {'type': 'MultiPolygon', 'coordinates': polygons(topology['arcs'], g)}}
                for g in topology['objects']['tracts']['geometries']]
    run = WORK / f'engine_{name}'
    run.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({'type': 'FeatureCollection', 'features': features})
    csv_text = 'CVEGEO,VALUE\n' + ''.join(f'{i},{v:.3f}\n' for i, v in targets.items())
    cached = (run / 'pop_cartogram.geojson').exists() and (run / 'in.geojson').exists() \
        and (run / 'in.geojson').read_text() == payload and (run / 'pop.csv').read_text() == csv_text
    if cached:
        return None, run
    (run / 'in.geojson').write_text(payload)
    (run / 'pop.csv').write_text(csv_text)
    log = open(run / 'engine.log', 'w')
    proc = subprocess.Popen([str(ENGINE), 'in.geojson', 'pop.csv', '--skip_projection', '-S',
                             '--id', 'CVEGEO', '--area', 'VALUE', *ENGINE_ARGS], cwd=run, stdout=log, stderr=log)
    return proc, run


def moved_arcs(topology, run):
    result = json.loads((run / 'pop_cartogram.geojson').read_text())
    before_by_id = {g['properties']['CVEGEO']: polygons(topology['arcs'], g)
                    for g in topology['objects']['tracts']['geometries']}
    moved = {}
    for f in result['features']:
        before = [r for p in before_by_id[f['properties']['CVEGEO']] for r in p]
        after = [r for p in f['geometry']['coordinates'] for r in p]
        assert [len(r) for r in before] == [len(r) for r in after], 'engine changed the vertex structure'
        for rb, ra in zip(before, after):
            for a, b in zip(rb, ra):
                moved[(a[0], a[1])] = b
    return [[moved[(x, y)] for x, y in arc] for arc in topology['arcs']]


def measure(topology, arcs, ids, targets):
    geoms, crossing = [], 0.0
    for g in topology['objects']['tracts']['geometries']:
        coords = polygons(arcs, g)
        geoms.append(shape({'type': 'MultiPolygon', 'coordinates': coords}))
        for ring in (r for p in coords for r in p if len(r) >= 4):
            poly = Polygon(ring)
            if not poly.is_valid:  # half the gap between repaired and signed area = the reversed loops
                crossing += (shapely.make_valid(poly).area - abs(shapely.area(poly))) / 2
    invalid = int(sum(not g.is_valid for g in geoms))
    geoms = [shapely.make_valid(g) for g in geoms]
    t = np.array([targets[i] for i in ids])
    areas = np.array([g.area for g in geoms])
    rel = np.abs(areas - t / t.sum() * areas.sum()) / (t / t.sum() * areas.sum())
    tree = STRtree(geoms)
    overlap = sum(geoms[i].intersection(geoms[j]).area for i in range(len(geoms)) for j in tree.query(geoms[i]) if j > i)
    worst = int(np.argmax(rel))
    return {'median_pct': round(float(np.median(rel)) * 100, 2), 'p90_pct': round(float(np.percentile(rel, 90)) * 100, 2),
            'weighted_pct': round(float((rel * t / t.sum()).sum()) * 100, 2), 'max_pct': round(float(rel.max()) * 100, 1),
            'worst_tract': ids[worst], 'worst_tract_area_share_pct': round(float(areas[worst] / areas.sum() * 100), 4),
            'overlap_pct': round(overlap / areas.sum() * 100, 3), 'self_crossing_pct': round(crossing / areas.sum() * 100, 4),
            'invalid_polygons': invalid}, areas


def main():
    ensure_inputs()
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    tracts, municipios = census()
    assert len(municipios) == 18, 'expected the 18 metro municipios'
    topology = build_topology()
    ids = [g['properties']['CVEGEO'] for g in topology['objects']['tracts']['geometries']]
    assert all(i in tracts for i in ids) and len(ids) == len(tracts) == 2185, 'tract boundaries and census disagree'

    runs, info = {}, {}
    for name, column in SHAPES.items():
        targets, raw, floor = targets_for(column, ids, tracts)
        info[name] = (targets, raw, floor)
        runs[name] = start_engine(name, topology, targets)
    for proc, _ in runs.values():  # both shapes compute in parallel; the engine is single-threaded
        if proc:
            assert proc.wait() == 0, 'engine failed'

    normal_q, normal_t = quantize(topology['arcs'])
    result = {'type': 'Topology', 'transform': normal_t, 'arcs': normal_q, 'shapes': {},
              'objects': {'tracts': {'type': 'GeometryCollection', 'geometries': [
                  {'type': g['type'], 'arcs': g['arcs'], 'properties': {'id': g['properties']['CVEGEO']}}
                  for g in topology['objects']['tracts']['geometries']]}}}
    metrics = {'settings': {'simplify_m': SIMPLIFY_M, 'densify_m': DENSIFY_M, 'engine_args': ENGINE_ARGS,
                            'floor_frac': FLOOR_FRAC, 'quantization': QUANTIZATION}, 'gates': GATES, 'shapes': {}}
    land_areas = None
    for name, column in SHAPES.items():
        targets, raw, floor = info[name]
        arcs = moved_arcs(topology, runs[name][1])
        q, t = quantize(arcs)
        m, _ = measure(result, decode(q, t), ids, targets)
        known = [v for v in raw.values() if v is not None]
        m.update({'column': column, 'total': int(sum(known)), 'unknown_tracts': sum(v is None for v in raw.values()),
                  'floor_value': round(floor, 1), 'tracts_floored': sum((raw[i] or 0) < floor for i in ids),
                  'floor_extra_map_share_pct': round(sum(targets.values()) and
                                                     (sum(targets.values()) - sum(known)) / sum(targets.values()) * 100, 2),
                  'converged': 'Could not converge' not in (runs[name][1] / 'engine.log').read_text()})
        m['passes_gates'] = all(m[k] <= limit for k, limit in GATES.items())
        metrics['shapes'][name] = m
        if m['passes_gates']:
            result['shapes'][name] = {'transform': t, 'arcs': q}
        if land_areas is None:
            _, land_areas = measure(result, decode(normal_q, normal_t), ids, targets)

    # Facts for the page, computed here so the text can never drift from the data.
    pop = np.array([number(tracts[i]['POBTOT']) or 0 for i in ids])
    order = np.argsort(-(pop / land_areas))
    half = np.searchsorted(np.cumsum(pop[order]) / pop.sum(), 0.5)
    empty = {i: number(tracts[i]['VIVPAR_DES']) for i in ids}
    by_mun = {}
    for i in ids:
        mun = tracts[i]['MUN']
        e, p = by_mun.get(mun, (0.0, 0.0))
        by_mun[mun] = (e + (empty[i] or 0), p + pop[ids.index(i)])
    total_empty = sum(e for e, _ in by_mun.values())
    top = sorted(by_mun.items(), key=lambda kv: -kv[1][0])[:4]
    metrics['insights'] = {
        'tracts': len(ids), 'people': int(pop.sum()),
        'half_people_land_pct': round(float(land_areas[order[:half + 1]].sum() / land_areas.sum() * 100), 1),
        'empty_homes': int(total_empty),
        'empty_top': [{'municipio': municipios[m]['NOM_MUN'], 'empty_share_pct': round(e / total_empty * 100, 1),
                       'people_share_pct': round(p / pop.sum() * 100, 1)} for m, (e, p) in top],
        'tracts_over_30pct_empty': sum(1 for i in ids if (rate(tracts[i], 'VIVPAR_DES', 'TVIVPAR') or 0) > 30),
        # Two different reasons a tract has no empty-home share: INEGI withheld a count, or it has no homes.
        'empty_suppressed': sum(1 for i in ids if number(tracts[i]['VIVPAR_DES']) is None or number(tracts[i]['TVIVPAR']) is None),
        'tracts_without_homes': sum(1 for i in ids if number(tracts[i]['TVIVPAR']) == 0),
    }

    variables = {'source': 'INEGI, Censo de Poblacion y Vivienda 2020, census by urban tract (AGEB) and block, Nuevo Leon',
                 'ids': ids, 'tract_municipio': [tracts[i]['MUN'] for i in ids],
                 'tract_code': [tracts[i]['AGEB'] for i in ids],
                 'population': [int(number(tracts[i]['POBTOT']) or 0) for i in ids],
                 'municipios': {m: municipios[m]['NOM_MUN'] for m in METRO},
                 'variables': [], 'values': {}, 'municipio_values': {}}
    for vid, group, label, description, numerator, denominator, unit in CATALOG:
        values = [rate(tracts[i], numerator, denominator) for i in ids]
        known = [v for v in values if v is not None]
        lo, hi = np.percentile(known, [2, 98])
        variables['variables'].append({'id': vid, 'group': group, 'label': label, 'description': description,
                                       'unit': unit, 'numerator': numerator, 'denominator': denominator,
                                       'domain': [round(float(lo), 2), round(float(hi), 2)],
                                       'not_published': sum(v is None for v in values)})
        variables['values'][vid] = values
        variables['municipio_values'][vid] = {m: rate(municipios[m], numerator, denominator) for m in METRO}

    (OUT / 'monterrey.topo.json').write_text(json.dumps(result, separators=(',', ':')))
    (OUT / 'variables.json').write_text(json.dumps(variables, separators=(',', ':'), ensure_ascii=False))
    (OUT / 'metrics.json').write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({k: {g: v[g] for g in list(GATES) + ['passes_gates', 'converged', 'max_pct']}
                      for k, v in metrics['shapes'].items()}, indent=2))
    print(json.dumps(metrics['insights'], indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
