# Automation Setup

This document explains how to set up automatic data updates for the Labor Market Dashboard.

## How It Works

A GitHub Actions workflow runs monthly (on the 7th) and:
1. Fetches latest data from FRED (Federal Reserve Economic Data)
2. Updates `data.json` with any new monthly values
3. Commits and pushes the changes automatically

The dashboard then shows the new data—no manual intervention needed.

## One-Time Setup

### 1. Get a FRED API Key (free, takes 30 seconds)

1. Go to https://fred.stlouisfed.org/docs/api/api_key.html
2. Click "Request API Key"
3. Create an account or sign in
4. Copy your API key

### 2. Add the API Key to GitHub Secrets

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `FRED_API_KEY`
5. Value: paste your API key
6. Click **Add secret**

### 3. Enable GitHub Actions

Actions should be enabled by default. If not:
1. Go to **Settings** → **Actions** → **General**
2. Select "Allow all actions and reusable workflows"
3. Save

## Testing the Automation

You can trigger the workflow manually to test:

1. Go to **Actions** tab in your repository
2. Click "Update Labor Market Data" in the left sidebar
3. Click **Run workflow** → **Run workflow**
4. Watch it execute (takes ~30 seconds)

If successful, you'll see a new commit updating `data.json`.

## Data Sources

All data is fetched from FRED, which aggregates:

| Metric | FRED Series | Original Source |
|--------|-------------|-----------------|
| Quit Rate | JTSQUR | BLS JOLTS |
| Job Openings | JTSJOL | BLS JOLTS |
| Hires Rate | JTSHIR | BLS JOLTS |
| Layoffs Rate | JTSLDR | BLS JOLTS |
| Unemployment Rate | UNRATE | BLS Employment Situation |
| Fed Funds Rate | FEDFUNDS | Federal Reserve |
| Avg Hourly Earnings | CES0500000003 | BLS Employment Situation |
| Prime-Age LFPR | LNS11300060 | BLS Employment Situation |

The openings/unemployed ratio is calculated from JTSJOL / UNEMPLOY.
Wage growth is calculated as year-over-year change in average hourly earnings.

## Schedule

The workflow runs on the 7th of each month at 10:00 AM UTC. This timing is chosen because:
- JOLTS data (quit rate, hires, openings) releases around the 6th-10th of each month
- The data covers the month ending ~40 days prior

You can adjust the schedule in `.github/workflows/update-data.yml` by modifying the cron expression.

## Troubleshooting

**Workflow fails with "FRED_API_KEY not set"**
- Make sure you added the secret in repository Settings → Secrets

**No changes committed**
- This is normal if there's no new data since last update
- JOLTS data has a ~5 week lag, so new data only appears monthly

**Data looks wrong**
- Check the workflow logs in the Actions tab
- Verify FRED is returning data by visiting the series page (e.g., https://fred.stlouisfed.org/series/JTSQUR)

## Running Locally

To test the update script locally:

```bash
export FRED_API_KEY=your_api_key_here
cd scripts
python update_data.py
```

This will update the local `data.json` file.
