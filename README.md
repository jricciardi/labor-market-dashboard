# Labor Market Dashboard

A quantitative dashboard for tracking labor market conditions and job search timing decisions.

## What This Tracks

The dashboard synthesizes Bureau of Labor Statistics data into a composite score (0-100) that indicates whether current conditions favor job seekers or employers.

**Core indicators (Tier 1):**
- Quit Rate — worker confidence in finding better opportunities
- Job Openings per Unemployed — supply/demand balance
- Hires Rate — actual hiring velocity
- Layoffs Rate — involuntary separations

**Macro context (Tier 2):**
- Unemployment Rate
- Federal Funds Rate
- Wage Growth (YoY)
- Prime-Age Labor Force Participation

## Score Interpretation

| Score | Verdict | Meaning |
|-------|---------|---------|
| 70+ | Favorable | Employee-favorable market. Active job searching is rational. |
| 55-69 | Lean Favorable | Functional market. Selective searching reasonable. |
| 40-54 | Lean Unfavorable | Headwinds present. Hold steady unless compelling reason to move. |
| <40 | Unfavorable | Employer-favorable. Focus on stability. |

## Data Sources

- [BLS JOLTS](https://www.bls.gov/jlt/) — quit rate, hires, openings, layoffs
- [BLS Employment Situation](https://www.bls.gov/news.release/empsit.toc.htm) — unemployment, wages, LFPR
- [Federal Reserve](https://www.federalreserve.gov/monetarypolicy/openmarket.htm) — fed funds rate

## Update Schedule

Data is updated monthly following BLS releases:
- Employment Situation: First Friday of each month
- JOLTS: ~35 days after reference month

---

*Built for personal job search timing decisions. Not financial or career advice.*
