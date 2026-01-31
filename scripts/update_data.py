#!/usr/bin/env python3
"""
Fetch latest labor market data from FRED and update data.json

FRED Series used:
- JTSQUR: Quit rate (total nonfarm)
- JTSJOL: Job openings level (thousands)
- UNEMPLOY: Unemployment level (thousands)  
- JTSHIR: Hires rate (total nonfarm)
- JTSLDR: Layoffs and discharges rate (total nonfarm)
- UNRATE: Unemployment rate
- FEDFUNDS: Federal funds effective rate
- CES0500000003: Average hourly earnings, private (for YoY wage growth)
- LNS11300060: Labor force participation rate, 25-54 years

Run with: python update_data.py
Requires FRED_API_KEY environment variable
"""

import json
import os
import sys
from datetime import datetime, timedelta
from urllib.request import urlopen
from urllib.error import URLError
import urllib.parse

FRED_API_KEY = os.environ.get('FRED_API_KEY')
FRED_BASE_URL = 'https://api.stlouisfed.org/fred/series/observations'

# FRED series IDs
SERIES = {
    'quitRate': 'JTSQUR',
    'jobOpenings': 'JTSJOL',  # Level, for calculating ratio
    'unemploymentLevel': 'UNEMPLOY',  # Level, for calculating ratio
    'hiresRate': 'JTSHIR',
    'layoffsRate': 'JTSLDR',
    'unempRate': 'UNRATE',
    'fedRate': 'FEDFUNDS',
    'avgHourlyEarnings': 'CES0500000003',  # For calculating YoY wage growth
    'lfpr': 'LNS11300060',
}

def fetch_fred_series(series_id, start_date='2015-01-01'):
    """Fetch a single series from FRED API"""
    params = {
        'series_id': series_id,
        'api_key': FRED_API_KEY,
        'file_type': 'json',
        'observation_start': start_date,
        'sort_order': 'asc',
    }
    url = f"{FRED_BASE_URL}?{urllib.parse.urlencode(params)}"
    
    try:
        with urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode())
            return data.get('observations', [])
    except URLError as e:
        print(f"Error fetching {series_id}: {e}")
        return []

def parse_observation(obs):
    """Parse a FRED observation, returning (date, value) or None if missing"""
    date_str = obs.get('date', '')
    value_str = obs.get('value', '.')
    
    if value_str == '.' or value_str == '':
        return date_str, None
    
    try:
        return date_str, float(value_str)
    except ValueError:
        return date_str, None

def date_to_label(date_str):
    """Convert YYYY-MM-DD to Mon-YY format"""
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    return dt.strftime('%b-%y')

def calculate_yoy_growth(values_by_date):
    """Calculate year-over-year growth rates"""
    sorted_dates = sorted(values_by_date.keys())
    growth = {}
    
    for date_str in sorted_dates:
        current = values_by_date.get(date_str)
        if current is None:
            growth[date_str] = None
            continue
            
        # Find value from 12 months ago
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        year_ago = dt - timedelta(days=365)
        year_ago_str = year_ago.strftime('%Y-%m-%d')
        
        # Look for closest date within a few days
        past_value = None
        for offset in range(0, 10):
            check_date = (year_ago + timedelta(days=offset)).strftime('%Y-%m-%d')
            if check_date in values_by_date:
                past_value = values_by_date[check_date]
                break
            check_date = (year_ago - timedelta(days=offset)).strftime('%Y-%m-%d')
            if check_date in values_by_date:
                past_value = values_by_date[check_date]
                break
        
        if past_value is not None and past_value != 0:
            growth[date_str] = round(((current - past_value) / past_value) * 100, 1)
        else:
            growth[date_str] = None
    
    return growth

