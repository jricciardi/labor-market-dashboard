# Sector & Occupation Extension — Methodology Plan (score model v3)

**Status:** PLAN — not yet implemented. Written July 2026 against score model v2.
**Prereq reading:** `docs/methodology.md` (v2 model), `index.html` `SCORE_COMPONENTS` config.
**Companion:** Phase 0 (switcher premium) is a committed decision; Phases 1–3 are designs to validate before building.

---

## 0. Purpose and design constraints

Extend the national 0–100 score so a specific person — the motivating persona is a **program manager at Microsoft** (a non-technical role at a tech company) — can see *their* market, not the average of all markets. Constraints:

1. **Survive economist scrutiny.** Every series must have a documented source, cadence, lag, seasonal-adjustment status, sample-size caveat, and revision behavior. Every transform must be reproducible from the pipeline code.
2. **Industry ≠ occupation.** NAICS classifies the *employer*; SOC classifies the *work*. A PM at Microsoft is Information-sector (NAICS 513) by employer but management/business-operations (SOC 11-3/13-1) by role. Both axes carry signal; conflating them is the #1 way this feature would mislead.
3. **Don't fabricate.** Where a slice lacks a component's data, the component drops and weights renormalize (the v2 machinery already does this). No proxy is silently substituted; every proxy is labeled.
4. **Honest resolution.** Sliced estimates are noisier than national. Each slice gets its own empirically justified margin, and the UI must say "±8" where ±8 is the truth.

---

## 1. The two-axis problem and the persona model

**Model:** a *persona* = (occupation family) × (industry blend), scored as:

```
persona_score = α · Σ_i  w_i(occ) · industry_score_i  +  (1 − α) · occupation_overlay_score
```

- `w_i(occ)` — the share of that occupation's employment in industry *i*, taken from the **BLS OEWS national industry–occupation staffing matrix** (annual, published every spring for the prior May). This is the defensible answer to "how much does the tech sector's health matter to a PM?": weight industries by where PMs actually work, not by intuition.
- `occupation_overlay_score` — built from occupation-axis series (§4B): occupation-level postings, occupation unemployment, occupation wage growth.
- `α` — default 0.5, exposed as a UI toggle ("my market is mostly my industry" ↔ "mostly my role"), because the true mixing ratio is person-specific (a PM deeply specialized in cloud infrastructure is more industry-bound than a generalist PM). Document that α is a preference, not an estimate.

Rationale for a blend rather than a single crossed cell: BLS does not publish monthly flows (quits/hires/layoffs) at industry×occupation cells; no defensible monthly series exists at that resolution. The blend uses real data on each axis and makes the combination explicit and tunable instead of pretending a crossed cell exists.

---

## 2. Phase 0 (committed): Atlanta Fed switcher premium — national

The single most decision-relevant series for this dashboard's core question ("should I invest time in a search?") that we don't already have.

| Item | Spec |
|---|---|
| Source | Atlanta Fed **Wage Growth Tracker** (CPS matched microdata), job-switcher vs job-stayer median 12-month wage growth, 3-month moving average |
| Access | Downloadable spreadsheet/CSV from atlantafed.org/chcs/wage-growth-tracker (no API key; cite per their terms). **Not on FRED** — needs a second fetcher in `update_data.py` with independent failure handling (a broken Atlanta Fed download must not block the FRED update) |
| Cadence / lag | Monthly, ~1 month lag (tracks CPS) |
| Transform | `switcherPremium = switcher_3mma − stayer_3mma` (percentage points) |
| Meaning | >1.5pp: market pays you to move (2015–2019 ≈ 1.0–1.3; 2022 peak ≈ 2.5+). ≈0pp: switching doesn't pay (2010–11 and 2024–25 lows; can go negative in recessions) |
| Normalization (provisional) | `(SWP + 0.5) / 3.0` → −0.5pp = 0, +2.5pp = 1. **Verify against full downloaded history before shipping; prefer the percentile method in §5.3 if it disagrees materially** |
| Sample-size caveat | Matched-CPS cell is small; use only the published 3MMA series, never the unsmoothed monthly |

