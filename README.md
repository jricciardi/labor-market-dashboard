# Is Now a Good Time?

A data-driven tool to help you understand when job seekers have more or less leverage than employers.

**Live site:** [jricciardi.github.io/labor-market-dashboard](https://jricciardi.github.io/labor-market-dashboard)

## What is this?

This dashboard combines eight labor market indicators into a single score to answer a simple question: **does the job market currently favor people looking for work, or employers doing the hiring?**

The score runs from 0 to 100. Higher means better for job seekers.

- **70+** — Good Time to Move
- **55–69** — Worth Exploring  
- **40–54** — Wait If You Can
- **<40** — Tough Market

## Data sources

All data comes from official government sources via the [FRED API](https://fred.stlouisfed.org/):

- **Bureau of Labor Statistics JOLTS** — Quit rate, hiring rate, layoff rate, job openings
- **BLS Employment Situation** — Unemployment rate, workforce participation, wage growth
- **Federal Reserve** — Fed funds interest rate

Data updates automatically each month after BLS releases.

## Local development

```bash
# Clone the repo
git clone https://github.com/jricciardi/labor-market-dashboard.git
cd labor-market-dashboard

# Open in browser
open index.html
```

For data updates, you'll need a [FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html):

```bash
export FRED_API_KEY=your_key_here
python scripts/update_data.py
```

## License

MIT — fork it, adapt it for your industry, use it however you want.

## Why this exists

This project is an experiment in pro-worker tooling: taking institutional data that's technically public but practically inaccessible and making it legible to regular people.

Built with AI assistance.