def main():
    if not FRED_API_KEY:
        print("Error: FRED_API_KEY environment variable not set")
        print("Get a free API key at: https://fred.stlouisfed.org/docs/api/api_key.html")
        sys.exit(1)
    
    print("Fetching data from FRED...")
    
    # Fetch all series
    raw_data = {}
    for name, series_id in SERIES.items():
        print(f"  Fetching {name} ({series_id})...")
        raw_data[name] = fetch_fred_series(series_id)
    
    # Parse into date-indexed dictionaries
    parsed = {}
    for name, observations in raw_data.items():
        parsed[name] = {}
        for obs in observations:
            date_str, value = parse_observation(obs)
            if date_str:
                parsed[name][date_str] = value
    
    # Get all unique month-start dates across all series
    all_dates = set()
    for name, data in parsed.items():
        all_dates.update(data.keys())
    
    # Filter to first of month only and sort
    monthly_dates = sorted([d for d in all_dates if d.endswith('-01')])
    
    # Build output arrays
    labels = []
    quit_rate = []
    openings_ratio = []
    hires_rate = []
    layoffs_rate = []
    unemp_rate = []
    fed_rate = []
    wage_growth = []
    lfpr = []
    
    # Calculate wage growth (YoY)
    wage_yoy = calculate_yoy_growth(parsed['avgHourlyEarnings'])
    
    for date_str in monthly_dates:
        label = date_to_label(date_str)
        labels.append(label)
        
        # Direct mappings
        quit_rate.append(parsed['quitRate'].get(date_str))
        hires_rate.append(parsed['hiresRate'].get(date_str))
        layoffs_rate.append(parsed['layoffsRate'].get(date_str))
        unemp_rate.append(parsed['unempRate'].get(date_str))
        fed_rate.append(parsed['fedRate'].get(date_str))
        lfpr.append(parsed['lfpr'].get(date_str))
        wage_growth.append(wage_yoy.get(date_str))
        
        # Calculate openings ratio (job openings / unemployment level)
        openings = parsed['jobOpenings'].get(date_str)
        unemp_level = parsed['unemploymentLevel'].get(date_str)
        if openings is not None and unemp_level is not None and unemp_level > 0:
            ratio = round(openings / unemp_level, 2)
            openings_ratio.append(ratio)
        else:
            openings_ratio.append(None)
    
    # Find the last date with actual JOLTS data (quit rate is a good proxy)
    last_data_idx = len(quit_rate) - 1
    while last_data_idx >= 0 and quit_rate[last_data_idx] is None:
        last_data_idx -= 1
    
    if last_data_idx < 0:
        print("Error: No valid data found")
        sys.exit(1)
    
    # Trim arrays to last available data point
    trim_to = last_data_idx + 1
    labels = labels[:trim_to]
    quit_rate = quit_rate[:trim_to]
    openings_ratio = openings_ratio[:trim_to]
    hires_rate = hires_rate[:trim_to]
    layoffs_rate = layoffs_rate[:trim_to]
    unemp_rate = unemp_rate[:trim_to]
    fed_rate = fed_rate[:trim_to]
    wage_growth = wage_growth[:trim_to]
    lfpr = lfpr[:trim_to]
    
    # Determine data coverage
    last_label = labels[-1]  # e.g., "Nov-25"
    last_month_dt = datetime.strptime(f"01-{last_label}", "%d-%b-%y")
    data_through = last_month_dt.strftime('%Y-%m')
    
    # Build output JSON
    output = {
        "metadata": {
            "lastUpdated": datetime.now().strftime('%Y-%m-%d'),
            "dataThrough": data_through,
            "description": "Labor market indicators for job search timing decisions"
        },
        "labels": labels,
        "quitRate": quit_rate,
        "openingsRatio": openings_ratio,
        "hiresRate": hires_rate,
        "layoffsRate": layoffs_rate,
        "unempRate": unemp_rate,
        "fedRate": fed_rate,
        "wageGrowth": wage_growth,
        "lfpr": lfpr
    }
    
    # Write to data.json
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, '..', 'data.json')
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nData updated successfully!")
    print(f"  Last updated: {output['metadata']['lastUpdated']}")
    print(f"  Data through: {output['metadata']['dataThrough']}")
    print(f"  Total months: {len(labels)}")
    print(f"  Latest quit rate: {quit_rate[-1]}")
    print(f"  Latest openings ratio: {openings_ratio[-1]}")

if __name__ == '__main__':
    main()
