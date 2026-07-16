"""Atlanta Fed Wage Growth Tracker: job switcher vs stayer premium.

The tracker publishes median 12-month wage growth for job switchers and job
stayers (3-month moving averages) as a downloadable Excel workbook. The
switcher premium — switcher minus stayer, in percentage points — is the
dashboard's "does moving actually pay right now?" component.

This fetcher is deliberately paranoid: the workbook's exact layout is not a
stable API, so we locate the data by header text rather than by position,
and we fail loudly with diagnostics rather than guessing. Callers fall back
to last-known-good values (see update_data.py) so a broken download or a
reshuffled spreadsheet can never blank out the published series.

Requires openpyxl (installed by the GitHub Actions workflow); import is
deferred so the FRED-only path has no third-party dependency.
"""

import io
import re
from datetime import datetime
from urllib.request import Request, urlopen

WORKBOOK_URLS = [
    # Primary and historical locations; verify_sources.py probes these and
    # records which resolve, plus the workbook structure it finds.
    'https://www.atlantafed.org/-/media/documents/datafiles/chcs/wage-growth-tracker/wage-growth-data.xlsx',
]
_UA = {'User-Agent': 'labor-market-dashboard/1.0 (github.com/jricciardi/labor-market-dashboard)'}

_SWITCHER = re.compile(r'switcher', re.I)
_STAYER = re.compile(r'stayer', re.I)


class AtlantaFedError(RuntimeError):
    """Raised when the tracker workbook can't be fetched or understood."""


def _download(url, timeout=60):
    with urlopen(Request(url, headers=_UA), timeout=timeout) as resp:
        return resp.read()


def _parse_date(cell):
    """Tracker date cells: datetimes, 'YYYY-MM', or 'Mon-YY' strings."""
    if isinstance(cell, datetime):
        return cell.strftime('%Y-%m-01')
    if isinstance(cell, str):
        for fmt in ('%Y-%m-%d', '%Y-%m', '%b-%y', '%b-%Y', '%m/%d/%Y'):
            try:
                return datetime.strptime(cell.strip(), fmt).strftime('%Y-%m-01')
            except ValueError:
                continue
    return None


def _find_columns(rows):
    """Locate (header_row_idx, switcher_col, stayer_col) by header text.

    Scans the first few rows for cells matching /switcher/i and /stayer/i.
    Returns None if the sheet doesn't carry both series.
    """
    for row_idx, row in enumerate(rows[:10]):
        switcher = stayer = None
        for col_idx, cell in enumerate(row):
            if not isinstance(cell, str):
                continue
            if _SWITCHER.search(cell):
                switcher = col_idx
            elif _STAYER.search(cell):
                stayer = col_idx
        if switcher is not None and stayer is not None:
            return row_idx, switcher, stayer
    return None


def parse_workbook(content):
    """Extract {YYYY-MM-01: (switcher, stayer)} from workbook bytes."""
    import openpyxl  # deferred: only the switcher path needs it

    workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    tried = []
    for sheet in workbook.worksheets:
        rows = [list(r) for r in sheet.iter_rows(values_only=True)]
        found = _find_columns(rows)
        if not found:
            tried.append(sheet.title)
            continue
        header_idx, sw_col, st_col = found
        series = {}
        for row in rows[header_idx + 1:]:
            if not row:
                continue
            date = _parse_date(row[0])
            if date is None:
                continue
            sw = row[sw_col] if sw_col < len(row) else None
            st = row[st_col] if st_col < len(row) else None
            if isinstance(sw, (int, float)) and isinstance(st, (int, float)):
                series[date] = (float(sw), float(st))
        if series:
            return series
        tried.append(f'{sheet.title} (headers found, no parseable rows)')
    raise AtlantaFedError(
        'no sheet with switcher+stayer columns and data; inspected: ' + ', '.join(tried))


def fetch_switcher_premium(start='2015-01-01'):
    """Return {YYYY-MM-01: premium_pp} — switcher minus stayer wage growth.

    Only the published 3MMA series are used upstream (the matched-CPS cell is
    too small for unsmoothed monthly reads); if the workbook carries both
    smoothed and unsmoothed variants, header matching prefers whichever sheet
    lists them first, so verify_sources.py's structure dump is the check that
    we're reading the smoothed cut.
    """
    errors = []
    for url in WORKBOOK_URLS:
        try:
            series = parse_workbook(_download(url))
            return {
                date: round(sw - st, 2)
                for date, (sw, st) in sorted(series.items())
                if date >= start
            }
        except Exception as e:  # noqa: BLE001 - every failure type falls through to LKG
            errors.append(f'{url}: {e}')
    raise AtlantaFedError('; '.join(errors))
