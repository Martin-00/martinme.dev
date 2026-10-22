"""City references for the Monterrey cartogram: terrain, rivers, avenues, places and names, carried into
every shape by the same transformation the cartogram applied to the tracts.

Inputs: INEGI's street centerlines for Nuevo Leon (Marco Geoestadistico 2020, layer 19e), the Copernicus
DEM GLO-90 (four 1-degree tiles, ESA), river lines from OpenStreetMap (ODbL), and place coordinates from
Wikidata (CC0). Writes src/assets/monterrey-cartogram/{basemap.json, terrain.webp, basemap-metrics.json}.

The warp. Every tract vertex exists in each shape (that is how the page morphs), so the triangles between
those vertices are a piecewise-linear map from the land to each cartogram, exact at every vertex: a street
drawn along a tract edge stays on that edge in every shape. Beyond the tracts there are no vertices, so
there the displacement is extended harmonically (the smoothest field that agrees with the tracts) and
fades to the best uniform scale far from the city, the way a cartogram's sea does. The page triangulates
the same points (tract vertices plus the anchors written here) to warp the terrain.

Quality gates, written before any result was seen:
  - a tract vertex held out of the triangulation lands within 0.5 px (median) and 2 px (p95) of its true
    position on a 1,000-px-wide map;
  - folded (flipped) triangles cover at most 0.05% of the frame in any shape;
  - every landmark sits in or within 300 m of an urban tract, and every peak outside them.
Revised after the first run, and why: 77% of the folded area lay inside tracts, which cover the terrain,
so the fold gate now counts only folds outside the tracts (the total is still reported); and the airport
sat 1.8 km from the nearest tract, as an airfield should, so sites like it get 3 km. The fold gate decides
where terrain is drawn, the way the area gates decide which shapes appear: a shape whose warp folds more
than that shows plain ground instead (empty homes squeezes narrow gaps between tracts too hard to follow).
"""
import json
import math
import os
import struct
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import shapefile
import shapely
from PIL import Image
from pyproj import CRS, Transformer
from shapely.geometry import LineString, Polygon, box, shape
from shapely.ops import polylabel
from shapely.strtree import STRtree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import ALBERS, decode, polygons  # noqa: E402
from fetch import MG_URL, RemoteWindow, http_range, open_remote_zip  # noqa: E402
from metro import METRO  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(os.environ.get('CACHE_DIR', Path.home() / '.cache/martinme-cartogram'))
MG = CACHE / 'data/nl/mg2020'
DEM_DIR = CACHE / 'data/dem'
OSM_RIVERS = CACHE / 'data/osm/rivers.json'
OUT = ROOT / 'src/assets/monterrey-cartogram'

DEM_URL = 'https://copernicus-dem-90m.s3.amazonaws.com/{0}/{0}.tif'
DEM_TILES = [f'Copernicus_DSM_COG_30_{t}_DEM' for t in
             ('N25_00_W101_00', 'N25_00_W100_00', 'N26_00_W101_00', 'N26_00_W100_00')]
OVERPASS = 'https://overpass-api.de/api/interpreter'
RIVER_QUERY = '[out:json][timeout:90];way["waterway"="river"](25.25,-100.85,26.1,-99.8);out geom tags;'
USER_AGENT = 'martinme.dev cartogram (https://martinme.dev/monterrey/)'

FRAME_HALF_M = (68_000, 54_000)  # terrain and anchors, around the tracts' centre: covers every screen shape
TEXTURE_M = 70                   # metres per terrain pixel (the DEM has 90 m)
ANCHOR_M = 2_500                 # anchor lattice beyond the tracts (a 1.25 km lattice folded more, not less)
ANCHOR_CLEAR_M = 1_000           # anchors keep at least about this far from tract vertices
FIELD_M = 1_000                  # cell of the harmonic displacement field
FIELD_SCALE = 1.6                # field extent relative to the frame; displacement is zero at its edge
SIMPLIFY_M = 15
SCALES = {'land': 1.0, 'people': 0.1, 'empty': 0.1}  # integer step of the written coordinates, per shape

MAJOR = {'Avenida', 'Boulevard', 'Calzada', 'Carretera', 'Autopista', 'Periférico', 'Circunvalación',
         'Prolongación'}
UNNAMED = {'Ninguno', 'No Aplica', ''}
PREFIX = {'Avenida': 'Av.', 'Boulevard': 'Blvd.', 'Calzada': 'Calz.', 'Carretera': 'Carr.',
          'Prolongación': 'Prol.', 'Circunvalación': 'Circ.'}
