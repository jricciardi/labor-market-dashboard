#!/usr/bin/env python3
"""Build occupation overlay files (data/occupations/*.json) — score v3 Phase 2.

The occupation axis answers "how is demand for MY KIND OF ROLE, across every
industry?" — the complement to the industry slices (docs/
sector-methodology-plan.md sections 1 and 4B). Monthly flow data doesn't
exist by occupation, so the components differ from the industry axis:

- postings (weight .40): Indeed Hiring Lab postings index for the closest
  occupational category, via FRED (daily, SA -> monthly mean). The most
  direct demand signal for a role; history starts 2020-02, a caveat the
  files carry explicitly.
- unempRate (.30): CPS unemployment rate by occupation group (NSA -> 12-month
  average) — slack among the people you compete with.
- realWageGrowth (.30): Atlanta Fed Wage Growth Tracker occupation-group
  median wage growth (12MMA) minus CPI YoY (12MMA to match). The tracker
  publishes only coarse groups; provenance says which group covers a family.

Same machinery as the industry slices: sources must verify (title + units),
percentile anchors are fit per series and embedded in the output, weights
renormalize when a component is missing, and a coverage gate flags files
that shouldn't get a headline number. Scoring requires postings + unempRate
(score_model.OCCUPATION_REQUIRED).

Run after update_data.py. Requires FRED_API_KEY.
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
REPORT_PATH = os.path.join(REPO_ROOT, 'data', 'source-verification.json')
OCC_DIR = os.path.join(REPO_ROOT, 'data', 'occupations')

WEIGHTS = {'postings': 0.40, 'unempRate': 0.30, 'realWageGrowth': 0.30}
START = '2020-02-01'  # postings index base month; the axis' common history

OCC_DEFS = [
    {
        'slug': 'management-business-ops',
        'name': 'Program & Project Management, Business Ops',
        'soc': '11-3, 13-1 (family)',
        'postings': 'indeed.us.project_management',
        'unemp': 'cps.occ.mgmt_business_financial.unemp_rate',
        'wgt_column': r'professional and management',
        'caveats': [
            'Postings are Indeed\'s "Project Management" category — narrower '
            'than the full management/business-operations family, but the '
            'closest live demand signal for PM-type roles.',
            'Wage growth uses the tracker\'s coarse "Professional and '
            'management" group, which spans this family and technical roles.',
        ],
    },
    {
        'slug': 'software-development',
        'name': 'Software Development',
        'soc': '15-125x (family)',
        'postings': 'indeed.us.software_dev',
        'unemp': 'cps.occ.computer_math.unemp_rate',
        'wgt_column': r'professional and management',
        'caveats': [
            'Wage growth uses the tracker\'s coarse "Professional and '
            'management" group, which spans this family and non-technical '
            'management roles.',
        ],
    },
]


def resolve(report, purpose, want_units=None):
    """Same trust rule as update_slices: verified + title-matched only;
    unit-string vagaries live in fred_client.units_match."""
    for entry in report.get('fred', {}).get(purpose, []):
        if not (entry.get('ok') and entry.get('titleMatchesPurpose') is True):
            continue
        if not fc.units_match(entry.get('units'), want_units):
            continue
        return entry
    return None


def build_component(key, dates, values, provenance, inverted=False, window=1):
    anchors = fc.fit_anchors(dates, values, inverted, window=window)
    if anchors is None:
        return None
    return {
        'name': key,
        'weight': WEIGHTS[key],
        'norm': anchors,
        'values': values,
        'provenance': provenance,
    }


def build_family(spec, report, cpi_yoy_12):
    print(f'  Building occupation family: {spec["slug"]}')
    components, skipped = {}, {}

    postings_entry = resolve(report, spec['postings'], 'index')
    if postings_entry is None:
        skipped['ALL'] = f'no verified series for {spec["postings"]}'
        return None, skipped
    postings_monthly = fc.monthly_mean(fc.fetch_observations(postings_entry['id'],
                                                             start_date=START))
    dates = fc.month_grid([postings_monthly], start=START)
    labels = [fc.date_to_label(d) for d in dates]

    def column(source):
        return [source.get(d) for d in dates]

    comp = build_component('postings', dates, column(postings_monthly), {
        'series': postings_entry['id'], 'title': postings_entry['title'],
        'note': 'Indeed postings index, Feb 2020 = 100; daily series averaged '
                'to months. History starts Feb 2020.',
    })
    if comp:
        components['postings'] = comp
    else:
        skipped['postings'] = 'insufficient history to fit anchors'

    unemp_entry = resolve(report, spec['unemp'], 'rate')
    if unemp_entry:
        raw = fc.fetch_observations(unemp_entry['id'], start_date='2019-01-01')
        smoothed = fc.moving_average([raw.get(d) for d in
                                      fc.month_grid([raw], start='2019-01-01')], 12,
                                     min_periods=10)
        aligned_dates = fc.month_grid([raw], start='2019-01-01')
        by_date = dict(zip(aligned_dates, smoothed))
        comp = build_component('unempRate', dates, column(by_date), {
            'series': unemp_entry['id'], 'title': unemp_entry['title'],
            'smoothing': '12mma (NSA source)',
        }, inverted=True, window=12)
        if comp:
            components['unempRate'] = comp
        else:
            skipped['unempRate'] = 'insufficient history to fit anchors'
    else:
        skipped['unempRate'] = 'source unverified'

    try:
        import atlanta_fed
        wgt = atlanta_fed.fetch_wgt_column('Occupation', spec['wgt_column'],
                                           start=START)
        real = [round(w - c, 1) if w is not None and c is not None else None
                for w, c in zip(column(wgt), (cpi_yoy_12.get(d) for d in dates))]
        # window=24: the WGT cut is a 12MMA of 12-month growth, so pandemic
        # months influence observations dated up to two years later
        comp = build_component('realWageGrowth', dates, real, {
            'series': f'Atlanta Fed WGT Occupation sheet, {spec["wgt_column"]!r}',
            'scope': 'coarse-group',
            'smoothing': '12mma of median 12-month growth, minus CPI YoY (12mma)',
        }, window=24)
        if comp:
            components['realWageGrowth'] = comp
        else:
            skipped['realWageGrowth'] = 'insufficient history to fit anchors'
    except Exception as e:  # noqa: BLE001 - WGT failure = missing component
        skipped['realWageGrowth'] = f'WGT occupation cut unavailable: {e}'

    if 'postings' not in components or 'unempRate' not in components:
        skipped['ALL'] = 'postings/unemployment missing — family not scorable'
        return None, skipped

    last_idx = max(fc.last_valid_index(c['values']) for c in components.values())
    dates, labels = dates[:last_idx + 1], labels[:last_idx + 1]
    for comp in components.values():
        comp['values'] = comp['values'][:last_idx + 1]

    covered_weight = round(sum(c['weight'] for c in components.values()), 3)
    doc = {
        'meta': {
            'slug': spec['slug'],
            'name': spec['name'],
            'kind': 'occupation',
            'soc': spec['soc'],
            'methodology': 'v3-phase2 (docs/sector-methodology-plan.md)',
            'generated': datetime.now().strftime('%Y-%m-%d'),
            'dataThrough': dates[-1][:7],
            'historyStart': START[:4],
            'caveats': spec['caveats'],
            'anchorWindow': f'{START[:7]}-present excluding 2020-03..2020-12 '
                            '(extended by averaging windows), p5/p95',
            'scoreNote': 'Scores compare this role family to its own '
                         'post-2020 history, not to other groups.',
            'coverage': 'ok' if covered_weight >= 0.60 else 'insufficient',
            'coveredWeight': covered_weight,
            'skippedComponents': skipped,
        },
        'labels': labels,
        'components': components,
    }
    doc['scores'] = sm.slice_scores(doc)
    doc['meta']['margin'] = score_margin(doc['scores'])
    return doc, skipped


def score_margin(scores, floor=5, window=60):
    recent = [s for s in scores[-window:] if s is not None]
    diffs = [b - a for a, b in zip(recent, recent[1:])]
    if len(diffs) < 12:
        return floor
    return max(floor, round(2 * statistics.pstdev(diffs)))


def face_validity(families):
    """Phase 2 sign tests: the 2022 postings boom-bust must be visible."""
    checks = {}
    for slug, doc in families.items():
        comp = doc['components'].get('postings')
        if not comp:
            continue
        peak_22 = max((v for l, v in zip(doc['labels'], comp['values'])
                       if v is not None and l.endswith('-22')), default=None)
        recent = [v for v in comp['values'] if v is not None][-12:]
        if peak_22 and recent:
            checks[f'{slug}_postings_below_2022_peak'] = {
                'pass': statistics.mean(recent) < peak_22,
                'peak2022': peak_22, 'recentMean': round(statistics.mean(recent), 1)}
    return checks


def main():
    if not os.path.exists(REPORT_PATH):
        print('No data/source-verification.json — run verify_sources.py first. '
              'Skipping occupation build (nothing emitted).')
        return
    with open(REPORT_PATH) as f:
        report = json.load(f)

    print('Fetching national CPI (12mma of YoY) for real-wage deflation...')
    cpi_yoy = fc.yoy_growth(fc.fetch_observations('CPIAUCSL', start_date='2018-01-01'))
    cpi_dates = fc.month_grid([cpi_yoy], start='2018-01-01')
    cpi_12 = dict(zip(cpi_dates,
                      fc.moving_average([cpi_yoy.get(d) for d in cpi_dates], 12,
                                        min_periods=10)))

    os.makedirs(OCC_DIR, exist_ok=True)
    built, all_skipped = {}, {}
    for spec in OCC_DEFS:
        doc, skipped = build_family(spec, report, cpi_12)
        all_skipped[spec['slug']] = skipped
        if doc is None:
            print(f'    SKIPPED {spec["slug"]}: {skipped.get("ALL")}')
            continue
        built[spec['slug']] = doc
        path = os.path.join(OCC_DIR, f'{spec["slug"]}.json')
        with open(path, 'w') as f:
            json.dump(doc, f, indent=1)
        latest = next((s for s in reversed(doc['scores']) if s is not None), None)
        print(f'    wrote {os.path.relpath(path)} '
              f'(through {doc["meta"]["dataThrough"]}, latest score {latest}, '
              f'margin +/-{doc["meta"]["margin"]}, coverage {doc["meta"]["coverage"]})')

    manifest = {
        'generated': datetime.now().strftime('%Y-%m-%d'),
        'methodology': 'v3-phase2',
        'occupations': [{
            'slug': doc['meta']['slug'],
            'name': doc['meta']['name'],
            'dataThrough': doc['meta']['dataThrough'],
            'margin': doc['meta']['margin'],
            'coverage': doc['meta']['coverage'],
            'coveredWeight': doc['meta']['coveredWeight'],
            'latestScore': next((s for s in reversed(doc['scores']) if s is not None), None),
            'components': sorted(doc['components'].keys()),
        } for doc in built.values()],
        'skipped': all_skipped,
        'faceValidity': face_validity(built),
    }
    with open(os.path.join(OCC_DIR, 'index.json'), 'w') as f:
        json.dump(manifest, f, indent=1)

    print(f'\nBuilt {len(built)}/{len(OCC_DEFS)} occupation families.')
    for name, result in manifest['faceValidity'].items():
        print(f'  face-validity {name}: {"PASS" if result["pass"] else "FAIL"} {result}')


if __name__ == '__main__':
    main()
