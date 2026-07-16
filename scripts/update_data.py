#!/usr/bin/env python3
"""Fetch latest labor market data and update data.json (national view).

FRED series:
- JTSQUR: Quit rate (total nonfarm)
- JTSJOL: Job openings level (thousands)
- UNEMPLOY: Unemployment level (thousands)
- JTSHIR: Hires rate (total nonfarm)
- JTSLDR: Layoffs and discharges rate (total nonfarm)
- UNRATE: Unemployment rate
- FEDFUNDS: Federal funds effective rate (charted, not scored)
- CES0500000003: Average hourly earnings, private (for YoY wage growth)
- LNS11300060: Labor force participation rate, 25-54 years
- UEMPMED: Median duration of unemployment (weeks)
- CPIAUCSL: CPI-U (for real wage growth = wage YoY minus CPI YoY)

Non-FRED:
- Atlanta Fed Wage Growth Tracker: job switcher minus job stayer median wage
  growth ("switcher premium", percentage points). Fetched independently; on
  failure the previous data.json values are carried so a third-party outage
  never blanks the series.

Run with: python scripts/update_data.py   (requires FRED_API_KEY)
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fred_client as fc

REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
DATA_PATH = os.path.join(REPO_ROOT, 'data.json')

SERIES = {
    'quitRate': 'JTSQUR',
    'jobOpenings': 'JTSJOL',
    'unemploymentLevel': 'UNEMPLOY',
    'hiresRate': 'JTSHIR',
    'layoffsRate': 'JTSLDR',
    'unempRate': 'UNRATE',
    'fedRate': 'FEDFUNDS',
    'avgHourlyEarnings': 'CES0500000003',
    'lfpr': 'LNS11300060',
    'uempMed': 'UEMPMED',
    'cpi': 'CPIAUCSL',
}

JOLTS_KEYS = ('quitRate', 'jobOpenings', 'hiresRate', 'layoffsRate')


def fetch_switcher_premium_with_fallback(dates):
    """Switcher premium aligned to the month grid, or last-known-good.

    Returns (values, source) where source is 'live', 'carried', or
    'unavailable'. The Atlanta Fed path must never break the FRED update.
    """
    try:
        import atlanta_fed
        by_date = atlanta_fed.fetch_switcher_premium()
        return [by_date.get(d) for d in dates], 'live'
    except Exception as e:  # noqa: BLE001 - any failure falls back to LKG
        print(f'  WARNING: switcher premium fetch failed ({e}); '
              'carrying previous values')
    try:
        with open(DATA_PATH) as f:
            old = json.load(f)
        old_by_label = dict(zip(old.get('labels', []),
                                old.get('switcherPremium', [])))
        if any(v is not None for v in old_by_label.values()):
            return [old_by_label.get(fc.date_to_label(d)) for d in dates], 'carried'
    except Exception:  # noqa: BLE001 - missing/corrupt old file: series absent
        pass
    return [None for _ in dates], 'unavailable'


def main():
    if not os.environ.get('FRED_API_KEY'):
        print('Error: FRED_API_KEY environment variable not set')
        print('Get a free API key at: https://fred.stlouisfed.org/docs/api/api_key.html')
        sys.exit(1)

    # Deliberate failure mode: any FRED series failing aborts the whole
    # refresh (data.json untouched) rather than writing a file with a
    # blanked column. The next scheduled run retries.
    print('Fetching data from FRED...')
    parsed = {}
    for name, series_id in SERIES.items():
        print(f'  Fetching {name} ({series_id})...')
        parsed[name] = fc.fetch_observations(series_id)

    dates = fc.month_grid(parsed.values())
    labels = [fc.date_to_label(d) for d in dates]

    wage_yoy = fc.yoy_growth(parsed['avgHourlyEarnings'])
    cpi_yoy = fc.yoy_growth(parsed['cpi'])

    def column(source):
        return [source.get(d) for d in dates]

    series = {
        'quitRate': column(parsed['quitRate']),
        'hiresRate': column(parsed['hiresRate']),
        'layoffsRate': column(parsed['layoffsRate']),
        'unempRate': column(parsed['unempRate']),
        'fedRate': column(parsed['fedRate']),
        'lfpr': column(parsed['lfpr']),
        'uempMed': column(parsed['uempMed']),
        'wageGrowth': column(wage_yoy),
    }
    series['openingsRatio'] = [
        round(o / u, 2) if o is not None and u else None
        for o, u in zip(column(parsed['jobOpenings']),
                        column(parsed['unemploymentLevel']))
    ]
    series['realWageGrowth'] = [
        round(w - c, 1) if w is not None and c is not None else None
        for w, c in zip(column(wage_yoy), column(cpi_yoy))
    ]

    print('Fetching Atlanta Fed switcher premium...')
    series['switcherPremium'], swp_source = fetch_switcher_premium_with_fallback(dates)

    # Trim to the last month where any indicator actually reported, so
    # non-JOLTS data (unemployment, wages) can appear before JOLTS catches up.
    last_idx = max(fc.last_valid_index(s) for s in series.values())
    if last_idx < 0:
        print('Error: No valid data found')
        sys.exit(1)
    dates = dates[:last_idx + 1]
    labels = labels[:last_idx + 1]
    series = {k: v[:last_idx + 1] for k, v in series.items()}

    for key in ('openingsRatio', 'unempRate', 'lfpr', 'wageGrowth',
                'uempMed', 'realWageGrowth'):
        series[key] = fc.interpolate_interior_nulls(series[key])

    jolts_idx = fc.last_valid_index(series['quitRate'])
    output = {
        'metadata': {
            'lastUpdated': datetime.now().strftime('%Y-%m-%d'),
            'dataThrough': dates[-1][:7],
            'joltsThrough': dates[jolts_idx][:7] if jolts_idx >= 0 else None,
            'switcherPremiumSource': swp_source,
            'description': 'Labor market indicators for job search timing decisions',
        },
        'labels': labels,
        'quitRate': series['quitRate'],
        'openingsRatio': series['openingsRatio'],
        'hiresRate': series['hiresRate'],
        'layoffsRate': series['layoffsRate'],
        'unempRate': series['unempRate'],
        'fedRate': series['fedRate'],
        'wageGrowth': series['wageGrowth'],
        'lfpr': series['lfpr'],
        'uempMed': series['uempMed'],
        'realWageGrowth': series['realWageGrowth'],
        'switcherPremium': series['switcherPremium'],
    }

    with open(DATA_PATH, 'w') as f:
        json.dump(output, f, indent=2)

    print('\nData updated successfully!')
    print(f"  Data through: {output['metadata']['dataThrough']}")
    print(f"  JOLTS through: {output['metadata']['joltsThrough'] or 'N/A'}")
    print(f'  Switcher premium: {swp_source} '
          f'(latest: {next((v for v in reversed(series["switcherPremium"]) if v is not None), None)})')
    print(f'  Total months: {len(labels)}')


if __name__ == '__main__':
    main()