HONORIFICS = ('Doctor ', 'Licenciado ', 'Ingeniero ', 'Profesor ', 'General ')
SPELLING = {'Ruíz Cortines': 'Ruiz Cortines'}  # INEGI's typo: the president was Adolfo Ruiz Cortines
AVENUES = 40
AVENUE_MIN_KM = 4

RIVERS = {'Río Santa Catarina': 'Río Santa Catarina', 'Río La Silla': 'Río La Silla',
          'Río Pesquería': 'Río Pesquería', 'Rio Pesqueria': 'Río Pesquería', 'Rio Salinas': 'Río Salinas',
          'Río San Juan': 'Río San Juan'}

# Wikidata (CC0), read 2026-10-22: id, kind, Spanish label, English label, latitude, longitude.
PLACES = [
    ('Q1778291', 'peak', 'Cerro de la Silla', 'Cerro de la Silla', 25.62778, -100.23905),
    ('Q5065013', 'peak', 'Cerro de las Mitras', 'Cerro de las Mitras', 25.71836, -100.43601),
    ('Q5065019', 'peak', 'Cerro del Topo Chico', 'Cerro del Topo Chico', 25.77344, -100.34980),
    ('Q20262772', 'peak', 'Chipinque', 'Chipinque', 25.60806, -100.35639),
    ('Q144040', 'range', 'Sierra Madre Oriental', 'Sierra Madre Oriental', 25.36667, -100.55000),
    ('Q383640', 'landmark', 'Obispado', 'Obispado', 25.67618, -100.34611),
    ('Q2265926', 'landmark', 'Macroplaza', 'Macroplaza', 25.66861, -100.30972),
    ('Q919965', 'landmark', 'Parque Fundidora', 'Fundidora Park', 25.67806, -100.28333),
    ('Q3058827', 'landmark', 'Estadio BBVA', 'Estadio BBVA', 25.67017, -100.24370),
    ('Q771800', 'landmark', 'Estadio Universitario', 'Estadio Universitario', 25.72281, -100.31206),
    ('Q29716', 'landmark', 'UANL', 'UANL', 25.72722, -100.31028),
    ('Q1343885', 'landmark', 'Tec de Monterrey', 'Tec de Monterrey', 25.65143, -100.29069),
    ('Q767660', 'site', 'Aeropuerto', 'Airport', 25.77833, -100.10639),
]
SHORT = {'009': 'Cadereyta', '019': 'San Pedro', '021': 'Escobedo', '025': 'Zuazua', '046': 'San Nicolás'}

GATES = {'heldout_median_px': 0.5, 'heldout_p95_px': 2.0, 'visible_folded_frame_pct': 0.05, 'landmark_max_m': 300,
         'site_max_m': 3000}


def ensure_inputs():
    """Streets from INEGI's state package (16 MB of it), 4 DEM tiles (20 MB), and OSM river lines (1 MB)."""
    if not (MG / '19e.shp').exists():
        info = open_remote_zip(RemoteWindow(MG_URL)).getinfo('19_nuevoleon.zip')
        n, e = struct.unpack('<HH', http_range(MG_URL, info.header_offset, info.header_offset + 29)[26:30])
        inner = open_remote_zip(RemoteWindow(MG_URL, info.header_offset + 30 + n + e, info.compress_size))
        for m in inner.infolist():
            name = m.filename.split('/')[-1]
            if name.startswith('19e.'):
                (MG / name).write_bytes(inner.read(m))
    DEM_DIR.mkdir(parents=True, exist_ok=True)
    for tile in DEM_TILES:
        if not (DEM_DIR / f'{tile}.tif').exists():
            urllib.request.urlretrieve(DEM_URL.format(tile), DEM_DIR / f'{tile}.tif')
    if not OSM_RIVERS.exists():
        OSM_RIVERS.parent.mkdir(parents=True, exist_ok=True)
        body = urllib.parse.urlencode({'data': RIVER_QUERY}).encode()
        request = urllib.request.Request(OVERPASS, body, {'User-Agent': USER_AGENT})
        OSM_RIVERS.write_bytes(urllib.request.urlopen(request, timeout=180).read())


