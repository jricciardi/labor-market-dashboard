# Labor Market Dashboard — Claude Context

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
