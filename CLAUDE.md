# Labor Market Dashboard — Claude Context

## Status & Roadmap (updated 2026-07-15, v3 Phase 0+1 in progress)

- **Score model v2.1** (v3 plan Phase 0): adds `switcherPremium` (Atlanta Fed Wage Growth Tracker, switcher − stayer wage growth, pp) at 12% weight with the §2 rebalance. Config lives in `index.html` (`SCORE_COMPONENTS`) and is mirrored in `scripts/score_model.py` — **keep them in lockstep**; the browser smoke test cross-checks the two. Margin ±5; fed funds charted, not scored.
- **Pipeline is now modular**: `scripts/fred_client.py` (FRED + transforms + percentile anchors), `scripts/atlanta_fed.py` (defensive xlsx parsing, last-known-good fallback recorded in `metadata.switcherPremiumSource`), `scripts/update_data.py` (national), `scripts/update_slices.py` (Phase 1 industry slices → `data/slices/*.json` with data-driven anchors, provenance, face-validity checks), `scripts/verify_sources.py` (probes candidate series IDs → `data/source-verification.json`; slices only build from verified IDs), `scripts/backtest.py` (vintage walk; frozen v2 comparison).
- **CI**: `.github/workflows/branch-data-refresh.yml` runs verify + national + slices on any push to `claude/**` that touches `scripts/**` and commits results back to the branch — this is how a network-restricted session gets real FRED/Atlanta Fed data. `update-data.yml` (main, scheduled 7th/14th) also builds slices once a verification report is committed.
- **Phase 0 + Phase 1 data are DONE on the branch (3 refresh iterations, 2026-07-16)**: switcher premium live (137 months, current +0.7pp; anchors (v+0.5)/3 validated against real percentiles — median 0.9→0.47, p95 1.9→0.8); national score with premium = 47 "Build Your Position"; all 7 slice files built (`data/slices/`), 5 with coverage ok, government slices honestly flagged insufficient (no wage/unemp data exists for gov); **all four face-validity checks PASS on real data** (info 2023 well below health 41.8 vs 68.6 and below PBS; federal falls 49→41 into 2025-26; leisure quit spike). Only 2 purposes unresolved: cps health/leisure unemp_rate (search-text tuning, non-blocking).
- **Hard-won lessons encoded in the pipeline** (don't regress these): FRED titles don't distinguish JOLTS rate vs level series — resolution is units-aware; title expectations are mandatory per purpose (wrong-sector CPS ids passed a laxer rule once); NSA-only series (Information JOLTS, all industry layoffs) get 12MMA not 3MMA; Atlanta Fed workbook parsing uses an explicit sheet preference (`data_overall` = 3MMA headline; `Job Switcher` sheet is 12MMA; `Alternative WGT` is a different methodology) with magnitude sanity bounds; Python scoring uses half-up rounding to match JS Math.round.
- **Phase 1 frontend SHIPPED**: "Your Corner of the Market" section (`#sectorSection`) — sector pills + per-slice panel with relative band labels ("around its usual" etc., §5.4 framing), trend chart, component chips with provenance tooltips, cross-slice ranking line, caveats. JS slice scorer in `index.html` (`sliceScoreAt`) mirrors `score_model.slice_score_at` — a drift console.warn fires if JS-computed scores diverge from the pipeline-embedded `scores` array. Insufficient-coverage slices (both government) render an honest no-score explanation. Progressive enhancement: no `data/slices/index.json` → section and nav entry stay hidden.
- **Next actions (Phase 2 — occupation overlays, then Phase 3 personas)**: (1) occupation-axis data: `IHLIDXUSTPPROJMANA` (Indeed PM postings, SA, 2020-02→now), `IHLIDXUSTPSOFTDEVE`, `LNU04032215/6` (mgmt occupation unemployment, NSA→12MMA) are **verified and ready** in `data/source-verification.json`; per plan §4B add Atlanta Fed WGT occupation-cut probe (tracker workbook has an `Occupation` sheet — 12MMA, structure already dumped in the verification report) and OEWS staffing-matrix ingestion for §1 persona blend weights; (2) resolve 2 remaining CPS purposes (health/leisure unemp_rate — search-text tuning); (3) validation battery §7.2/7.3 as slice history accrues; (4) flagship persona: PM-in-tech worked example (§6).
- Environment note: the Claude remote environment blocks FRED/Atlanta Fed domains and can't dispatch GitHub Actions (403) — but pushes to `claude/**` auto-trigger the branch refresh workflow, which has the secrets.

## Project Overview
"Is Now a Good Time?" — A pro-worker labor market dashboard that combines 8 indicators into a single actionable score (0–100) answering: does the job market currently favor job seekers or employers?

**Stack:** Single-file app (`index.html`) — vanilla HTML/CSS/JS, Chart.js via CDN, no build step.
**Data:** Monthly automated updates via Python + FRED API. Hosted on GitHub Pages.

## Design Context

### Users
Job seekers and workers navigating an uncertain labor market. They arrive with stress or uncertainty — often after a hard week, a layoff, or a feeling that "everyone else seems to be doing fine." They want a fast, trustworthy read on whether *now* is a good time to make a career move. They're not economists; they're people who deserve the same quality of market intelligence that institutional players take for granted.

### Brand Personality
Calm, credible, clear. This is a tool that respects the user's intelligence. It doesn't hype, it doesn't hedge, and it doesn't bury the signal in jargon. Think trusted analyst, not dashboard startup. Think journalist, not fintech app.

**Three words:** Calm · Credible · Clear

### Emotional Goals
Leave users feeling *empowered agency* — "I have data most people don't, and I can act strategically." Not anxiety, not overwhelm. Strategic clarity. The interface should reduce noise, not add to it.

### Aesthetic Direction
**Reference:** NYT / The Pudding — editorial data journalism. Beautiful, purposeful charts. Strong visual hierarchy. Accessible to non-experts. The kind of thing you'd want to share because it's both *correct* and *well-made*.

**Anti-references:** Avoid anything that reads as a startup landing page, a Bloomberg terminal clone, or a generic analytics SaaS. No gradients for gradients' sake. No aggressive animation. No dark-pattern UI elements.

**Visual tone:** Restrained but not sterile. Dense but not cluttered. The monospace font stack reinforces "data tool" — lean into it. Use white space to create hierarchy, not emptiness.

**Theme:** Dark mode default (deep blue-tinted neutrals). Full light mode support via `[data-theme="light"]`.

### Design Principles

1. **Signal over noise** — Every visual element should help the user find the answer faster. Remove anything that doesn't serve comprehension.

2. **Earned trust** — Use clean typography, precise data labels, and restrained color. Credibility is destroyed by over-design. Earn it with clarity.

3. **Semantic color is sacred** — The green/yellow/orange/red system carries meaning across the entire interface. Never use these colors decoratively. Never break the mapping.

4. **Editorial hierarchy** — Lead with the verdict (the score), then support it. Structure content like a great news article: headline → key facts → context → details.

5. **Accessible by default** — WCAG AA minimum. Keyboard navigable. Reduced motion respected. Color meaning always reinforced with text or shape — never color alone.

### Token Reference
| Token | Value | Use |
|---|---|---|
| `--bg-primary` | `#0a0a0f` | Page background |
| `--bg-secondary` | `#12121a` | Cards, sections |
| `--bg-tertiary` | `#1a1a25` | Elevated components |
| `--accent-green` | `#00d9a0` | Good / positive signal |
| `--accent-yellow` | `#ffc940` | Neutral / watch |
| `--accent-orange` | `#ff8c40` | Caution / declining |
| `--accent-red` | `#ff4d6a` | Bad / negative signal |
| `--accent-blue` | `#4d9fff` | Focus / interaction |
| `--text-primary` | `#e8e8ed` | Main text |
| `--text-secondary` | `#9898a8` | Descriptions |
| `--text-muted` | `#606070` | Labels, captions |

### Typography
- **JetBrains Mono** — all UI, data values, labels, body text (weights 400–700)
- **Instrument Serif** — display headlines, section titles (italic variants for editorial feel)
- Tabular numerals for all data values: `font-variant-numeric: tabular-nums`
