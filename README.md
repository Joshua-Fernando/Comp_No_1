# Orbit Wars Agent

Kaggle competition agent for Orbit Wars. Python. Automated monitoring via GitHub Actions.

## One-time setup

### 1. Add Kaggle secrets to GitHub

**Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|---|---|
| `KAGGLE_USERNAME` | Your Kaggle username |
| `KAGGLE_KEY` | API key from kaggle.com → Account → Create New Token |

### 2. Push to GitHub

```bash
git remote add origin <YOUR_REPO_URL>
git branch -M main
git push -u origin main
```

---

## Workflows

### Monitor — every 2 hours + manual

Runs `morning_check.sh`, appends to `logs/score_history.log`, commits back.

- Score drops >30 pts → opens a GitHub issue automatically
- At 8 UTC: also runs `daily_review.py` and commits replays

**Trigger manually:** Actions tab → Monitor → Run workflow

### Benchmark — on push

Triggers when `main.py` or any `main_v*.py` is pushed.

- Runs `benchmark.py --agent <file>` for each changed agent file
- Posts PASS ✅ / FAIL ❌ + full output as a commit comment
- Workflow fails if any agent fails the benchmark gate

---

## Reading score history

```bash
grep "Current:" logs/score_history.log      # score trend
grep "Delta:" logs/score_history.log        # daily deltas
```

---

## Local development

```bash
# One-time setup
python -m venv .venv && .venv/bin/pip install -r requirements.txt

# Benchmark
.venv/bin/python benchmark.py --agent main.py

# Daily check
bash morning_check.sh
```

---

## Notes

- `logs/` and `replays/` are gitignored locally but committed by CI (`git add -f`)
- `.last_score` is ephemeral (gitignored); score history persists in `logs/score_history.log`
- Never submit without passing `benchmark.py` (≥8/10 vs-random AND ≥2/5 self-play)
