# Weekly Labor Market Write-Up Prompt

Copy and paste this prompt template into Claude along with your current data.

---

## PROMPT TEMPLATE

```
You are helping me write a weekly labor market analysis for my personal job search dashboard. I'm a program/product manager in the Seattle area tracking when conditions favor active job searching.

**Data as of: [DATE]**

### TIER 1 - CORE INDICATORS
| Metric | Value | Signal |
|--------|-------|--------|
| Quit Rate | [X]% | 🟢/🟡/🔴 |
| Job Openings per Unemployed | [X] | 🟢/🟡/🔴 |
| Hires Rate | [X]% | 🟢/🟡/🔴 |
| Layoffs Rate | [X]% | 🟢/🟡/🔴 |

### TIER 2 - MACRO CONTEXT
| Metric | Value | Signal |
|--------|-------|--------|
| Unemployment Rate | [X]% | 🟢/🟡/🔴 |
| Fed Funds Rate | [X]% | 🟢/🟡/🔴 |
| Avg Hourly Earnings YoY | [X]% | 🟢/🟡/🔴 |
| Prime-Age LFPR (25-54) | [X]% | 🟢/🟡/🔴 |

### TIER 3 - SENTIMENT
| Metric | Value | Signal |
|--------|-------|--------|
| ZipRecruiter Job Seeker Confidence | [X] | 🟢/🟡/🔴 |
| Indeed Job Postings vs Pre-Pandemic | [X]% | 🟢/🟡/🔴 |
| Conference Board "Jobs Hard to Get" | [X]% | 🟢/🟡/🔴 |
| Challenger YTD Job Cuts | [X]K | 🟢/🟡/🔴 |

### SEATTLE/PM SPECIFIC
| Metric | Value | Signal |
|--------|-------|--------|
| Seattle Metro Unemployment | [X]% | 🟢/🟡/🔴 |
| Tech Job Postings vs Pre-Pandemic | [X]% | 🟢/🟡/🔴 |
| Target Company Open PM Roles | [X] | 🟢/🟡/🔴 |

**COMPOSITE SCORE: [X]/100 ([🟢 FAVORABLE / 🟡 NEUTRAL / 🔴 UNFAVORABLE])**

---

Please write a 3-4 paragraph weekly summary that:

1. **What Changed**: Highlight the 2-3 most significant changes from last month's data
2. **What It Means**: Interpret the signals specifically for a PM job seeker in Seattle tech
3. **Action Recommendation**: One of these verdicts with specific guidance:
   - 🟢 "Apply Aggressively" - prioritize applications, accept informational interviews
   - 🟡 "Selective Networking" - maintain connections, apply only to strong fits
   - 🔴 "Hold Steady" - focus on current role, passive monitoring only
4. **Watch List**: Note any upcoming data releases (JOLTS, jobs report, Fed meeting) or events that could shift the picture

Keep the tone direct and actionable. No hedging or caveats—give me your honest read.
```

---

## DATA RELEASE CALENDAR

Use this to know when to update your dashboard:

| Data | Release | Timing |
|------|---------|--------|
| Employment Situation (unemployment, wages) | BLS | 1st Friday of each month |
| JOLTS (quits, openings, hires) | BLS | ~35 days after reference month |
| Consumer Confidence | Conference Board | Last Tuesday of each month |
| Challenger Job Cuts | Challenger Gray | 1st Thursday of each month |
| ZipRecruiter Confidence | ZipRecruiter | Quarterly (mid-month after quarter end) |
| Fed Rate Decision | FOMC | 8 meetings per year (check calendar) |

### Recommended Update Cadence

**Monthly (first week):**
- Employment Situation data → Update unemployment, wages, LFPR
- Previous month's JOLTS → Update quit rate, openings, hires, layoffs

**Monthly (end of month):**
- Conference Board consumer confidence → Update "jobs hard to get"
- Challenger report → Update YTD job cuts

**Quarterly:**
- ZipRecruiter Job Seeker Confidence
- Fed dot plot (March, June, September, December)

**Weekly (optional):**
- Indeed Hiring Lab job postings tracker
- Target company job board scan

---

## SAMPLE OUTPUT

Here's what a good weekly write-up looks like:

> **Week of January 8, 2026**
>
> The November JOLTS data showed quit rate ticking up slightly to 2.0% from October's 1.8%—the first uptick in three months. While one month doesn't make a trend, it's the first green shoot since summer. Meanwhile, job openings fell to 7.1M against 7.6M unemployed, pushing the ratio below 1.0 for the first time since 2021. The labor market has officially tipped employer-favorable by this measure.
>
> For Seattle PM roles specifically, the picture remains challenging. Tech job postings on Indeed are now only 2-3% above pre-pandemic levels after being 30%+ elevated in 2022. The December Fed cut to 3.5-3.75% should eventually help, but monetary policy operates with a lag. Your target company tracker shows Microsoft and Amazon with modest PM hiring, but nothing like the 2021-22 boom.
>
> **Verdict: 🟡 Selective Networking.** Conditions don't favor aggressive job searching, but they're not deteriorating rapidly either. Focus on maintaining your network, taking informational interviews when they come naturally, and applying only to roles that are strong fits. Don't feel pressure to jump at marginal opportunities.
>
> **Watch this week:** January 10 brings the December Employment Situation report. A surprise uptick in unemployment could shift sentiment. The next JOLTS release (December data) comes February 3—that quit rate trend is worth watching closely.

---

## QUICK REFERENCE: THRESHOLD CHEAT SHEET

### Quit Rate
- 🟢 3.0%+ (job seekers confident)
- 🟡 2.0-2.5% (balanced)  
- 🔴 <2.0% (employees staying put)

### Job Openings / Unemployed
- 🟢 1.5+ (more jobs than seekers)
- 🟡 1.0-1.2 (balanced)
- 🔴 <1.0 (more seekers than jobs)

### Unemployment Rate
- 🟢 <4.0% (tight labor market)
- 🟡 4.0-4.5% (balanced)
- 🔴 >5.0% (slack in market)

### Fed Funds Rate
- 🟢 <3.0% (stimulative)
- 🟡 3.0-4.0% (neutral)
- 🔴 >4.5% (restrictive)