def vertices(topo):
    """Unique tract vertices: land positions and, in the same order, their position in each cartogram."""
    land_arcs = decode(topo['arcs'], topo['transform'])
    shape_arcs = {s: decode(v['arcs'], v['transform']) for s, v in topo['shapes'].items()}
    seen, land, images = {}, [], {s: [] for s in shape_arcs}
    for i, arc in enumerate(land_arcs):
        for j, p in enumerate(arc):
            key = (round(p[0], 3), round(p[1], 3))
            if key in seen:
                continue
            seen[key] = len(land)
            land.append(p)
            for s in shape_arcs:
                images[s].append(shape_arcs[s][i][j])
    return np.array(land), {s: np.array(v) for s, v in images.items()}, land_arcs, shape_arcs


def similarity(land, image):
    """Best uniform scale and translation (no rotation: the engine never rotates)."""
    lm, im = land.mean(axis=0), image.mean(axis=0)
    a = np.sum((land - lm) * (image - im)) / np.sum((land - lm) ** 2)
    return a, im - a * lm


def harmonic(points, values, x0, y0, nx, ny):
    """Solve Laplace's equation on a grid: fixed where tract vertices fall, zero at the edge."""
    ix = ((points[:, 0] - x0) / FIELD_M).astype(int)
    iy = ((points[:, 1] - y0) / FIELD_M).astype(int)
    sums, counts = np.zeros((ny, nx, 2)), np.zeros((ny, nx))
    np.add.at(sums, (iy, ix), values)
    np.add.at(counts, (iy, ix), 1)
    fixed = counts > 0
    field = np.zeros((ny, nx, 2))
    field[fixed] = sums[fixed] / counts[fixed][:, None]
    fixed[0, :] = fixed[-1, :] = fixed[:, 0] = fixed[:, -1] = True
    parity = np.add.outer(np.arange(ny), np.arange(nx)) % 2
    omega = 2 / (1 + math.sin(math.pi / max(nx, ny)))
    for sweep in range(20_000):
        change = 0.0
        for colour in (0, 1):
            free = ~fixed & (parity == colour)
            average = 0.25 * (np.roll(field, 1, 0) + np.roll(field, -1, 0) + np.roll(field, 1, 1)
                              + np.roll(field, -1, 1))
            step = omega * (average - field)
            field[free] += step[free]
            change = max(change, float(np.abs(step[free]).max()))
        if change < 1e-6 * np.abs(values).max():
            break
    return field, sweep


def bilinear(field, x0, y0, points):
    """Sample a cell-centred grid at points."""
    fx = (points[:, 0] - x0) / FIELD_M - 0.5
    fy = (points[:, 1] - y0) / FIELD_M - 0.5
    i, j = np.floor(fy).astype(int), np.floor(fx).astype(int)
    v, u = (fy - i)[:, None], (fx - j)[:, None]
    return ((1 - v) * (1 - u) * field[i, j] + (1 - v) * u * field[i, j + 1]
            + v * (1 - u) * field[i + 1, j] + v * u * field[i + 1, j + 1])


