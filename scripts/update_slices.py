#!/usr/bin/env python3
"""Build per-industry slice files (data/slices/*.json) — score v3 Phase 1.

Method (docs/sector-methodology-plan.md sections 3-5):
- Components per slice: JOLTS quits/hires/layoffs (3-month moving average —
  industry cells are noisier than total nonfarm), openings-per-unemployed
  where a CPS unemployed-by-industry series exists (12MMA denominator, NSA
  handling), real wage growth (CES industry AHE YoY minus national CPI YoY),
  and the national switcher premium as a labeled overlay. Duration,
  participation, and the unemployment rate have no defensible monthly
  industry cut and drop out; weights renormalize at score time.
- Normalization anchors are fit from each slice series' own 2015-present
  history (p5/p95, pandemic months excluded) and embedded in the output, so
  the scorer — Python here, JS in the app — stays generic.
- Sources must be verified first: this script only uses a series id that
  verify_sources.py confirmed exists AND whose FRED title matches the
  purpose. A wrong guess becomes a missing component, never a wrong number.
- Each slice file carries provenance (chosen ids, titles, smoothing, anchor
  windows) and the manifest carries face-validity check results (plan
  section 7.1) so a human can see whether the battery passes before any UI
  ships these numbers.

Run after update_data.py (needs data.json for the national overlay and the
face-validity baseline). Requires FRED_API_KEY.
"""

import json
import os
import statistics
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fred_client as fc
import score_model as sm

REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
DATA_PATH = os.path.join(REPO_ROOT, 'data.json')
REPORT_PATH = os.path.join(REPO_ROOT, 'data', 'source-verification.json')
SLICES_DIR = os.path.join(REPO_ROOT, 'data', 'slices')

WEIGHTS = {key: weight for key, weight, *_ in sm.NATIONAL_COMPONENTS}

SLICE_DEFS = [
    {
        'slug': 'information',
        'name': 'Information',
        'naics': '51',
        'jolts': 'jolts.information',
        'ces_ahe': 'ces.information.ahe',
        'cps_unemployed': 'cps.information.unemployed',
        'caveats': [
            'NAICS 51 is the closest measurable proxy for "tech" but also '
            'includes broadcasting, telecom, and publishing; software-adjacent '
            'consulting (computer systems design) sits in Professional & '
            'Business Services instead.',
        ],
    },
    {
        'slug': 'professional-business',
        'name': 'Professional & Business Services',
        'naics': '54-56',
        'jolts': 'jolts.pbs',
        'ces_ahe': 'ces.pbs.ahe',
        'cps_unemployed': 'cps.pbs.unemployed',
        'caveats': [
            'This supersector spans consultants, lawyers, and engineers (54) '
            'together with temp agencies, janitorial, and waste services (56); '
            'the aggregate can mask opposite moves in white-collar vs support '
            'work.',
        ],
    },
    {
        'slug': 'health-social',
        'name': 'Health Care & Social Assistance',
        'naics': '62',
        'jolts': 'jolts.healthsocial',
        'ces_ahe': 'ces.healthsocial.ahe',
        'cps_unemployed': None,
        'caveats': [
            'Hospitals, home health, and childcare have very different pay '
            'and churn dynamics; this is the sector aggregate.',
        ],
    },
    {
        'slug': 'leisure-hospitality',
        'name': 'Leisure & Hospitality',
        'naics': '71-72',
        'jolts': 'jolts.leisure',
        'ces_ahe': 'ces.leisure.ahe',
        'cps_unemployed': None,
        'caveats': [
            'Structurally high-churn: quit and hire rates run roughly twice '
            'the national level. Scores compare this sector to its own '
            'history, not to other sectors.',
        ],
    },
    {
        'slug': 'manufacturing',
        'name': 'Manufacturing',
        'naics': '31-33',
        'jolts': 'jolts.manufacturing',
        'ces_ahe': 'ces.manufacturing.ahe',
        'cps_unemployed': None,
        'caveats': ['Durable and nondurable goods can diverge within this aggregate.'],
    },
    {
        'slug': 'government-federal',
        'name': 'Federal Government',
        'naics': '91 (fed)',
        'jolts': 'jolts.govfederal',
        'ces_ahe': None,  # CES hourly-earnings coverage is private-sector only
        'cps_unemployed': None,
        'caveats': [
            'Wage components are unavailable for government; the score leans '
            'on turnover flows and the national switcher premium.',
        ],
    },
    {
        'slug': 'government-state-local',
        'name': 'State & Local Government',
        'naics': '92-93 (S&L)',
        'jolts': 'jolts.govstatelocal',
        'ces_ahe': None,
        'cps_unemployed': None,
        'caveats': [
            'Wage components are unavailable for government; the score leans '
            'on turnover flows and the national switcher premium.',
        ],
    },
]