**Weight rebalance (national v2.1, must sum to 1.00):**

| Component | v2 | v2.1 | Note |
|---|---|---|---|
| Hiring rate | .18 | .16 | |
| Quit rate | .18 | .16 | |
| **Switcher premium** | — | **.12** | directly prices the switch decision |
| Unemployment duration | .12 | .12 | |
| Jobs per seeker | .12 | .10 | |
| Real wage growth | .12 | .10 | partial overlap with SWP (both wage signals) |
| Layoffs | .10 | .08 | |
| Unemployment rate | .10 | .08 | |
| Participation | .08 | .08 | |

Re-run the full vintage backtest (`scratchpad/score_v2.py` pattern — reconstruct it from `docs/methodology.md` + this file if the scratchpad is gone) before/after; the tier verdict for the last 12 months should not change more than ±1 month at any boundary, else re-tune.

**Verification tasks before coding:** (a) exact download URL + file format stability; (b) whether the tracker publishes switcher/stayer **crossed with** occupation or industry groups (believed *not* crossed — if true, SWP stays a national-only overlay applied to every slice, clearly labeled); (c) license/citation text.

---

## 3. Slice taxonomy — and where official groupings mislead

Launch slices (chosen for JOLTS supersector data availability + audience relevance), with the disaggregation problems named up front:

| Slice | Official basis | Squashed-together problem | Our treatment |
|---|---|---|---|
| **Tech (software & IT services)** | No clean NAICS match | "Information" (51) includes broadcasting, telecom, news; software publishing is 513, but computer-systems-design (5415) sits inside **Professional & Business Services** | Composite slice: JOLTS Information as flow proxy, **labeled as proxy**; overlay CES 5415 + 513 employment/earnings trends; postings from Indeed software/IT categories. Show the definition in the UI ("what counts as tech here") |
| **Professional & Business Services** | NAICS 54–56 supersector | Lawyers, consultants, engineers (54) squashed with temp agencies, janitorial, waste services (56). Temp help (561320) is its own leading indicator | Report supersector JOLTS but overlay CES 54 vs 56 employment growth split; break out **temp-help employment** as a leading-indicator chip, not a scored component |
| **Health Care & Social Assistance** | NAICS 62 | Hospitals vs home health vs childcare: very different pay/dynamics | Supersector score + CES sub-industry wage/employment context chips |
| **Financial Activities** | NAICS 52–53 | Banking squashed with real estate | Supersector score; note the split |
| **Manufacturing** | NAICS 31–33 | Durable vs nondurable diverge in cycles | JOLTS publishes durable/nondurable separately — use both, default combined |
| **Leisure & Hospitality** | NAICS 71–72 | High-churn structural baseline (quit rate ~2× national) | Percentile normalization (§5.3) makes within-industry comparison valid; cross-industry chip (§6.3) handles the rest |
| **Government** | Federal vs S&L | 2025–26 federal RIFs make "government" as one bucket actively misleading | JOLTS has federal vs state/local series — keep separate; never merge |
| **Retail Trade** | NAICS 44–45 | E-commerce warehousing lives in Transportation & Warehousing, not Retail | Name it in the slice description; offer T&W as its own slice later |

Occupation families for overlays (SOC-based, chosen for data coverage): Management & Business Operations (11-x, 13-1) — *includes PM*; Computer & Mathematical (15-x); Healthcare Practitioners (29-x); Office & Administrative (43-x); Sales (41-x); Production/Transport (51/53).

**PM-specific note:** SOC 13-1082 "Project Management Specialists" only became a distinct code in the 2018 SOC revision — OEWS history starts ~2021 (short-history caveat); program managers at tech firms are variously coded 13-1082, 11-3021 (computer & IS managers), or 13-1111 (management analysts). The occupation family (not a single code) is the honest resolution.

