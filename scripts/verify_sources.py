#!/usr/bin/env python3
"""Probe candidate data sources for score v3 and record what actually exists.

The v3 plan (docs/sector-methodology-plan.md section 4) lists series IDs from
memory. This script verifies them: it asks FRED for each candidate's
metadata, and — for any purpose no candidate satisfies — runs a FRED series
search and verifies the hits, so wrong guesses self-heal on the next run.
It also dumps the Atlanta Fed workbook's structure and checks Indeed Hiring
Lab raw files. Everything lands in data/source-verification.json.

Trust rules (enforced here and consumed by update_slices.py):
- every purpose MUST have title expectations; an entry counts as verified
  only when the series exists AND its FRED title matches all expectation
  patterns. A wrong guess becomes a missing component, never a wrong number.
  (The first live run proved why: two CPS candidates resolved to the wrong
  sectors and, under a laxer rule, shipped into a slice.)
- "series doesn't exist" (HTTP 400) is recorded as notFound; network/rate
  errors are retried once and recorded as kind=transient so a bad network
  moment is distinguishable from a bad guess.

Run in an environment with outbound network access (the GitHub Actions
workflows do; the Claude remote environment cannot).
"""

import json
import os
import re
import sys
import urllib.error
from datetime import datetime
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fred_client as fc

REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', 'data', 'source-verification.json')

SECTOR_PATTERNS = {
    'information': r'\binformation\b',
    'pbs': r'professional and business',
    'healthsocial': r'health care and social|education and health',
    'leisure': r'\bleisure\b',
    'manufacturing': r'\bmanufacturing\b',
    'govfederal': r'\bfederal\b',
    'govstatelocal': r'state and local',
}
MEASURE_PATTERNS = {
    'quits': r'\bquits\b',
    'hires': r'\bhires\b',
    'layoffs': r'layoffs and discharges|\blayoffs\b',
    'openings': r'\bjob openings\b',
}

# Candidate FRED IDs per purpose. Multiple guesses per slot are expected; the
# report shows which resolve and what they actually are. Confirmed on the
# first live run (2026-07-16): PBS=540099, health=6200, leisure=7000,
# manufacturing=3000, state&local=9200; Information and federal government
# patterns and ALL industry layoffs suffixes were wrong -> now also guessed
# with the 0099 pattern, plus FRED search fills remaining holes.
FRED_CANDIDATES = {
    # --- industry axis: JOLTS ---
    'jolts.information.quits': ['JTS510099QUR', 'JTS5100QUR'],
    'jolts.information.hires': ['JTS510099HIR', 'JTS5100HIR'],
    'jolts.information.layoffs': ['JTS510099LDR', 'JTS5100LDR'],
    'jolts.information.openings': ['JTS510099JOL', 'JTS5100JOL'],
    'jolts.pbs.quits': ['JTS540099QUR'],
    'jolts.pbs.hires': ['JTS540099HIR'],
    'jolts.pbs.layoffs': ['JTS540099LDR', 'JTS5400LDR'],
    'jolts.pbs.openings': ['JTS540099JOL'],
    'jolts.healthsocial.quits': ['JTS6200QUR'],
    'jolts.healthsocial.hires': ['JTS6200HIR'],
    'jolts.healthsocial.layoffs': ['JTS6200LDR', 'JTS620099LDR'],
    'jolts.healthsocial.openings': ['JTS6200JOL'],
    'jolts.leisure.quits': ['JTS7000QUR'],
    'jolts.leisure.hires': ['JTS7000HIR'],
    'jolts.leisure.layoffs': ['JTS7000LDR', 'JTS700099LDR'],
    'jolts.leisure.openings': ['JTS7000JOL'],
    'jolts.manufacturing.quits': ['JTS3000QUR'],
    'jolts.manufacturing.hires': ['JTS3000HIR'],
    'jolts.manufacturing.layoffs': ['JTS3000LDR', 'JTS300099LDR'],
    'jolts.manufacturing.openings': ['JTS3000JOL'],
    'jolts.govfederal.quits': ['JTS910099QUR', 'JTS9100QUR'],
    'jolts.govfederal.hires': ['JTS910099HIR', 'JTS9100HIR'],
    'jolts.govfederal.layoffs': ['JTS910099LDR', 'JTS9100LDR'],
    'jolts.govfederal.openings': ['JTS910099JOL', 'JTS9100JOL'],
    'jolts.govstatelocal.quits': ['JTS9200QUR'],
    'jolts.govstatelocal.hires': ['JTS9200HIR'],
    'jolts.govstatelocal.layoffs': ['JTS9200LDR', 'JTS920099LDR'],
    'jolts.govstatelocal.openings': ['JTS9200JOL'],
    # --- industry axis: CES average hourly earnings (supersector) ---
    'ces.information.ahe': ['CES5000000003'],
    'ces.pbs.ahe': ['CES6000000003'],
    'ces.healthsocial.ahe': ['CES6562000003', 'CES6500000003'],
    'ces.leisure.ahe': ['CES7000000003'],
    'ces.manufacturing.ahe': ['CES3000000003'],
    # --- industry axis: CPS unemployment by industry of last job (NSA) ---
    # First run proved the LNU0303224x guesses map to other sectors; rely on
    # search with strict title matching.
    'cps.information.unemployed': [],
    'cps.pbs.unemployed': [],
    'cps.information.unemp_rate': [],
    'cps.pbs.unemp_rate': [],
    'cps.healthsocial.unemp_rate': [],
    'cps.leisure.unemp_rate': [],
    'cps.manufacturing.unemp_rate': [],
    # --- occupation axis (Phase 2 prep) ---
    'cps.occ.mgmt_prof.unemp_rate': ['LNU04032215'],
    'cps.occ.mgmt_business_financial.unemp_rate': ['LNU04032216'],
    'indeed.us.aggregate': ['IHLIDXUS'],
    'indeed.us.software_dev': ['IHLIDXUSTPSOFTDEVE'],
    'indeed.us.project_management': ['IHLIDXUSTPPROJMANA'],
}