JOLTS_MEASURES = {'quitRate': 'quits', 'hiresRate': 'hires', 'layoffsRate': 'layoffs'}
SMOOTH_WINDOW = 3  # months, for JOLTS industry cells (plan section 5.1)
DENOM_WINDOW = 12  # months, NSA CPS unemployed-by-industry (plan section 5.2)


def resolve(report, purpose):
    """First verified candidate for a purpose, or None. Trusts only entries
    that exist on FRED and whose title matched the purpose keywords."""
    for entry in report.get('fred', {}).get(purpose, []):
        if entry.get('ok') and entry.get('titleMatchesPurpose', True):
            return entry
    return None


def build_component(key, dates, values, provenance, inverted=False):
    anchors = fc.fit_anchors(dates, values, inverted)
    if anchors is None:
        return None
    return {
        'name': key,
        'weight': WEIGHTS[key],
        'norm': anchors,
        'values': values,
        'provenance': provenance,
    }


def build_slice(spec, report, national, cpi_yoy_by_date):
    print(f'  Building slice: {spec["slug"]}')
    components = {}
    skipped = {}
    fetched = {}

    def fetch_for(purpose):
        entry = resolve(report, purpose)
        if entry is None:
            return None, None
        if purpose not in fetched:
            fetched[purpose] = fc.fetch_observations(entry['id'])
        return fetched[purpose], entry

    # Month grid from the slice's JOLTS quits series (its defining axis)
    quits_map, quits_entry = fetch_for(f'{spec["jolts"]}.quits')
    if quits_map is None:
        skipped['ALL'] = f'no verified series for {spec["jolts"]}.quits'
        return None, skipped
    dates = fc.month_grid([quits_map])
    labels = [fc.date_to_label(d) for d in dates]

    def column(source):
        return [source.get(d) for d in dates]

    # JOLTS rates, smoothed
    for key, measure in JOLTS_MEASURES.items():
        source, entry = fetch_for(f'{spec["jolts"]}.{measure}')
        if source is None:
            skipped[key] = 'source unverified'
            continue
        smoothed = fc.moving_average(column(source), SMOOTH_WINDOW)
        comp = build_component(key, dates, smoothed, {
            'series': entry['id'], 'title': entry['title'],
            'smoothing': f'{SMOOTH_WINDOW}mma',
        }, inverted=(key == 'layoffsRate'))
        if comp:
            components[key] = comp
        else:
            skipped[key] = 'insufficient history to fit anchors'

    # Openings per unemployed (only where a CPS industry denominator exists)
    if spec['cps_unemployed']:
        openings_map, openings_entry = fetch_for(f'{spec["jolts"]}.openings')
        unemployed_map, unemployed_entry = fetch_for(spec['cps_unemployed'])
        if openings_map and unemployed_map:
            openings = fc.moving_average(column(openings_map), SMOOTH_WINDOW)
            denom = fc.moving_average(column(unemployed_map), DENOM_WINDOW)
            ratio = [round(o / u, 2) if o is not None and u else None
                     for o, u in zip(openings, denom)]
            comp = build_component('openingsRatio', dates, ratio, {
                'series': [openings_entry['id'], unemployed_entry['id']],
                'title': f"{openings_entry['title']} / {unemployed_entry['title']}",
                'smoothing': f'{SMOOTH_WINDOW}mma numerator, {DENOM_WINDOW}mma NSA denominator',
                'note': 'Denominator is unemployed by industry of last job '
                        '(CPS, not seasonally adjusted; 12-month average).',
            })
            if comp:
                components['openingsRatio'] = comp
            else:
                skipped['openingsRatio'] = 'insufficient history to fit anchors'
        else:
            skipped['openingsRatio'] = 'openings or CPS denominator unverified'
    else:
        skipped['openingsRatio'] = 'no CPS unemployed-by-industry series for this sector'

    # Real wage growth: industry AHE YoY minus national CPI YoY
    if spec['ces_ahe']:
        ahe_map, ahe_entry = fetch_for(spec['ces_ahe'])
        if ahe_map:
            wage_yoy = fc.yoy_growth(ahe_map)
            real = [round(w - c, 1) if w is not None and c is not None else None
                    for w, c in zip(column(wage_yoy),
                                    (cpi_yoy_by_date.get(d) for d in dates))]
            comp = build_component('realWageGrowth', dates, real, {
                'series': [ahe_entry['id'], 'CPIAUCSL'],
                'title': f"{ahe_entry['title']} YoY minus national CPI YoY",
                'note': 'No industry-level CPI exists; deflating industry '
                        'wages by national CPI is standard practice.',
            })
            if comp:
                components['realWageGrowth'] = comp
            else:
                skipped['realWageGrowth'] = 'insufficient history to fit anchors'
        else:
            skipped['realWageGrowth'] = 'CES AHE series unverified'
    else:
        skipped['realWageGrowth'] = 'no wage series for this sector (CES covers private only)'

    # National switcher premium overlay, aligned by label
    national_swp = dict(zip(national.get('labels', []),
                            national.get('switcherPremium', []) or []))
    swp = [national_swp.get(lbl) for lbl in labels]
    if any(v is not None for v in swp):
        comp = build_component('switcherPremium', dates, swp, {
            'series': 'Atlanta Fed Wage Growth Tracker (national)',
            'scope': 'national',
            'note': 'The tracker does not publish switcher/stayer by industry; '
                    'this component is the same for every slice.',
        })
        if comp:
            components['switcherPremium'] = comp
    else:
        skipped['switcherPremium'] = 'national switcher premium unavailable'

    if 'quitRate' not in components or 'hiresRate' not in components:
        skipped['ALL'] = 'quits/hires missing — slice not scorable'
        return None, skipped

    # Trim trailing months where nothing reported
    last_idx = max(fc.last_valid_index(c['values']) for c in components.values())
    dates, labels = dates[:last_idx + 1], labels[:last_idx + 1]
    for comp in components.values():
        comp['values'] = comp['values'][:last_idx + 1]

    doc = {
        'meta': {
            'slug': spec['slug'],
            'name': spec['name'],
            'naics': spec['naics'],
            'methodology': 'v3-phase1 (docs/sector-methodology-plan.md)',
            'generated': datetime.now().strftime('%Y-%m-%d'),
            'dataThrough': dates[-1][:7],
            'caveats': spec['caveats'],
            'anchorWindow': '2015-present excluding 2020-03..2020-12, p5/p95',
            'scoreNote': 'Scores compare this sector to its own history, not '
                         'to other sectors. See methodology plan section 5.4.',
            'skippedComponents': skipped,
        },
        'labels': labels,
        'components': components,
    }
    scores = sm.slice_scores(doc)
    doc['scores'] = scores
    doc['meta']['margin'] = score_margin(scores)
    return doc, skipped