def anchors(land, images, frame):
    """A lattice of points beyond the tracts, carried into each shape by the harmonic extension."""
    x0, y0, x1, y1 = frame
    xs = np.arange(x0, x1 + 1, ANCHOR_M)
    ys = np.arange(y0, y1 + 1, ANCHOR_M)
    grid = np.array([(x, y) for y in ys for x in xs], dtype=float)
    occupied = set(zip((land[:, 0] // ANCHOR_CLEAR_M).astype(int), (land[:, 1] // ANCHOR_CLEAR_M).astype(int)))
    cx, cy = (grid[:, 0] // ANCHOR_CLEAR_M).astype(int), (grid[:, 1] // ANCHOR_CLEAR_M).astype(int)
    keep = np.array([not any((a + da, b + db) in occupied for da in (-1, 0, 1) for db in (-1, 0, 1))
                     for a, b in zip(cx, cy)])
    points = grid[keep]
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    hx, hy = (x1 - x0) / 2 * FIELD_SCALE, (y1 - y0) / 2 * FIELD_SCALE
    fx0, fy0 = mx - hx, my - hy
    nx, ny = int(2 * hx / FIELD_M), int(2 * hy / FIELD_M)
    result, sweeps = {}, {}
    for s, image in images.items():
        a, t = similarity(land, image)
        field, sweeps[s] = harmonic(land, image - (a * land + t), fx0, fy0, nx, ny)
        result[s] = a * points + t + bilinear(field, fx0, fy0, points)
    return points, result, sweeps


class Warp:
    """Piecewise-linear map from the land to each shape, through a Delaunay triangulation of the land."""

    def __init__(self, land, images):
        self.land, self.images = land, images
        index = {(x, y): i for i, (x, y) in enumerate(land.tolist())}
        triangles = shapely.get_parts(shapely.delaunay_triangles(shapely.multipoints(land)))
        corners = [shapely.get_coordinates(t)[:3] for t in triangles]
        self.triangles = np.array([[index[(x, y)] for x, y in c.tolist()] for c in corners])
        self.tree = STRtree(triangles)

    def folded(self, shape_name, visible):
        """Triangles whose orientation flips from the land to the shape: how many, and the share of the
        frame they cover there, in all and where the terrain shows (the `visible` triangles)."""
        def signed(p):
            a, b, c = p[self.triangles[:, 0]], p[self.triangles[:, 1]], p[self.triangles[:, 2]]
            return 0.5 * ((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1]))
        before, after = signed(self.land), signed(self.images[shape_name])
        flipped = np.sign(before) != np.sign(after)
        total = np.abs(after).sum()
        return {'triangles': int(flipped.sum()), 'of': len(self.triangles),
                'frame_pct': round(float(100 * np.abs(after[flipped]).sum() / total), 4),
                'visible_frame_pct': round(float(100 * np.abs(after[flipped & visible]).sum() / total), 4)}

    def centroids(self):
        return self.land[self.triangles].mean(axis=1)

    def __call__(self, points):
        """Map land points; points outside the triangulation come back as NaN."""
        points = np.asarray(points, dtype=float)
        found = np.full(len(points), -1)
        query, tri = self.tree.query(shapely.points(points), predicate='intersects')
        order = np.unique(query, return_index=True)[1]
        found[query[order]] = tri[order]
        ok = found >= 0
        corners = self.triangles[found[ok]]
        a, b, c = (self.land[corners[:, k]] for k in range(3))
        v0, v1, v2 = b - a, c - a, points[ok] - a
        d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
        d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
        den = d00 * d11 - d01 * d01
        wb, wc = (d11 * d20 - d01 * d21) / den, (d00 * d21 - d01 * d20) / den
        wa = 1 - wb - wc
        out = {}
        for s, image in self.images.items():
            mapped = np.full((len(points), 2), np.nan)
            mapped[ok] = (wa[:, None] * image[corners[:, 0]] + wb[:, None] * image[corners[:, 1]]
                          + wc[:, None] * image[corners[:, 2]])
            out[s] = mapped
        return out


def heldout_errors(land, images, anchor_land, anchor_images, widths, fraction=0.1):
    """Leave some tract vertices out, map them through the rest, and measure the miss in px per 1,000."""
    rng = np.random.default_rng(1)
    out = rng.random(len(land)) < fraction
    warp = Warp(np.vstack([land[~out], anchor_land]),
                {s: np.vstack([images[s][~out], anchor_images[s]]) for s in images})
    mapped = warp(land[out])
    errors = {}
    for s in images:
        miss = np.linalg.norm(mapped[s] - images[s][out], axis=1)
        miss = miss[~np.isnan(miss)] / widths[s] * 1000
        errors[s] = {'median_px': round(float(np.median(miss)), 3), 'p95_px': round(float(np.percentile(miss, 95)), 3),
                     'max_px': round(float(miss.max()), 2), 'n': int(len(miss))}
    return errors


def encode(lines, shape_name):
    """Polylines as integer runs: the first point, then the steps between points."""
    step = SCALES[shape_name]
    out = []
    for line in lines:
        q = np.round(np.asarray(line) / step).astype(int)
        out.append(np.concatenate([q[:1], np.diff(q, axis=0)]).ravel().tolist())
    return out


def mapped_lines(warp, lines):
    """Map polylines into every shape, keeping only points the triangulation covers."""
    flat = np.vstack(lines)
    mapped = warp(flat)
    keep = ~np.isnan(mapped['people'][:, 0])
    result, start = {'land': []} | {s: [] for s in warp.images}, 0
    for line in lines:
        k = keep[start:start + len(line)]
        if k.sum() >= 2:
            result['land'].append(flat[start:start + len(line)][k])
            for s in warp.images:
                result[s].append(mapped[s][start:start + len(line)][k])
        start += len(line)
    return {s: encode(v, s) for s, v in result.items()}


def label(name, kind):
    for h in HONORIFICS:
        if name.startswith(h):
            name = name[len(h):]
    for wrong, right in SPELLING.items():
        name = name.replace(wrong, right)
    first = name.split()[0]
    if first in ('Carretera', 'Autopista', 'Libramiento', 'Avenida', 'Anillo', 'Periférico'):
        return name
    return f"{PREFIX.get(kind, '')} {name}".strip()


def avenues(warp, frame_box):
    """INEGI's named arteries, joined into connected roads, longest first."""
    reader = shapefile.Reader(str(MG / '19e'), encoding='latin-1')
    to_albers = Transformer.from_crs(CRS.from_wkt((MG / '19e.prj').read_text()), ALBERS, always_xy=True)
    lines, kinds = defaultdict(list), defaultdict(Counter)
    for sr in reader.iterShapeRecords(fields=['CVE_MUN', 'NOMVIAL', 'TIPOVIAL']):
        rec = sr.record
        if rec['CVE_MUN'] not in METRO or rec['TIPOVIAL'] not in MAJOR or rec['NOMVIAL'] in UNNAMED:
            continue
        x, y = to_albers.transform(*np.array(sr.shape.points).T)
        line = LineString(np.column_stack([x, y]))
        lines[rec['NOMVIAL']].append(line)
        kinds[rec['NOMVIAL']][rec['TIPOVIAL']] += line.length
    roads = []
    for name, parts in lines.items():
        merged = shapely.get_parts(shapely.line_merge(shapely.union_all(parts)))
        tree = STRtree(merged)
        group = list(range(len(merged)))

        def root(i):
            while group[i] != i:
                group[i] = group[group[i]]
                i = group[i]
            return i
        a, b = tree.query(merged, predicate='intersects')
        for i, j in zip(a, b):
            group[root(i)] = root(j)
        components = defaultdict(list)
        for i in range(len(merged)):
            components[root(i)].append(merged[i])
        for members in components.values():
            km = sum(m.length for m in members) / 1000
            if km >= AVENUE_MIN_KM:
                roads.append((km, name, members))
    roads.sort(key=lambda r: -r[0])
    result = []
    for km, name, members in roads[:AVENUES]:
        clipped = [shapely.intersection(m.simplify(SIMPLIFY_M), frame_box) for m in members]
        coords = [np.array(g.coords) for c in clipped for g in shapely.get_parts(c) if not g.is_empty]
        if coords:
            result.append({'name': label(name, kinds[name].most_common(1)[0][0]), 'km': round(km, 1),
                           'lines': mapped_lines(warp, coords)})
    return result


def rivers(warp, frame_box):
    """OpenStreetMap's river lines (INEGI's miss most of the Santa Catarina inside the city)."""
    to_albers = Transformer.from_crs('EPSG:4326', ALBERS, always_xy=True)
    by_name = defaultdict(list)
    for way in json.loads(OSM_RIVERS.read_text())['elements']:
        name = RIVERS.get(way.get('tags', {}).get('name'))
        if name and len(way.get('geometry', [])) >= 2:
            x, y = to_albers.transform([p['lon'] for p in way['geometry']], [p['lat'] for p in way['geometry']])
            by_name[name].append(LineString(np.column_stack([x, y])))
    result = []
    for name, parts in by_name.items():
        merged = shapely.intersection(shapely.line_merge(shapely.union_all(parts)).simplify(SIMPLIFY_M), frame_box)
        coords = [np.array(g.coords) for g in shapely.get_parts(merged) if not g.is_empty and g.length > 500]
        if coords:
            result.append({'name': name, 'km': round(sum(len(c) and LineString(c).length for c in coords) / 1000, 1),
                           'lines': mapped_lines(warp, coords)})
    return sorted(result, key=lambda r: -r['km'])


def places(warp, tracts_land):
    to_albers = Transformer.from_crs('EPSG:4326', ALBERS, always_xy=True)
    points = np.array([to_albers.transform(lon, lat) for *_, lat, lon in PLACES])
    mapped = warp(points)
    union = shapely.union_all(tracts_land)
    result, checks = [], []
    for k, (qid, kind, es, en, lat, lon) in enumerate(PLACES):
        distance = float(union.distance(shapely.Point(points[k])))
        checks.append({'id': qid, 'kind': kind, 'name': es, 'metres_from_tracts': round(distance)})
        result.append({'id': qid, 'kind': kind, 'es': es, 'en': en} | {
            s: [round(float(v), 1) for v in (points[k] if s == 'land' else mapped[s][k])] for s in ('land', *mapped)})
    return result, checks


def municipio_labels(topo, land_arcs, shape_arcs, names, tract_municipio):
    """A label point per municipio and shape: the pole of inaccessibility of its largest piece."""
    labels = {m: {'label': SHORT.get(m, names[m])} for m in names}
    for s, arcs in [('land', land_arcs)] + list(shape_arcs.items()):
        pieces = defaultdict(list)
        for g, m in zip(topo['objects']['tracts']['geometries'], tract_municipio):
            pieces[m].append(shape({'type': 'MultiPolygon', 'coordinates': polygons(arcs, g)}).buffer(0))
        for m, geoms in pieces.items():
            union = shapely.union_all(geoms)
            largest = max(shapely.get_parts(union), key=lambda p: p.area)
            point = polylabel(largest, tolerance=math.sqrt(largest.area) / 200)
            labels[m][s] = [round(point.x, 1), round(point.y, 1)]
    return labels


def read_dem():
    """Mosaic the four tiles into one longitude-latitude grid of elevations (metres)."""
    tiles = [Image.open(DEM_DIR / f'{t}.tif') for t in DEM_TILES]
    step = tiles[0].tag_v2[33550][0]
    raster_is_point = 2 in [tiles[0].tag_v2.get(34735, (0,))[i + 3] for i in range(0, len(tiles[0].tag_v2.get(34735, ())), 4)
                            if tiles[0].tag_v2.get(34735)[i] == 1025]
    lons = [t.tag_v2[33922][3] for t in tiles]
    lats = [t.tag_v2[33922][4] for t in tiles]
    west, north = min(lons), max(lats)
    size = tiles[0].size[0]
    width = round((max(lons) - west) / step) + size
    height = round((north - min(lats)) / step) + size
    mosaic = np.full((height, width), np.nan, dtype=np.float32)
    for t, lon, lat in zip(tiles, lons, lats):
        r, c = round((north - lat) / step), round((lon - west) / step)
        mosaic[r:r + t.size[1], c:c + t.size[0]] = np.asarray(t, dtype=np.float32)
    offset = 0.0 if raster_is_point else 0.5
    return mosaic, west + offset * step, north - offset * step, step


def terrain(frame):
    """A shaded-relief texture of the frame in the land's projection: dark, so the tracts stay the story."""
    dem, lon0, lat0, step = read_dem()
    x0, y0, x1, y1 = frame
    nx, ny = int((x1 - x0) / TEXTURE_M), int((y1 - y0) / TEXTURE_M)
    xs = x0 + (np.arange(nx) + 0.5) * TEXTURE_M
    ys = y1 - (np.arange(ny) + 0.5) * TEXTURE_M
    gx, gy = np.meshgrid(xs, ys)
    lon, lat = Transformer.from_crs(ALBERS, 'EPSG:4326', always_xy=True).transform(gx, gy)
    fc, fr = (lon - lon0) / step, (lat0 - lat) / step
    c, r = np.floor(fc).astype(int), np.floor(fr).astype(int)
    u, v = fc - c, fr - r
    z = ((1 - v) * (1 - u) * dem[r, c] + (1 - v) * u * dem[r, c + 1]
         + v * (1 - u) * dem[r + 1, c] + v * u * dem[r + 1, c + 1])
    dzdy, dzdx = np.gradient(z, TEXTURE_M)
    dzdy = -dzdy  # rows run south
    normal = np.dstack([-dzdx, -dzdy, np.ones_like(z)])
    normal /= np.linalg.norm(normal, axis=2, keepdims=True)
    shade = np.zeros_like(z)
    for azimuth, weight in ((315, 0.6), (270, 0.2), (360, 0.2)):
        a, alt = math.radians(azimuth), math.radians(42)
        light = np.array([math.sin(a) * math.cos(alt), math.cos(a) * math.cos(alt), math.sin(alt)])
        shade += weight * np.clip(normal @ light, 0, 1)
    flat = math.sin(math.radians(42))
    relief = np.clip(shade / flat, 0, 1.5)  # 1 on flat ground
    height = np.clip((z - 400) / 2000, 0, 1)[..., None]
    low, high = np.array([33, 38, 47]), np.array([92, 88, 81])
    colour = (low + (high - low) * height ** 0.75) * (0.4 + 0.6 * relief[..., None])
    image = Image.fromarray(np.clip(colour, 0, 255).astype(np.uint8), 'RGB')
    image.save(OUT / 'terrain.webp', quality=82, method=6)
    return {'size': [nx, ny], 'elevation_m': [round(float(np.nanmin(z))), round(float(np.nanmax(z)))]}


def main():
    ensure_inputs()
    topo = json.loads((OUT / 'monterrey.topo.json').read_text())
    variables = json.loads((OUT / 'variables.json').read_text())
    land, images, land_arcs, shape_arcs = vertices(topo)
    cx, cy = (land[:, 0].min() + land[:, 0].max()) / 2, (land[:, 1].min() + land[:, 1].max()) / 2
    frame = (round(cx - FRAME_HALF_M[0]), round(cy - FRAME_HALF_M[1]), round(cx + FRAME_HALF_M[0]),
             round(cy + FRAME_HALF_M[1]))
    frame_box = box(*frame)

    anchor_land, anchor_images, sweeps = anchors(land, images, frame)
    widths = {s: float(np.ptp(v[:, 0])) for s, v in images.items()}
    warp = Warp(np.vstack([land, anchor_land]), {s: np.vstack([images[s], anchor_images[s]]) for s in images})
    tracts_land = [shape({'type': 'MultiPolygon', 'coordinates': polygons(land_arcs, g)}).buffer(0)
                   for g in topo['objects']['tracts']['geometries']]
    centres = warp.centroids()
    visible = ~shapely.contains_xy(shapely.union_all(tracts_land), centres[:, 0], centres[:, 1])
    folds = {s: warp.folded(s, visible) for s in images}
    heldout = heldout_errors(land, images, anchor_land, anchor_images, widths)

    place_list, place_checks = places(warp, tracts_land)
    basemap = {
        'source': 'Streets: INEGI, Marco Geoestadistico 2020. Rivers: OpenStreetMap contributors (ODbL). '
                  'Terrain: Copernicus DEM GLO-90 (ESA). Places: Wikidata (CC0).',
        'scales': SCALES,
        'frame': list(frame),
        'terrain_shapes': ['land'] + [s for s, f in folds.items()
                                      if f['visible_frame_pct'] <= GATES['visible_folded_frame_pct']],
        'anchors': {'land': np.round(anchor_land).astype(int).ravel().tolist()} | {
            s: np.round(v / SCALES[s]).astype(int).ravel().tolist() for s, v in anchor_images.items()},
        'rivers': rivers(warp, frame_box),
        'avenues': avenues(warp, frame_box),
        'places': place_list,
        'municipios': municipio_labels(topo, land_arcs, shape_arcs, variables['municipios'],
                                       variables['tract_municipio']),
    }
    texture = terrain(frame)
    (OUT / 'basemap.json').write_text(json.dumps(basemap, ensure_ascii=False, separators=(',', ':')))

    landmark_miss = max(c['metres_from_tracts'] for c in place_checks if c['kind'] == 'landmark')
    site_miss = max(c['metres_from_tracts'] for c in place_checks if c['kind'] == 'site')
    peaks_inside = [c['name'] for c in place_checks if c['kind'] in ('peak', 'range') and c['metres_from_tracts'] == 0]
    passes = (all(h['median_px'] <= GATES['heldout_median_px'] and h['p95_px'] <= GATES['heldout_p95_px']
                  for h in heldout.values())
              and landmark_miss <= GATES['landmark_max_m'] and site_miss <= GATES['site_max_m']
              and not peaks_inside)
    metrics = {'gates': GATES, 'passes_gates': passes, 'terrain_shapes': basemap['terrain_shapes'],
               'heldout': heldout, 'folds': folds,
               'anchors': len(anchor_land), 'field_sweeps': sweeps, 'places': place_checks,
               'peaks_inside_tracts': peaks_inside, 'terrain': texture,
               'avenues': [(a['name'], a['km']) for a in basemap['avenues']],
               'rivers': [(r['name'], r['km']) for r in basemap['rivers']],
               'bytes': (OUT / 'basemap.json').stat().st_size, 'terrain_bytes': (OUT / 'terrain.webp').stat().st_size}
    (OUT / 'basemap-metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=1))
    print(json.dumps(metrics, ensure_ascii=False, indent=1))
    if not passes:
        raise SystemExit('basemap fails its quality gates')


if __name__ == '__main__':
    main()
