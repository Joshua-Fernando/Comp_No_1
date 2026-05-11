# Architecture Map

```
comp/
├── main.py              # Competition agent — submit this
├── test_agent.py        # Local harness (--diagnose flag)
├── main_v2_backup.py    # Earlier version backup
├── .venv/               # Virtualenv with kaggle_environments
└── .claude/
    ├── COMMON_MISTAKES.md
    ├── QUICK_START.md
    └── ARCHITECTURE_MAP.md
```

## Agent structure (main.py)

- `agent(obs, config)` — entry point called by kaggle_environments each turn
- `build_assignment()` — greedy fleet dispatch loop
- `score_target()` — scores each (source, target) pair; blends speed+value
- `ships_to_capture()` — estimates ships needed including garrison growth
- `failed_targets` — module-level dict `{(player_id, planet_id): (turn, ships)}`; skip recently failed attacks

## Game constants

- Board: 100×100, sun at (50,50)
- Max turns: 500
- Fleet speed: varies by ship count (heavier = slower)
- Win condition: more ships at turn 500, or opponent eliminated
