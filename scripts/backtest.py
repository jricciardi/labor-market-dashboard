#!/usr/bin/env python3
"""Backtest and vintage-analysis harness for the composite score.

This is the tool that found the 2026-05-07 fake-neutral artifact: it walks
every historical commit of data.json ("vintages") and recomputes the score
the dashboard *displayed* at that moment, for comparison against scores
computed on today's revised data. Keep it working — it is the project's
accuracy audit.

Usage:
  python scripts/backtest.py history [N]   score table for the last N months (default 24)
  python scripts/backtest.py vintage       displayed score per data.json commit
  python scripts/backtest.py compare       current model vs frozen v2, last 24 months
  python scripts/backtest.py slices        score table for each built slice
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score_model as sm

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def load_data():
    with open(os.path.join(REPO, 'data.json')) as f:
        return json.load(f)


# Frozen copy of the v2 model (shipped 2026-07-15, PR #9) for changeover
# comparisons. Do not edit — it documents what v2 was.
V2_COMPONENTS = [
    ('quitRate',       0.18, lambda v: (v - 1.5) / 1.5,  None, None),
    ('hiresRate',      0.18, lambda v: (v - 2.8) / 1.6,  None, None),
    ('openingsRatio',  0.12, lambda v: 0.35 * (v - 0.3) / 0.7 if v <= 1.0
                             else 0.35 + 0.65 * (v - 1.0), None, None),
    ('layoffsRate',    0.10, lambda v: (2.5 - v) / 1.7,  None, None),
    ('uempMed',        0.12, lambda v: (16 - v) / 8,     None, None),
    ('unempRate',      0.10, lambda v: (7.0 - v) / 3.5,  None, None),
    ('realWageGrowth', 0.12, lambda v: (v + 1.0) / 3.0,  'wageGrowth',
                             lambda v: (v - 2.0) / 3.0),
    ('lfpr',           0.08, lambda v: (v - 80.5) / 4.0, None, None),
]


def score_with(components, data, idx):
    """Score one month under an arbitrary component table (v2 replays)."""
    saved = sm.NATIONAL_COMPONENTS
    try:
        sm.NATIONAL_COMPONENTS = components
        return sm.national_score(data, idx)
    finally:
        sm.NATIONAL_COMPONENTS = saved


def cmd_history(n=24):
    data = load_data()
    scores = sm.national_scores(data)
    for i in range(max(0, len(scores) - n), len(scores)):
        print(f'  {data["labels"][i]:>7} {scores[i]}')
    label, score = sm.current_score(data)
    print(f'  DISPLAYED: {label} {score}')


def cmd_vintage():
    commits = subprocess.check_output(
        ['git', '-C', REPO, 'log', '--reverse', '--pretty=%h %ad',
         '--date=short', '--', 'data.json']).decode().strip().split('\n')
    prev = None
    for line in commits:
        sha, date = line.split()
        try:
            blob = subprocess.check_output(
                ['git', '-C', REPO, 'show', f'{sha}:data.json'],
                stderr=subprocess.DEVNULL)
            data = json.loads(blob)
        except Exception:  # noqa: BLE001 - unreadable vintage: skip
            continue
        label, score = sm.current_score(data)
        marker = '' if (label, score) == prev else '  <-- changed'
        print(f'  {date} ({sha}) displayed {score} (scored month {label}){marker}')
        prev = (label, score)


def cmd_compare(n=24):
    data = load_data()
    total = len(data['labels'])
    print(f'{"Month":>8} {"v2":>4} {"v" + sm.MODEL_VERSION:>5}')
    for i in range(max(0, total - n), total):
        v2 = score_with(V2_COMPONENTS, data, i)
        cur = sm.national_score(data, i)
        flag = '' if v2 == cur or v2 is None or cur is None or abs(v2 - cur) <= 3 else '  <-- >3pt shift'
        print(f'{data["labels"][i]:>8} {str(v2):>4} {str(cur):>5}{flag}')


def cmd_slices():
    slices_dir = os.path.join(REPO, 'data', 'slices')
    if not os.path.isdir(slices_dir):
        print('No data/slices/ — run update_slices.py first.')
        return
    for name in sorted(os.listdir(slices_dir)):
        if name == 'index.json' or not name.endswith('.json'):
            continue
        with open(os.path.join(slices_dir, name)) as f:
            doc = json.load(f)
        scores = sm.slice_scores(doc)
        recent = [(lbl, s) for lbl, s in zip(doc['labels'], scores) if s is not None][-6:]
        print(f'  {doc["meta"]["slug"]:<24} margin ±{doc["meta"]["margin"]}  '
              + '  '.join(f'{lbl}:{s}' for lbl, s in recent))


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'history'
    arg = int(sys.argv[2]) if len(sys.argv) > 2 else None
    if mode == 'history':
        cmd_history(arg or 24)
    elif mode == 'vintage':
        cmd_vintage()
    elif mode == 'compare':
        cmd_compare(arg or 24)
    elif mode == 'slices':
        cmd_slices()
    else:
        print(__doc__)
