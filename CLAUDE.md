# CLAUDE.md — Orbit Wars Agent

Kaggle competition agent (`main.py`) for Orbit Wars. Python. No git repo.

## Commands

```bash
.venv/bin/python test_agent.py            # full suite: 5 vs random + 3 self-play
.venv/bin/python test_agent.py --diagnose # fleet logs + per-5-turn snapshots, seeds 0–2
.venv/bin/kaggle competitions submissions orbit-wars   # list submissions + IDs
.venv/bin/kaggle competitions episodes <SUBMISSION_ID> # list episode IDs
.venv/bin/python replay_analyzer.py replays/*.json     # analyze downloaded replays
.venv/bin/python watch_replays.py                      # fetch latest submission episodes + print summary table
.venv/bin/python watch_replays.py --submission-id ID   # specific submission
.venv/bin/python watch_replays.py --n 20               # fetch more episodes (default 10)
```

## Key Files

- `main.py` — competition agent; submit this file
- `benchmark.py` — gate check: 10 vs-random + 5 self-play, exit 0=PASS (≥8/10 + ≥2/5)
- `morning_check.sh` — daily status: leaderboard, score, delta, episode count
- `daily_review.py` — download recent replays to `replays/YYYY-MM-DD/`, print closest-loss/worst-loss/best-win
- `experiment_log.md` — hypothesis → result tracking for each version
- `routine.md` — daily workflow documentation
- `test_agent.py` — local harness with `--diagnose` flag
- `main_v2_backup.py` — verified baseline (score ~543)
- `replay_analyzer.py` — analyze episode replay JSONs (final scores, planet snapshots, fleet patterns)
- `watch_replays.py` — post-submission validation: fetch latest episodes, download replays, print win/fleet-size/stuck summary

## Tuple Indices

Planet: `[id, owner, x, y, radius, ships, production]`
Fleet:  `[id, owner, x, y, angle, from_planet_id, ships]`
`owner == -1` = neutral

## Gotchas

- **Self-play module state**: both agents share the same `main.py` import in one process. Any module-level dict must key by `(player_id, ...)`, not just entity id. Always `clear()` on `turn == 0`.
- **Binary reward**: `step[i]["reward"]` is `+1/-1`. Actual ship counts: `obs["planets"][n][5]` (ships), `obs["fleets"][n][6]` (ships).
- **`env.steps[t]`**: full world state per turn after `env.run()`. `step[0]["observation"]` has data for both players (full-info game).
- **`.venv` required**: `python3` → `ModuleNotFoundError: kaggle_environments`. Always use `.venv/bin/python`.
- **uv venv — no pip**: `.venv/bin/pip` doesn't exist. Install packages with `uv pip install <pkg> --python .venv/bin/python`.
- **Replay download CLI bug**: `competition_episode_replay()` crashes on missing `Content-Length`. Workaround: call `get_episode_replay(request)` directly and write `response.content` to file.
- **Episode replay format**: `data["steps"][turn][player_index]["observation"]` — not `[player][turn]`. `data["rewards"]` = final `[+1/-1]` list.
