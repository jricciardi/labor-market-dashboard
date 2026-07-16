#!/usr/bin/env python3
"""Probe candidate data sources for score v3 and record what actually exists.

The v3 plan (docs/sector-methodology-plan.md section 4) lists series IDs from
memory, flagged "V?" — this script is the verification step. It asks FRED for
each candidate's *metadata* (title, seasonal adjustment, date range), dumps
the Atlanta Fed workbook's structure, and checks Indeed Hiring Lab raw files,
then writes everything to data/source-verification.json.

update_slices.py consumes that report and will only build a slice component
from a candidate that (a) verified and (b) whose FRED title matches the
expected keywords — so a wrong guess degrades to a missing component instead
of silently scoring the wrong series.

Run in an environment with outbound network access (the GitHub Actions
workflow does this; the Claude remote environment cannot).
"""

import json
import os
import re
import sys
from datetime import datetime
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fred_client as fc

REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', 'data', 'source-verification.json')

# Candidate FRED IDs per purpose. Multiple guesses per slot are expected;
# the report shows which resolve and what they actually are. Keep failed
# probes in the report (cheap, and they document what was ruled out).
#
# JOLTS mnemonic guesses follow the JTS{industry}{measure} pattern with
# 2- and 6-digit industry codes; measures: QUR quits, HIR hires,
# LDR layoffs+discharges, JOL openings level. All seasonally adjusted (JTS;
# JTU is NSA).
FRED_CANDIDATES = {
    # --- industry axis: JOLTS ---
    'jolts.information.quits': ['JTS5100QUR', 'JTS510000QUR'],
    'jolts.information.hires': ['JTS5100HIR', 'JTS510000HIR'],
    'jolts.information.layoffs': ['JTS5100LDR', 'JTS510000LDR'],
    'jolts.information.openings': ['JTS5100JOL', 'JTS510000JOL'],
    'jolts.pbs.quits': ['JTS540099QUR', 'JTS5400QUR'],
    'jolts.pbs.hires': ['JTS540099HIR', 'JTS5400HIR'],
    'jolts.pbs.layoffs': ['JTS540099LDR', 'JTS5400LDR'],
    'jolts.pbs.openings': ['JTS540099JOL', 'JTS5400JOL'],
    'jolts.healthsocial.quits': ['JTS6200QUR', 'JTS620000QUR', 'JTS6562QUR'],
    'jolts.healthsocial.hires': ['JTS6200HIR', 'JTS620000HIR', 'JTS6562HIR'],
    'jolts.healthsocial.layoffs': ['JTS6200LDR', 'JTS620000LDR', 'JTS6562LDR'],
    'jolts.healthsocial.openings': ['JTS6200JOL', 'JTS620000JOL', 'JTS6562JOL'],
    'jolts.leisure.quits': ['JTS7000QUR', 'JTS700000QUR', 'JTS7100QUR'],
    'jolts.leisure.hires': ['JTS7000HIR', 'JTS700000HIR', 'JTS7100HIR'],
    'jolts.leisure.layoffs': ['JTS7000LDR', 'JTS700000LDR', 'JTS7100LDR'],
    'jolts.leisure.openings': ['JTS7000JOL', 'JTS700000JOL', 'JTS7100JOL'],
    'jolts.manufacturing.quits': ['JTS3000QUR', 'JTS300000QUR'],
    'jolts.manufacturing.hires': ['JTS3000HIR', 'JTS300000HIR'],
    'jolts.manufacturing.layoffs': ['JTS3000LDR', 'JTS300000LDR'],
    'jolts.manufacturing.openings': ['JTS3000JOL', 'JTS300000JOL'],
    'jolts.govfederal.quits': ['JTS9091QUR', 'JTS910000QUR', 'JTS9100QUR'],
    'jolts.govfederal.hires': ['JTS9091HIR', 'JTS910000HIR', 'JTS9100HIR'],
    'jolts.govfederal.layoffs': ['JTS9091LDR', 'JTS910000LDR', 'JTS9100LDR'],
    'jolts.govfederal.openings': ['JTS9091JOL', 'JTS910000JOL', 'JTS9100JOL'],
    'jolts.govstatelocal.quits': ['JTS9092QUR', 'JTS920000QUR', 'JTS9200QUR'],
    'jolts.govstatelocal.hires': ['JTS9092HIR', 'JTS920000HIR', 'JTS9200HIR'],
    'jolts.govstatelocal.layoffs': ['JTS9092LDR', 'JTS920000LDR', 'JTS9200LDR'],
    'jolts.govstatelocal.openings': ['JTS9092JOL', 'JTS920000JOL', 'JTS9200JOL'],
    # --- industry axis: CES average hourly earnings (supersector) ---
    'ces.information.ahe': ['CES5000000003'],
    'ces.pbs.ahe': ['CES6000000003'],
    'ces.healthsocial.ahe': ['CES6562000003', 'CES6500000003'],
    'ces.leisure.ahe': ['CES7000000003'],
    'ces.manufacturing.ahe': ['CES3000000003'],
    # CES detail for the "tech != Information" composite overlay
    'ces.software_publishers.employment': ['CES5051200001', 'CES5051300001'],
    'ces.computer_systems_design.employment': ['CES6054150001'],
    # --- industry axis: CPS unemployed by industry of last job (NSA) ---
    'cps.information.unemployed': ['LNU03032240', 'LNU04032240'],
    'cps.pbs.unemployed': ['LNU03032241', 'LNU04032241'],
    # --- occupation axis (Phase 2 prep) ---
    'cps.occ.mgmt_prof.unemp_rate': ['LNU04032215'],
    'cps.occ.mgmt_business_financial.unemp_rate': ['LNU04032216'],
    'indeed.us.aggregate': ['IHLIDXUS'],
    'indeed.us.software_dev': ['IHLIDXUSTPSOFTDEVE'],
    'indeed.us.project_management': ['IHLIDXUSTPPROJMANA', 'IHLIDXUSTPPROJMANAG'],
}

