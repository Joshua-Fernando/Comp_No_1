# Experiment Log — Orbit Wars

---

## Template

## YYYY-MM-DD - vN
**Hypothesis:** [one sentence — what you believe will improve performance]
**Change:** [what code changed — function name + diff summary]
**Local benchmark:** vs-random W/L/D, self-play W/L/D, key metric (avg fleet size / first capture turn)
**Submitted:** [yes/no — if no, why not]
**Kaggle result:** [score after 20+ episodes — fill in next day]
**Learning:** [what this taught you — update if benchmark misleads]

---

## 2026-05-11 - v11

**Hypothesis:** Idle turns (not fleet size) cause losses. Replays show 5+ consecutive idle turns with 400+ ships at inflection point (~t80).

**Evidence:** 5-game loss analysis shows opponents launch 25–193 fleets vs my 14–56. Two distinct winning strategies (big-strike avg fleet=15, spam-expansion avg fleet=3) both beat my moderate-everything approach. At inflection turn (~t80), I had 400+ ships not firing.

**Change:** `should_launch()` returns True whenever `available >= target.ships + 1` (no buffer, no waiting). `compute_send()` early game (`step < 120`) returns `needed + 3` instead of half-available, freeing ships for next turn's launch.

**Local benchmark:** vs-random 10/0/0 [PASS], self-play 3/2/0 [PASS]. vs-random idle 2.9/game (target <5 ✓). Self-play idle 109.6/game = mirror-match deadlock artifact, not real signal.

**Submitted:** yes — 2026-05-11 12:11

**Kaggle result:** [pending — fill in after 20+ episodes]

**Learning:** [pending — fill in after Kaggle result known]
