"""Shared FRED access and monthly-series transforms for the data pipeline.

Every function here is pure stdlib. Scripts import this module by path
(they live in the same directory), so no packaging is required:

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import fred_client
"""

import json
import os
import urllib.parse
from datetime import datetime, timedelta
from urllib.error import URLError
from urllib.request import urlopen

FRED_BASE = 'https://api.stlouisfed.org/fred'


class FredError(RuntimeError):
    """Raised when FRED cannot be reached or returns an error payload."""


def _api_key():
    key = os.environ.get('FRED_API_KEY')
    if not key:
        raise FredError('FRED_API_KEY environment variable not set')
    return key


def _get_json(endpoint, params, timeout=30):
    params = dict(params, api_key=_api_key(), file_type='json')
    url = f"{FRED_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    try:
        with urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except URLError as e:
        raise FredError(f'FRED request failed for {endpoint} '
                        f'({params.get("series_id", "?")}): {e}') from e


def fetch_series_meta(series_id):
    """Return FRED metadata for a series id, or None if the id is unknown.

    Metadata (title, seasonal adjustment, date range) is how we verify that
    a candidate id means what we think it means before trusting its data.
    """
    try:
        payload = _get_json('series', {'series_id': series_id})
    except FredError:
        raise
    except Exception:
        return None
    seriess = payload.get('seriess') or []
    return seriess[0] if seriess else None


def fetch_observations(series_id, start_date='2015-01-01'):
    """Return {YYYY-MM-DD: float|None} for a series' monthly observations."""
    payload = _get_json('series/observations', {
        'series_id': series_id,
        'observation_start': start_date,
        'sort_order': 'asc',
    })
    out = {}
    for obs in payload.get('observations', []):
        date_str = obs.get('date', '')
        value_str = obs.get('value', '.')
        if not date_str:
            continue
        try:
            out[date_str] = float(value_str)
        except ValueError:
            out[date_str] = None
    return out


# ---------------------------------------------------------------------------
# Monthly-grid transforms. All operate on {date_str: value} maps or plain
# lists aligned to a labels grid, and all treat None as "missing".
# ---------------------------------------------------------------------------

def month_grid(date_maps, start='2015-01-01'):
    """Union of first-of-month dates across the given {date: value} maps."""
    dates = set()
    for m in date_maps:
        dates.update(d for d in m if d.endswith('-01') and d >= start)
    return sorted(dates)


def monthly_mean(obs_map):
    """Collapse a daily/weekly {date: value} map to {YYYY-MM-01: mean}.

    Used for the Indeed postings indexes, which FRED publishes at daily
    cadence; the pipeline's grid is monthly.
    """
    buckets = {}
    for date_str, v in obs_map.items():
        if v is None:
            continue
        buckets.setdefault(date_str[:7], []).append(v)
    return {f'{month}-01': round(sum(vals) / len(vals), 1)
            for month, vals in buckets.items()}


def date_to_label(date_str):
    """YYYY-MM-DD -> Mon-YY (the dashboard's label format)."""
    return datetime.strptime(date_str, '%Y-%m-%d').strftime('%b-%y')


def yoy_growth(values_by_date):
    """Year-over-year percent change per date, tolerant of ragged month keys."""
    growth = {}
    for date_str in sorted(values_by_date):
        current = values_by_date.get(date_str)
        if current is None:
            growth[date_str] = None
            continue
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        year_ago = dt - timedelta(days=365)
        past = None
        for offset in range(0, 10):
            for candidate in (year_ago + timedelta(days=offset),
                              year_ago - timedelta(days=offset)):
                key = candidate.strftime('%Y-%m-%d')
                if key in values_by_date:
                    past = values_by_date[key]
                    break
            if past is not None:
                break
        if past:
            growth[date_str] = round((current - past) / past * 100, 1)
        else:
            growth[date_str] = None
    return growth


def moving_average(series, window, min_periods=None):
    """Trailing moving average over a list.

    Requires a full window of positions; min_periods (default: the full
    window) sets how many non-None values must be present. A long NSA
    average (e.g. 12MMA) can tolerate a stray missing month via
    min_periods without letting one gap null out a year of output.
    """
    need = window if min_periods is None else min_periods
    out = []
    for i in range(len(series)):
        tail = series[max(0, i - window + 1):i + 1]
        vals = [v for v in tail if v is not None]
        if len(tail) == window and len(vals) >= need:
            out.append(round(sum(vals) / len(vals), 2))
        else:
            out.append(None)
    return out


def interpolate_interior_nulls(series):
    """Linearly fill null runs that have real data on both sides."""
    result = list(series)
    n = len(result)
    i = 0
    while i < n:
        if result[i] is None:
            start = i
            while i < n and result[i] is None:
                i += 1
            end = i
            if start > 0 and end < n and result[start - 1] is not None and result[end] is not None:
                span = end - start + 1
                for j in range(start, end):
                    t = (j - start + 1) / span
                    result[j] = round(result[start - 1] + t * (result[end] - result[start - 1]), 2)
        else:
            i += 1
    return result


def last_valid_index(series):
    for i in range(len(series) - 1, -1, -1):
        if series[i] is not None:
            return i
    return -1


def percentile(sorted_values, p):
    """Linear-interpolation percentile (p in [0,1]) of a pre-sorted list."""
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = p * (len(sorted_values) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = rank - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


PANDEMIC_WINDOW = ('2020-03-01', '2020-12-01')


def add_months(date_str, n):
    """YYYY-MM-01 plus n months."""
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    total = dt.year * 12 + (dt.month - 1) + n
    return f'{total // 12:04d}-{total % 12 + 1:02d}-01'


def fit_anchors(dates, values, inverted, lo_p=0.05, hi_p=0.95, window=1):
    """Fit percentile normalization anchors per the v3 methodology plan.

    Uses the series' own 2015-present history, excluding Mar-Dec 2020 so the
    COVID shock doesn't stretch the scale. `window` is the trailing-average
    width of the values being fit: a smoothed observation dated after the
    pandemic still contains pandemic months until `window - 1` months have
    passed, so the exclusion end extends accordingly. Returns
    {lo, hi, inverted} where lo maps to normalized 0.05 and hi to 0.95
    (see score_model.normalize).
    """
    exclude_end = add_months(PANDEMIC_WINDOW[1], window - 1)
    sample = sorted(
        v for d, v in zip(dates, values)
        if v is not None and not (PANDEMIC_WINDOW[0] <= d <= exclude_end)
    )
    if len(sample) < 24:  # need a couple of years of data to calibrate
        return None
    return {
        'lo': round(percentile(sample, lo_p), 3),
        'hi': round(percentile(sample, hi_p), 3),
        'inverted': inverted,
    }