# Expected-title keywords: a candidate only counts as verified-for-purpose if
# its FRED title matches every regex for its purpose. This is the guard
# against an ID that exists but means something else.
TITLE_EXPECTATIONS = {
    'jolts.information': [r'quits|hires|layoffs|openings', r'information'],
    'jolts.pbs': [r'quits|hires|layoffs|openings', r'professional and business'],
    'jolts.healthsocial': [r'quits|hires|layoffs|openings', r'health care'],
    'jolts.leisure': [r'quits|hires|layoffs|openings', r'leisure'],
    'jolts.manufacturing': [r'quits|hires|layoffs|openings', r'manufacturing'],
    'jolts.govfederal': [r'quits|hires|layoffs|openings', r'federal'],
    'jolts.govstatelocal': [r'quits|hires|layoffs|openings', r'state and local'],
    'ces.information': [r'earnings', r'information'],
    'ces.pbs': [r'earnings', r'professional and business'],
    'ces.healthsocial': [r'earnings', r'health'],
    'ces.leisure': [r'earnings', r'leisure'],
    'ces.manufacturing': [r'earnings', r'manufacturing'],
}

INDEED_GITHUB_CANDIDATES = [
    'https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master/US/job_postings_by_sector_US.csv',
    'https://raw.githubusercontent.com/hiring-lab/data/master/US/job_postings_by_sector_US.csv',
]

_UA = {'User-Agent': 'labor-market-dashboard/1.0 (verification probe)'}


def title_matches(purpose, title):
    prefix = purpose.rsplit('.', 1)[0]
    patterns = TITLE_EXPECTATIONS.get(prefix)
    if not patterns:
        return True  # no expectation registered: existence is enough
    return all(re.search(p, title, re.I) for p in patterns)


def probe_fred():
    report = {}
    for purpose, candidates in FRED_CANDIDATES.items():
        entries = []
        for series_id in candidates:
            try:
                meta = fc.fetch_series_meta(series_id)
            except fc.FredError as e:
                entries.append({'id': series_id, 'ok': False, 'error': str(e)})
                continue
            if meta is None:
                entries.append({'id': series_id, 'ok': False, 'error': 'not found'})
                continue
            entries.append({
                'id': series_id,
                'ok': True,
                'titleMatchesPurpose': title_matches(purpose, meta.get('title', '')),
                'title': meta.get('title'),
                'seasonalAdjustment': meta.get('seasonal_adjustment_short'),
                'frequency': meta.get('frequency_short'),
                'start': meta.get('observation_start'),
                'end': meta.get('observation_end'),
            })
        report[purpose] = entries
        best = next((e for e in entries if e.get('ok') and e.get('titleMatchesPurpose', True)), None)
        print(f'  {purpose}: {best["id"] + " -> " + best["title"] if best else "NO MATCH"}')
    return report


def probe_atlanta_fed():
    import atlanta_fed
    results = []
    for url in atlanta_fed.WORKBOOK_URLS:
        entry = {'url': url}
        try:
            content = atlanta_fed._download(url)
            entry['ok'] = True
            entry['bytes'] = len(content)
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
        results.append(entry)
        print(f'  atlanta fed {url}: '
              f'{"ok, parsed=" + str(entry.get("parsedOk")) if entry.get("ok") else entry.get("error")}')
    return results


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
    print('Probing FRED candidates...')
    report = {
        'generated': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'fred': probe_fred(),
    }
    print('Probing Atlanta Fed workbook...')
    report['atlantaFed'] = probe_atlanta_fed()
    print('Probing Indeed Hiring Lab files...')
    report['indeedGithub'] = probe_indeed_github()

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, 'w') as f:
        json.dump(report, f, indent=2)
    print(f'\nReport written to {os.path.relpath(REPORT_PATH)}')


if __name__ == '__main__':
    main()