# Title expectations are REQUIRED for every purpose: entries only count as
# verified when the FRED title matches ALL patterns for the purpose.
TITLE_EXPECTATIONS = {}
for _sector, _pat in SECTOR_PATTERNS.items():
    for _measure, _mpat in MEASURE_PATTERNS.items():
        TITLE_EXPECTATIONS[f'jolts.{_sector}.{_measure}'] = [_mpat, _pat]
    TITLE_EXPECTATIONS[f'ces.{_sector}.ahe'] = [r'average hourly earnings', _pat]
    TITLE_EXPECTATIONS[f'cps.{_sector}.unemployed'] = [r'unemployment level', _pat]
    TITLE_EXPECTATIONS[f'cps.{_sector}.unemp_rate'] = [r'unemployment rate', _pat]
TITLE_EXPECTATIONS.update({
    'cps.occ.mgmt_prof.unemp_rate': [r'unemployment rate', r'management, professional'],
    'cps.occ.mgmt_business_financial.unemp_rate': [r'unemployment rate', r'management, business'],
    'indeed.us.aggregate': [r'job postings on indeed'],
    'indeed.us.software_dev': [r'software development', r'indeed'],
    'indeed.us.project_management': [r'project management', r'indeed'],
})

# Search texts used when no direct candidate verifies for a purpose.
SEARCH_TEXTS = {}
for _sector, _name in [('information', 'Information'),
                       ('pbs', 'Professional and Business Services'),
                       ('healthsocial', 'Health Care and Social Assistance'),
                       ('leisure', 'Leisure and Hospitality'),
                       ('manufacturing', 'Manufacturing'),
                       ('govfederal', 'Federal government'),
                       ('govstatelocal', 'State and Local government')]:
    for _measure, _mname in [('quits', 'Quits rate'), ('hires', 'Hires rate'),
                             ('layoffs', 'Layoffs and discharges rate'),
                             ('openings', 'Job openings')]:
        SEARCH_TEXTS[f'jolts.{_sector}.{_measure}'] = f'JOLTS {_mname} {_name}'
    SEARCH_TEXTS[f'ces.{_sector}.ahe'] = f'Average hourly earnings {_name}'
    SEARCH_TEXTS[f'cps.{_sector}.unemployed'] = f'Unemployment level {_name} industry'
    SEARCH_TEXTS[f'cps.{_sector}.unemp_rate'] = f'Unemployment rate {_name} industry'

INDEED_GITHUB_CANDIDATES = [
    'https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master/US/job_postings_by_sector_US.csv',
]

_UA = {'User-Agent': 'labor-market-dashboard/1.0 (verification probe)'}


def title_matches(purpose, title):
    patterns = TITLE_EXPECTATIONS.get(purpose)
    if not patterns:
        return False  # no expectation registered -> never trusted for building
    return all(re.search(p, title, re.I) for p in patterns)


def _meta_entry(purpose, series_id, meta, source):
    return {
        'id': series_id,
        'ok': True,
        'source': source,
        'titleMatchesPurpose': title_matches(purpose, meta.get('title', '')),
        'title': meta.get('title'),
        'seasonalAdjustment': meta.get('seasonal_adjustment_short'),
        'frequency': meta.get('frequency_short'),
        'start': meta.get('observation_start'),
        'end': meta.get('observation_end'),
    }


def _probe_id(purpose, series_id, source='candidate'):
    """Verify one series id, distinguishing not-found from transient errors."""
    for attempt in (1, 2):
        try:
            meta = fc.fetch_series_meta(series_id)
            if meta is None:
                return {'id': series_id, 'ok': False, 'source': source,
                        'kind': 'notFound', 'error': 'no series in response'}
            return _meta_entry(purpose, series_id, meta, source)
        except fc.FredError as e:
            cause = e.__cause__
            if isinstance(cause, urllib.error.HTTPError) and cause.code == 400:
                return {'id': series_id, 'ok': False, 'source': source,
                        'kind': 'notFound', 'error': 'HTTP 400 (unknown series id)'}
            if attempt == 2:
                return {'id': series_id, 'ok': False, 'source': source,
                        'kind': 'transient', 'error': str(e)}


