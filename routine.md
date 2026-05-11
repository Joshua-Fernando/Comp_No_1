# Orbit Wars — Daily Routine

## Morning (~5 min)

```bash
bash morning_check.sh
```

Review:
- Am I in top 50? Top 20?
- Score delta: improving or regressing?
- Any FAILED submissions to investigate?
- Episode count: enough games to judge last version?

**Decision gate:** If score regressed >20 pts, run `daily_review.py` before any code changes.

---

## Before Coding (~10 min)

1. Read `experiment_log.md` — what was last hypothesis? Did it pan out?
2. Identify ONE metric to move (e.g. avg first capture turn, idle turn count, fleet size)
3. Write hypothesis in `experiment_log.md` BEFORE touching `main.py`

---

## Implement + Benchmark (~20-40 min)

```bash
# 1. Make change to main.py
# 2. Run benchmark
.venv/bin/python benchmark.py
# Exit 0 = PASS (vs-random ≥8/10 AND self-play ≥2/5), Exit 1 = FAIL

# 3. If PASS, submit:
.venv/bin/kaggle competitions submit orbit-wars -f main.py -m "v<N>: <one-line change>"
```

**Do not submit if benchmark fails.**

---

## After Submission (~2 min)

Fill in `experiment_log.md`:
- `**Change:**` — what you changed (function + logic)
- `**Local benchmark:**` — W/L/D numbers from benchmark.py
- `**Submitted:** yes`

---

## Evening Check (~5 min, 6+ hours after submit)

```bash
bash morning_check.sh
```

Check if score improved. If 20+ episodes in:
- Fill in `**Kaggle result:**` in experiment_log.md
- Fill in `**Learning:**` — was the hypothesis right? What surprised you?

---

## Weekly Review (Sundays, ~30 min)

```bash
.venv/bin/python daily_review.py --n 100
```

1. Read this week's `experiment_log.md` entries
2. Count: submissions, improved, regressed
3. Check `kaggle competitions submissions orbit-wars` for score trajectory
4. Identify ONE change that moved score most
5. Identify ONE losing pattern still appearing in replays
6. Pick next week's theme:
   - "week of expansion speed" — reduce idle turns
   - "week of defense geometry" — improve garrison + reinforce logic
   - "week of fleet sizing" — send-amount tuning
   - "week of target selection" — scoring function improvements

Write the theme at the top of next week's experiment_log section.

---

## File Reference

| File | Purpose |
|------|---------|
| `main.py` | Competition agent — only file submitted |
| `benchmark.py` | Gate check before every submit |
| `morning_check.sh` | Daily status snapshot |
| `daily_review.py` | Download + analyze recent replays |
| `experiment_log.md` | Hypothesis → result tracking |
| `replay_analyzer.py` | Deep replay analysis (loss investigation) |
| `test_agent.py` | Detailed game output + --diagnose mode |
| `download_replays.py` | Bulk replay + log downloader |
| `watch_replays.py` | Quick post-submission summary table |

---

## Submission Rules

- Never submit without passing `benchmark.py`
- Never submit two versions within 2 hours (score needs 20+ episodes to stabilize)
- Keep `main_v2_backup.py` as the verified baseline (score: ~503)
- One change per version — makes attribution clear