def score_margin(scores, floor=5, window=60):
    """max(floor, 2x stdev of month-over-month changes) — plan section 5.5."""
    recent = [s for s in scores[-window:] if s is not None]
    diffs = [b - a for a, b in zip(recent, recent[1:])]
    if len(diffs) < 12:
        return floor
    return max(floor, round(2 * statistics.pstdev(diffs)))


def mean_over(labels, scores, year_prefixes):
    vals = [s for lbl, s in zip(labels, scores)
            if s is not None and any(lbl.endswith(p) for p in year_prefixes)]
    return round(statistics.mean(vals), 1) if vals else None


def face_validity(slices, national):
    """Plan section 7.1 sign tests. Reported, not silently enforced."""
    national_scores = sm.national_scores(national)
    nat_labels = national['labels']
    checks = {}

    def slice_mean(slug, years):
        doc = slices.get(slug)
        return mean_over(doc['labels'], doc['scores'], years) if doc else None

    nat_2023 = mean_over(nat_labels, national_scores, ['-23'])
    info_2023 = slice_mean('information', ['-23'])
    if info_2023 is not None and nat_2023 is not None:
        checks['information_2023_below_national'] = {
            'pass': info_2023 < nat_2023, 'slice': info_2023, 'national': nat_2023}

    health_2324 = slice_mean('health-social', ['-23', '-24'])
    nat_2324 = mean_over(nat_labels, national_scores, ['-23', '-24'])
    if health_2324 is not None and nat_2324 is not None:
        checks['health_2023_24_above_national'] = {
            'pass': health_2324 > nat_2324, 'slice': health_2324, 'national': nat_2324}

    fed_2024 = slice_mean('government-federal', ['-24'])
    fed_2526 = slice_mean('government-federal', ['-25', '-26'])
    if fed_2024 is not None and fed_2526 is not None:
        checks['federal_falls_2025_26'] = {
            'pass': fed_2526 < fed_2024, '2024': fed_2024, '2025_26': fed_2526}

    lh = slices.get('leisure-hospitality')
    if lh and 'quitRate' in lh['components']:
        vals = [v for lbl, v in zip(lh['labels'], lh['components']['quitRate']['values'])
                if v is not None and (lbl.endswith('-21') or lbl.endswith('-22'))]
        base = [v for lbl, v in zip(lh['labels'], lh['components']['quitRate']['values'])
                if v is not None and lbl.endswith('-19')]
        if vals and base:
            checks['leisure_quits_spike_2021_22'] = {
                'pass': max(vals) > max(base) * 1.15,
                'peak_2021_22': max(vals), 'peak_2019': max(base)}
    return checks