---

## 4. Data inventory (per component × axis)

Column "V?" = series ID pattern needs verification at implementation time (IDs below are from memory and must be confirmed against FRED/BLS before use).

### 4A. Industry axis (monthly flows exist — this is the strong axis)

| Component | Series (Information example) | SA? | Caveats | V? |
|---|---|---|---|---|
| Quit rate | FRED `JTS5100QUR` (pattern `JTS{naics}00QUR`) | SA | JOLTS industry cells have materially larger SEs than total nonfarm → 3MMA required (§5.1) | ✔ |
| Hires rate | `JTS5100HIR` | SA | same | ✔ |
| Layoffs rate | `JTS5100LDR` | SA | same; small cells are spiky | ✔ |
| Openings | `JTS5100JOL` | SA | ghost-postings caveat is *worse* at industry level (posting norms differ by sector) — keep the reduced weight | ✔ |
| Jobs-per-seeker denominator | Unemployed by industry of last job, CPS (`LNU033242xx` family) | **NSA only** | must use 12-month MA or YoY framing (§5.2); excludes new entrants by construction | ✔ |
| Real wage growth | CES AHE by supersector (`CES5000000003` pattern) minus national CPI | SA | industry CPI does not exist; deflating by national CPI is standard practice — document it | ✔ |
| Unemployment rate | Unemployed by industry (CPS, NSA) ÷ industry labor force proxy | NSA | noisy; consider dropping for slices and letting weights renormalize rather than shipping a bad number | ✔ |
| Duration | **No monthly industry cut published** | — | drops out per-slice; renormalization handles it; national duration shown as context | — |
| Participation | No industry meaning | — | drops out | — |
| Switcher premium | National overlay (§2) | — | labeled "national, all industries" | — |

### 4B. Occupation axis (levels & wages, sparser — the overlay axis)

| Signal | Source | Cadence/lag | Caveats | V? |
|---|---|---|---|---|
| Postings by occupational category | **Indeed Hiring Lab** (github.com/hiring-lab), categories include software development AND project management; some categories mirrored on FRED (`IHLIDX*`) | Weekly, ~days lag | Private source; level shifts when Indeed changes methodology — use YoY / index-vs-own-history, subscribe to their changelog | ✔ |
| Unemployment rate by occupation | CPS (`LNU0403x` family) | Monthly, NSA | 12MMA mandatory; occupation of *last job* | ✔ |
| Wage growth by occupation group | Atlanta Fed WGT occupation cut | Monthly 3MMA | verify exact groups published | ✔ |
| Employment & wage levels by detailed SOC | OEWS | Annual, ~1yr lag | levels not flows — context, not score |  |
| Staffing matrix (persona weights `w_i`) | OEWS national industry–occupation matrix | Annual | refresh weights once/year at build time |  |
| Job-to-job flows by industry | Census LEHD **J2J** | Quarterly, ~3q lag | too laggy to score; use in validation (§7) as ground truth for switching activity |  |

### 4C. Explicitly rejected

- **layoffs.fyi / WARN scrapes** as scored inputs: coverage bias (WARN thresholds, tech-media salience). Usable as annotation chips only.
- **LinkedIn hiring rate**: not reproducibly downloadable.
- **Challenger job cuts** as a scored input: announcement ≠ separation; validation-only (§7).

---

## 5. Statistical treatment (the part reviewers will actually poke)

### 5.1 Smoothing
All JOLTS industry-cell rates: **3-month moving average** before normalization (BLS itself cautions on monthly industry volatility). National series stay unsmoothed (current behavior) — document the asymmetry: slices trade a month of responsiveness for stability.

### 5.2 Seasonality
Never mix SA and NSA levels. NSA series (CPS industry/occupation unemployment) enter only as **12-month moving averages or YoY deltas**. No homegrown X-13 in a client-side app.

