# Quick Start

```bash
.venv/bin/python test_agent.py            # 5 vs random + 3 self-play
.venv/bin/python test_agent.py --diagnose # seeds 0–2: fleet log + snapshot table (turns 0–75)
```

## Interpret output

- `WIN/LOSS/DRAW` = binary reward (`+1/-1`)
- `my=` / `opp=` = actual ship counts at game end
- `pl=` = ships on planets, `fl=` = ships in transit, `prod=` = production/turn
- Diagnose table: `p0pl/p1pl` = planet count, `p0sh/p1sh` = total ships

## Submission

Copy `main.py` contents into Kaggle notebook agent cell. No imports outside stdlib + numpy.
