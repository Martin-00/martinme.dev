"""Census 2020 rates for coloring the cartogram: one catalog, true denominators, official aggregates.

Writes src/assets/cartogram/variables.json. Municipio values come from ITER municipio rows; state and
national values come from INEGI's own state and national rows (never averaged rates), and every count
must sum exactly from municipios to states to the nation, or the build fails.
"""
import csv
import glob
import json
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(os.environ.get('CACHE_DIR', Path.home() / '.cache/martinme-cartogram'))
OUT = Path(os.environ.get('OUT_DIR', ROOT / 'src/assets/cartogram'))

# id, group, label, description, numerator, denominator (None = INEGI's own average), unit
CATALOG = [
    ('hli', 'Identity', 'Indigenous-language speakers', 'Share of people aged 3+ who speak an Indigenous language', 'P3YM_HLI', 'P_3YMAS', '%'),
    ('afro', 'Identity', 'Afro-Mexican', 'Share of people who consider themselves Afro-Mexican or Afro-descendant', 'POB_AFRO', 'POBTOT', '%'),
    ('age65', 'Age and health', 'Aged 65 and over', 'Share of people aged 65 or older', 'POB65_MAS', 'POBTOT', '%'),
    ('uninsured', 'Age and health', 'No health coverage', 'Share of people not affiliated with any public or private health service', 'PSINDER', 'POBTOT', '%'),
    ('disability', 'Age and health', 'Living with a disability', 'Share of people with a lot of difficulty, or unable, to see, hear, walk, remember, care for themselves, or communicate', 'PCON_DISC', 'POBTOT', '%'),
    ('illiteracy', 'Education', 'Cannot read or write', 'Share of people aged 15+ who cannot read and write a short note', 'P15YM_AN', 'P_15YMAS', '%'),
    ('schooling', 'Education', 'Average years of schooling', 'Average grades completed by people aged 15+ (INEGI excludes those who did not state them)', 'GRAPROES', None, 'years'),
    ('internet', 'Home', 'Homes with internet', 'Share of occupied homes with internet access', 'VPH_INTER', 'VIVPARH_CV', '%'),
    ('no_electricity', 'Home', 'Homes without electricity', 'Share of occupied homes without electric power', 'VPH_S_ELEC', 'VIVPARH_CV', '%'),
    ('no_ict', 'Home', 'Homes without any communication technology', 'Share of occupied homes with no radio, TV, computer, phone line, cell phone, or internet', 'VPH_SINTIC', 'VIVPARH_CV', '%'),
]


def rows():
    path = glob.glob(str(CACHE / 'data/iter/**/conjunto_de_datos_iter_00CSV20.csv'), recursive=True)[0]
    mun, states, nation = {}, {}, None
    with open(path, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if r['LOC'] != '0000':
                continue
            if r['ENTIDAD'] == '00':
                nation = r
            elif r['MUN'] == '000':
                states[r['ENTIDAD']] = r
            else:
                mun[r['ENTIDAD'] + r['MUN']] = r
    return mun, states, nation


def value(row, numerator, denominator):
    if denominator is None:
        return round(float(row[numerator]), 2)
    return round(100 * int(row[numerator]) / int(row[denominator]), 2)


def main():
    mun, states, nation = rows()
    assert len(mun) == 2469 and len(states) == 32
    counts = {c for _, _, _, _, n, d, _ in CATALOG for c in (n, d) if c and c != 'GRAPROES'} | {'POBTOT'}
    for c in sorted(counts):  # municipios sum to states, states sum to the nation, exactly
        for code, s in states.items():
            assert sum(int(r[c]) for k, r in mun.items() if k[:2] == code) == int(s[c]), (c, code)
        assert sum(int(s[c]) for s in states.values()) == int(nation[c]), c

    ids = sorted(mun)
    out = {'source': 'INEGI, Censo de Poblacion y Vivienda 2020, ITER', 'ids': ids,
           'variables': [], 'municipios': {}, 'states': {code: {} for code in sorted(states)}}
    for vid, group, label, description, numerator, denominator, unit in CATALOG:
        values = [value(mun[i], numerator, denominator) for i in ids]
        lo, hi = np.percentile(values, [2, 98])  # color range robust to a few extreme municipios
        out['variables'].append({
            'id': vid, 'group': group, 'label': label, 'description': description, 'unit': unit,
            'numerator': numerator, 'denominator': denominator,
            'national': value(nation, numerator, denominator), 'domain': [round(lo, 2), round(hi, 2)]})
        out['municipios'][vid] = values
        for code, s in states.items():
            out['states'][code][vid] = value(s, numerator, denominator)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'variables.json').write_text(json.dumps(out, separators=(',', ':'), ensure_ascii=False))
    for v in out['variables']:
        print(f"{v['label']:44} Mexico {v['national']:>6} {v['unit']:5} color range {v['domain']}")


if __name__ == '__main__':
    main()