def _search_series(text, limit=8):
    """FRED full-text series search; returns raw series metadata dicts."""
    payload = fc._get_json('series/search', {
        'search_text': text, 'limit': limit, 'order_by': 'popularity'})
    return payload.get('seriess', [])


def probe_fred():
    report = {}
    for purpose, candidates in FRED_CANDIDATES.items():
        entries = [_probe_id(purpose, sid) for sid in candidates]
        verified = [e for e in entries if e.get('ok') and e.get('titleMatchesPurpose')]
        if not verified and purpose in SEARCH_TEXTS:
            try:
                for meta in _search_series(SEARCH_TEXTS[purpose]):
                    if meta.get('frequency_short') != 'M':
                        continue
                    if not title_matches(purpose, meta.get('title', '')):
                        continue
                    entry = _meta_entry(purpose, meta['id'], meta, 'search')
                    entries.append(entry)
                    verified.append(entry)
                # prefer seasonally adjusted search hits
                verified.sort(key=lambda e: e.get('seasonalAdjustment') != 'SA')
            except fc.FredError as e:
                entries.append({'id': f'search:{SEARCH_TEXTS[purpose]}',
                                'ok': False, 'source': 'search',
                                'kind': 'transient', 'error': str(e)})
        # order the report best-first so consumers can take entries[0]
        entries.sort(key=lambda e: (not e.get('ok'),
                                    not e.get('titleMatchesPurpose', False),
                                    e.get('seasonalAdjustment') != 'SA'))
        report[purpose] = entries
        best = next((e for e in entries if e.get('ok') and e.get('titleMatchesPurpose')), None)
        print(f'  {purpose}: '
              f'{best["id"] + " -> " + (best["title"] or "")[:60] if best else "NO MATCH"}')
    return report


def probe_atlanta_fed():
    import atlanta_fed
    entry = {}
    try:
        content, url = atlanta_fed._workbook_bytes()
        entry.update(url=url, ok=True, bytes=len(content))
        import io
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        sheets = []
        for sheet in wb.worksheets:
            rows = []
            for i, row in enumerate(sheet.iter_rows(values_only=True)):
                rows.append(row)
                if i >= 3:
                    break
            sheets.append({
                'title': sheet.title,
                'headRows': [[str(c)[:60] if c is not None else None
                              for c in (r or [])][:25] for r in rows],
            })
        entry['sheets'] = sheets
        try:
            premium = atlanta_fed.parse_workbook(content)
            latest = sorted(premium.items())[-1]
            entry['parsedOk'] = True
            entry['months'] = len(premium)
            entry['latest'] = {'date': latest[0],
                               'premium': round(latest[1][0] - latest[1][1], 2)}
        except Exception as e:  # noqa: BLE001 - diagnostics only
            entry['parsedOk'] = False
            entry['parseError'] = str(e)
    except Exception as e:  # noqa: BLE001 - diagnostics only
        entry['ok'] = False
        entry['error'] = str(e)
    print(f'  atlanta fed: ok={entry.get("ok")} parsed={entry.get("parsedOk")} '
          f'{entry.get("error") or entry.get("parseError") or ""}')
    return [entry]


def probe_indeed_github():
    results = []
    for url in INDEED_GITHUB_CANDIDATES:
        entry = {'url': url}
        try:
            with urlopen(Request(url, headers=_UA), timeout=30) as resp:
                first_line = resp.read(2000).decode('utf-8', 'replace').split('\n')[0]
            entry['ok'] = True
            entry['headerLine'] = first_line[:300]
        except Exception as e:  # noqa: BLE001 - diagnostics only
            entry['ok'] = False
            entry['error'] = str(e)
        results.append(entry)
        print(f'  indeed {url.rsplit("/", 2)[-1]}: {entry.get("ok") or entry.get("error")}')
    return results


def main():
    if not os.environ.get('FRED_API_KEY'):
        print('Error: FRED_API_KEY not set — refusing to write an all-failure report')
        sys.exit(1)

    print('Probing FRED candidates (search fallback for unresolved purposes)...')
    report = {
        'generated': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'fred': probe_fred(),
    }
    print('Probing Atlanta Fed workbook...')
    report['atlantaFed'] = probe_atlanta_fed()
    print('Probing Indeed Hiring Lab files...')
    report['indeedGithub'] = probe_indeed_github()

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    tmp_path = REPORT_PATH + '.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(report, f, indent=2)
    os.replace(tmp_path, REPORT_PATH)
    print(f'\nReport written to {os.path.relpath(REPORT_PATH)}')

    transient = sum(1 for entries in report['fred'].values()
                    for e in entries if e.get('kind') == 'transient')
    if transient:
        print(f'WARNING: {transient} transient FRED errors — '
              'rerun before trusting NO MATCH results.')


if __name__ == '__main__':
    main()