### 5.3 Normalization: percentile anchors, computed in the pipeline
Linear anchors hand-tuned per slice × component (~50+ pairs) would be arbitrary and unmaintainable — this was already the weakest part of v1/v2. For slices:

- For each (slice, component): compute the empirical **p5 and p95 over Jan-2015–present, excluding Mar–Dec 2020**, in the Python pipeline.
- Map p5→0.05, p95→0.95, linear between, clamp to [0,1]; invert where lower-is-better.
- **Emit the anchors into the slice JSON** (`norm: {lo, hi, inverted}`) so the frontend stays a dumb, generic evaluator (the v2 `SCORE_COMPONENTS` shape already supports per-component norm params — this moves their *values* from code to data).
- Freeze anchors per methodology version (recompute only on version bumps, not monthly) so the score's meaning doesn't drift silently.

National v2 keeps its current hand-set anchors for now (no silent re-scoring); a future v3 unification can migrate national to percentile anchors as its own reviewed change.

### 5.4 What a slice score *means* (relative vs absolute)
Percentile normalization makes a slice score mean "**vs your field's own 2015–present normal**" — the right frame for a *timing* decision ("is now good *for my field*?"). It deliberately does not answer "is my field better than other fields right now?" That cross-sectional question gets its own chip (§6.3) instead of being smuggled into one number. Lead the UI with the timing number; show the cross-sectional chip beside it. State this distinction in the methodology accordion.

### 5.5 Margins per slice
Propagate uncertainty honestly: margin = max(±5 national floor, round(2 × pooled SD of month-over-month score changes under the vintage backtest for that slice)). Expect Information ≈ ±7–8. Display per-slice margin in the score chip (the v2 UI already parameterizes this).

### 5.6 Missing data & revisions
Carry-forward ≤3 months and weight-renormalization rules apply unchanged per slice. JOLTS industry revisions are larger than national: the backtest (§7.2) must quantify first-print vs revised score gaps per slice and feed §5.5.

---

## 6. Persona construction — worked example: PM at Microsoft

1. **Occupation family:** Management & Business Operations (11-3021, 13-1082, 13-1111).
2. **Industry blend `w_i`** from OEWS staffing matrix for that family (illustrative shape — pull real numbers at build time): PBS ~25%, Information+5415 composite ("tech") ~15%, Finance ~12%, Health ~10%, Manufacturing ~10%, Government ~8%, other ~20%. The point the UI must make: **a PM's market is majority *outside* the tech sector** — that is the disaggregation insight for this persona, and it is data, not opinion.
3. **Occupation overlay:** Indeed "project management" postings index (YoY and vs-2019 level), management-occupations unemployment 12MMA, WGT occupation-group wage growth (if published).
4. **Score:** blend per §1 with α = 0.5 default.
5. **Panel copy:** "Your market vs national" — e.g., which of the persona's components sit above/below the national equivalents, plus the tech-proxy caveat ("Information ≠ tech; here's what we actually measure").

### 6.3 Cross-sectional chip
For each slice: current slice score minus national score, plus a one-line ranking context ("Health care currently scores highest; Information lowest"). Computed from the same slice files; no new data.

---

## 7. Validation battery (acceptance criteria before shipping Phase 1)

