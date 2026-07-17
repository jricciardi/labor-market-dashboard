"""Python mirror of the dashboard's score model.

`index.html` (SCORE_COMPONENTS) is the display-time authority; this module
must stay in lockstep with it. It exists so the pipeline and the backtest can
score months in Python — for validation, per-slice face-validity checks, and
vintage analysis. The browser smoke test compares the two implementations'
current score to catch drift.

Two scorers live here:
  - the NATIONAL model (v2.1): fixed linear anchors, hand-set in code, same
    values as index.html;
  - the SLICE model: identical weighted-average machinery, but normalization
    anchors are data-driven (fit by update_slices.py, carried in each slice
    JSON) per docs/sector-methodology-plan.md section 5.3.
"""

import math

MODEL_VERSION = '2.1'
CARRY_LIMIT = 3  # max months a stale value may stand in for a missing one


def clamp(x):
    return min(1.0, max(0.0, x))


def round_half_up(x):
    """JS Math.round semantics; Python's round() is half-to-even, which can
    disagree with the browser by 1 point exactly on tier boundaries."""
    return math.floor(x + 0.5)


def _ratio_norm(v):
    # Piecewise: steeper below 1.0, where every hundredth means more
    # competition per opening. Mirrors index.html exactly.
    return 0.35 * (v - 0.3) / 0.7 if v <= 1.0 else 0.35 + 0.65 * (v - 1.0)


# key, weight, norm, fallback_key, fallback_norm
# Weights are the v2.1 table from docs/sector-methodology-plan.md section 2
# and must sum to 1.00.
NATIONAL_COMPONENTS = [
    ('quitRate',        0.16, lambda v: (v - 1.5) / 1.5,   None, None),
    ('hiresRate',       0.16, lambda v: (v - 2.8) / 1.6,   None, None),
    ('switcherPremium', 0.12, lambda v: (v + 0.5) / 3.0,   None, None),
    ('uempMed',         0.12, lambda v: (16 - v) / 8,      None, None),
    ('openingsRatio',   0.10, _ratio_norm,                 None, None),
    ('realWageGrowth',  0.10, lambda v: (v + 1.0) / 3.0,   'wageGrowth',
                              lambda v: (v - 2.0) / 3.0),
    ('layoffsRate',     0.08, lambda v: (2.5 - v) / 1.7,   None, None),
    ('unempRate',       0.08, lambda v: (7.0 - v) / 3.5,   None, None),
    ('lfpr',            0.08, lambda v: (v - 80.5) / 4.0,  None, None),
]

assert abs(sum(w for _, w, *_ in NATIONAL_COMPONENTS) - 1.0) < 1e-9, \
    'national component weights must sum to 1.00'


def _series_value(data, key, idx):
    arr = data.get(key) or []
    return arr[idx] if idx < len(arr) else None


def values_at(data, idx, carry_limit=CARRY_LIMIT):
    """Collect component inputs for one month, carrying stale values forward."""
    out = {}
    for key, _, _, fallback, _ in NATIONAL_COMPONENTS:
        for k in (key, fallback):
            if not k or k in out:
                continue
            v = _series_value(data, k, idx)
            if v is None:
                for p in range(idx - 1, max(idx - carry_limit, 0) - 1, -1):
                    if _series_value(data, k, p) is not None:
                        v = _series_value(data, k, p)
                        break
            out[k] = v
    return out


def score_from_values(values):
    """Weighted average over available components; weights renormalize.

    Returns None when the month isn't scorable (quits/ratio missing or less
    than half the weight present) — mirrors index.html scoreFromValues.
    """
    num = den = 0.0
    have = set()
    for key, weight, norm, fallback, fallback_norm in NATIONAL_COMPONENTS:
        v, n = values.get(key), norm
        if v is None and fallback:
            v, n = values.get(fallback), fallback_norm
        if v is None:
            continue
        have.add(key)
        num += clamp(n(v)) * weight
        den += weight
    if 'quitRate' not in have or 'openingsRatio' not in have or den < 0.5:
        return None
    return min(100, round_half_up(num / den * 100))


def has_real_scored_data(data, idx):
    """True when at least one scored series actually reported this month."""
    for key, _, _, fallback, _ in NATIONAL_COMPONENTS:
        if _series_value(data, key, idx) is not None:
            return True
        if fallback and _series_value(data, fallback, idx) is not None:
            return True
    return False


def national_score(data, idx):
    if not has_real_scored_data(data, idx):
        return None
    return score_from_values(values_at(data, idx))


def national_scores(data):
    return [national_score(data, i) for i in range(len(data['labels']))]


def current_score(data):
    """(label, score) the dashboard would display: last scorable month."""
    scores = national_scores(data)
    for i in range(len(scores) - 1, -1, -1):
        if scores[i] is not None:
            return data['labels'][i], scores[i]
    return None, None


# ---------------------------------------------------------------------------
# Slice scoring: anchors come from data, machinery stays identical.
# ---------------------------------------------------------------------------

def normalize(value, anchors):
    """Map a raw value to [0,1] using percentile anchors from a slice file.

    anchors: {lo, hi, inverted} where lo maps to 0.05 and hi to 0.95 —
    the p5/p95 fit in fred_client.fit_anchors. Inverted flips the scale so
    higher normalized always means better for workers.
    """
    lo, hi = anchors['lo'], anchors['hi']
    if hi == lo:
        return None
    t = 0.05 + 0.90 * (value - lo) / (hi - lo)
    if anchors.get('inverted'):
        t = 1.0 - t
    return clamp(t)


SLICE_REQUIRED = ('quitRate', 'hiresRate')       # industry axis: leverage core
OCCUPATION_REQUIRED = ('postings', 'unempRate')  # role axis: demand + slack


def slice_score_at(components, idx, carry_limit=CARRY_LIMIT,
                   required=SLICE_REQUIRED):
    """Score one month of a slice/overlay from its JSON `components` block.

    components: {key: {weight, norm: {lo,hi,inverted}, values: [...]}}.
    Requires every `required` key (the axis' defining signals) and at least
    half of the document's total weight present, else None.
    """
    num = den = total = 0.0
    have = set()
    for key, comp in components.items():
        total += comp['weight']
        values = comp['values']
        v = values[idx] if idx < len(values) else None
        if v is None:
            for p in range(idx - 1, max(idx - carry_limit, 0) - 1, -1):
                if p < len(values) and values[p] is not None:
                    v = values[p]
                    break
        if v is None:
            continue
        norm = normalize(v, comp['norm'])
        if norm is None:
            continue
        have.add(key)
        num += norm * comp['weight']
        den += comp['weight']
    if any(k not in have for k in required) or den < total * 0.5:
        return None
    return min(100, round_half_up(num / den * 100))


def required_for(doc):
    """Axis-appropriate required keys for a slice/overlay document."""
    kind = doc.get('meta', {}).get('kind', 'industry')
    return OCCUPATION_REQUIRED if kind == 'occupation' else SLICE_REQUIRED


def slice_scores(slice_doc):
    comps = slice_doc['components']
    n = len(slice_doc['labels'])
    required = required_for(slice_doc)
    return [slice_score_at(comps, i, required=required) for i in range(n)]
