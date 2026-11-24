# GLG Men's Sixes Projections

Projections and pricing for the men's Lexus Global Lacrosse Games (Dec 8–13 2026, World Lacrosse sixes rules): game lines, player props, tournament futures, a depth chart, lineups, overrides, results and grading. The model is described in `reports/model_guide.md`, which the app also shows on its Model & Data page.

## What's in this repo

| Path | Contents |
|---|---|
| `app/` | Streamlit app. `glg_app.py` is the entry point and `views/` holds the pages |
| `glg/engine.py` | Projection engine |
| `glg/store.py` | Saved data: overrides, results, box scores, snapshots. Local files, or a private GitHub Gist in the cloud |
| `glg/live_sync.py` | Merges scraped GLG results into the saved data |
| `scripts/scrape_glg_live.py` | Scrapes completed GLG games from the PLL stats API; run by the GitHub Action |
| `scripts/migrate_to_gist.py` | One-time copy of locally saved data into the Gist |
| `.github/workflows/glg-live.yml` | "GLG results update" Action: nightly Dec 9–14, or on demand |
| `warehouse/sixes.duckdb` | Player and team database the model reads |
| `data/glg/` | Schedule and 2023 Worlds inputs |
| `reports/` | Model guide, calibration notes, analysis |

**Run locally:** `pip install -r requirements.txt`, then `python -m streamlit run app/glg_app.py --server.port 8690`, or double-click `run_glg_app.bat`.

---

# One-time setup (about 15 minutes)

Do these steps in order. You will collect three values along the way; keep them in a note while you work, then delete the note.

| Value | Step |
|---|---|
| **Gist ID** | 1 |
| **Gist token** | 2 |
| **PLL token** | 3 |

## Step 1: Create the private Gist (where the app saves your work)
1. Go to https://gist.github.com, signed in as the GitHub account that owns this repo.
2. In **"Filename including extension…"** type exactly: `overrides.json`
3. In the big text box type exactly: `{}`
4. Click the arrow next to the green button, choose **Create secret gist**, then click **Create secret gist**.
5. Look at the page address. It looks like `https://gist.github.com/ajpayzant/1a2b3c4d5e6f...`. The last part, after your username, is the **Gist ID**. Copy it.

## Step 2: Create the Gist token (lets the app and Action write to the Gist)
1. Go to https://github.com/settings/tokens/new. That's **Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token (classic)**.
2. **Note:** `GLG app gist`.
3. **Expiration:** pick a date after the tournament, e.g. 90 days.
4. **Select scopes:** tick only **`gist`**.
5. Click **Generate token** and copy it. It starts with `ghp_`. This is the **Gist token**. GitHub only shows it once.

## Step 3: Get the PLL token (lets the Action read PLL stats)
This is the same token your PLL Google Sheet already uses.
1. Open the PLL database Google Sheet.
2. Go to **Extensions → Apps Script**.
3. On the left, click the gear icon, **Project Settings**.
4. Scroll to **Script Properties** and find **`PLL_BEARER_TOKEN`**.
5. Copy its value. This is the **PLL token**. If it starts with `Bearer `, leave that word out.

## Step 4: Add the three secrets to this repo (for the results Action)
1. Open https://github.com/ajpayzant/Global-Lacrosse-Games-Projections/settings/secrets/actions. That's **Settings → Secrets and variables → Actions**.
2. Click **New repository secret** three times, once for each:

| Name (exactly) | Secret |
|---|---|
| `PLL_BEARER_TOKEN` | the PLL token |
| `GLG_GIST_ID` | the Gist ID |
| `GLG_GITHUB_TOKEN` | the Gist token |

## Step 5: Deploy the app on Streamlit Cloud
1. Go to https://share.streamlit.io and click **Create app**, then **Deploy a public app from GitHub**.
2. **Repository:** `ajpayzant/Global-Lacrosse-Games-Projections`. **Branch:** `main`. **Main file path:** `app/glg_app.py`.
3. Click **Advanced settings**:
   - **Python version:** 3.12.
   - **Secrets:** paste these two lines with your values:

     ```
     GLG_GIST_ID = "your Gist ID"
     GLG_GITHUB_TOKEN = "your Gist token"
     ```

4. Click **Save**, then **Deploy**. The first start takes a few minutes while packages install.
5. Check the app's left sidebar. It should say **"Saved data: GitHub Gist (cloud)"**. If it says "local files", the secrets weren't saved: open the app's **⋮ → Settings → Secrets** and fix them.

## Step 6: Check that saving survives a restart
1. In the app, open **Ratings & Overrides**, give any team an attack override of 0.01, and click **Save overrides**.
2. In Streamlit Cloud, open the app's **⋮ → Reboot app**.
3. After it restarts, the override should still be there. Then clear it with **Clear ALL overrides**.

## Step 7: Check that the results Action runs
1. Open the repo's **Actions** tab, select **GLG results update**, and click **Run workflow** (on branch main).
2. It should finish with a green tick in about a minute.
   - Before the tournament there are no finished games, so it saves nothing new. That's expected.
   - A red **"Missing repository secrets"** error means Step 4 needs fixing.
3. In the app, **Results & Grading** now shows "Last update … finals applied: none yet".

## Step 8 (optional): Bring over the depth charts you saved locally
On your computer, in this folder, open a Command Prompt and run:
```
set GLG_GIST_ID=your Gist ID
set GLG_GITHUB_TOKEN=your Gist token
python scripts\migrate_to_gist.py
```
It prints `copied overrides.json`. Your saved USA and Haudenosaunee depth charts then appear in the cloud app. Alternatively, re-enter them on the cloud app's Depth Chart page.

---

# During the tournament
- **Before each session:** Results & Grading → **Snapshot projections now**, so grading compares against pre-game projections.
- **About 20 minutes before each game:** Game Center → **Lineups**. Mark who's not dressed; 12 per game are allowed.
- **After the day's games:**
  - The Action runs automatically at about midnight ET, Dec 9–14.
  - To update sooner: **Actions → GLG results update → Run workflow**.
  - Scores and player box scores land in the Gist, and the app's projections, tournament odds and grading update within a minute.
- **If the scrape misses a game:** enter the score on **Results & Grading**. Manual entries are kept unless the scrape later finalises that game.
- **The Gist token expires** on the date you chose. If saving or the Action starts failing after that, create a new token (Step 2) and update it in both places (Steps 4 and 5).