def main():
    if not os.path.exists(REPORT_PATH):
        print('No data/source-verification.json — run verify_sources.py first. '
              'Skipping slice build (nothing emitted).')
        return
    with open(REPORT_PATH) as f:
        report = json.load(f)
    with open(DATA_PATH) as f:
        national = json.load(f)

    print('Fetching national CPI for real-wage deflation...')
    cpi_yoy = fc.yoy_growth(fc.fetch_observations('CPIAUCSL'))

    os.makedirs(SLICES_DIR, exist_ok=True)
    built, all_skipped = {}, {}
    for spec in SLICE_DEFS:
        doc, skipped = build_slice(spec, report, national, cpi_yoy)
        all_skipped[spec['slug']] = skipped
        if doc is None:
            print(f'    SKIPPED {spec["slug"]}: {skipped.get("ALL")}')
            continue
        built[spec['slug']] = doc
        path = os.path.join(SLICES_DIR, f'{spec["slug"]}.json')
        with open(path, 'w') as f:
            json.dump(doc, f, indent=1)
        latest = next((s for s in reversed(doc['scores']) if s is not None), None)
        print(f'    wrote {os.path.relpath(path)} '
              f'(through {doc["meta"]["dataThrough"]}, latest score {latest}, '
              f'margin +/-{doc["meta"]["margin"]}, '
              f'{len(doc["components"])} components)')

    manifest = {
        'generated': datetime.now().strftime('%Y-%m-%d'),
        'methodology': 'v3-phase1',
        'slices': [{
            'slug': doc['meta']['slug'],
            'name': doc['meta']['name'],
            'dataThrough': doc['meta']['dataThrough'],
            'margin': doc['meta']['margin'],
            'latestScore': next((s for s in reversed(doc['scores']) if s is not None), None),
            'components': sorted(doc['components'].keys()),
        } for doc in built.values()],
        'skipped': all_skipped,
        'faceValidity': face_validity(built, national),
    }
    with open(os.path.join(SLICES_DIR, 'index.json'), 'w') as f:
        json.dump(manifest, f, indent=1)

    print(f'\nBuilt {len(built)}/{len(SLICE_DEFS)} slices.')
    for name, result in manifest['faceValidity'].items():
        print(f'  face-validity {name}: {"PASS" if result["pass"] else "FAIL"} {result}')
    failures = [n for n, r in manifest['faceValidity'].items() if not r['pass']]
    if failures:
        print('\nWARNING: face-validity failures above must be resolved before '
              'any UI ships these slices (plan section 7.1).')


if __name__ == '__main__':
    main()