1. **Face validity (sign tests, must all pass):** Information slice dips below national during the 2022-23 tech layoff wave; Leisure & Hospitality spikes above national on quits in 2021-22; Federal government slice falls sharply in 2025-26; Health care stays above national through 2023-25.
2. **Vintage stability:** re-run the git-archaeology backtest per slice (the repo's own `data.json` history now includes the new series). Acceptance: no slice shows a first-print vs revised gap > its stated margin in >10% of months.
3. **External corroboration:** per-industry score changes correlate with (a) Challenger announced cuts by sector (negative sign), (b) Indeed postings by sector (positive), (c) CES industry employment growth led 0–3 months (positive). Report Spearman correlations in the methodology doc; no hard threshold, but a wrong *sign* blocks the slice.
4. **Reconciliation:** CES-employment-weighted mean of industry scores vs national score — mean absolute gap ≤ 5 points over the backtest window; publish the gap chart. (Gaps stem from percentile-vs-fixed anchors; explain, don't hide.)
5. **Robustness:** ±25% perturbation of every weight → report share of months whose tier verdict is unchanged (target ≥ 85%). This is the "your weights are arbitrary" pre-rebuttal: the *verdict* must not hinge on third-decimal weight choices.
6. **J2J cross-check:** slice quits trends vs LEHD J2J job-to-job flow rates by industry (quarterly) — directional agreement.

---

## 8. Architecture & schema

```
data.json                      # national (unchanged shape) — URL stays stable
data/slices/{slug}.json        # same shape + per-component norm anchors + margin + provenance block
data/personas.json             # occupation families: staffing weights w_i, overlay series refs, α default
```

- Pipeline: `update_data.py` grows a `SLICES` registry (slug → {component → FRED/other series ID}); one generic fetch/transform path; Atlanta Fed + Indeed fetchers isolated so third-party failures never block the FRED path (emit last-known-good with a `staleSince` stamp).
- Frontend: slice picker → lazy-fetch slice JSON → feed the existing generic scorer (norm params read from JSON). National remains the default view and the OG/social artifact.
- Provenance block per slice file: series IDs, fetch date, anchor values + the window they were fit on, margin, and caveat strings the UI renders verbatim.

## 9. Product notes

- Picker phrased as "What's your world?" — two dropdowns (role family, industry) + α slider tucked behind "advanced". Persona URL-addressable (`?occ=pm&ind=tech`) for sharing.
- Every proxy visibly labeled in-place (not only in the accordion): "tech" definition, national-only switcher premium, NSA 12MMA framings.
- Tier names stay; subtitle changes to "…for your field, vs its own normal" on slice views (§5.4).

## 10. Phasing & restart checklist

**Phase 0 — Switcher premium (national).** Verify §2 unknowns → fetcher → component + rebalance → vintage backtest → methodology docs. *Small, high-value, independently shippable.*

**Phase 1 — Industry engine.** Verify §4A series IDs (start: Information, PBS, Health, Leisure & Hospitality, Government fed/S&L) → pipeline registry + percentile anchors → slice JSONs → generic frontend scorer + picker → §7 validation → ship behind a "beta" label.

**Phase 2 — Occupation overlays.** Indeed categories + CPS occupation unemployment + WGT occupation cut → overlay score → occupation family pages.

**Phase 3 — Personas.** OEWS staffing matrix → blend + α UI → PM-at-Microsoft as the flagship worked example → cross-sectional chips.

**First actions on session restart (do these before writing code):**
1. Read this file + `docs/methodology.md`; check `git log --oneline -10` for state.
2. Resolve every "V?" row in §4 and the §2 verification tasks against live FRED/Atlanta Fed/Indeed sources (this environment blocks those domains — do it via the GitHub Actions workflow pattern from v2, a local machine, or an environment with network access; **record confirmed IDs in this file** by replacing the V? marks).
3. Then implement Phase 0.

## 11. Honest limitations (pre-write the criticisms)

- Industry×occupation monthly flow cells don't exist; the blend (§1) is our approximation and α is a preference parameter, disclosed as such.
- "Tech" is a constructed slice; Information is its measurable proxy. We show the seam rather than welding over it.
- Percentile normalization encodes "normal for your field" — a field whose decade was uniformly bad scores high in a mediocre month. The cross-sectional chip (§6.3) is the counterweight, and the UI shows both.
- Indeed is a private data source with methodology drift risk; it never enters a scored component beyond postings, and always in own-history-relative form.
- Occupation series lag and NSA constraints mean the occupation overlay is structurally ~1 quarter blunter than the industry axis. Say so in the UI.
