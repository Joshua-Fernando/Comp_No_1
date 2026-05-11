# Common Mistakes

## 1. Module-level state not keyed by player_id

**Symptom**: Self-play gives asymmetric behavior — P0's failed_targets blocks P1's valid attacks or vice versa.
**Check**: Any module-level `dict` or `set` that persists between turns.
**Fix**: Key by `(player_id, entity_id)`. Add `failed_targets.clear()` at `if turn == 0`.

## 2. Trickle attacks — sending fleets that can't capture

**Symptom**: Agent ships drop sharply turns 30–50 in self-play; fleet log shows repeated small fleets to same target.
**Fix**: `min_fleet_size(target_ships) = max(target_ships + 1, 5)`. Skip targets in `failed_targets` for 20 turns after failure.

## 3. Wrong Python interpreter

**Symptom**: `ModuleNotFoundError: No module named 'kaggle_environments'`
**Fix**: Use `.venv/bin/python`, not `python3` or `python`.

## 4. Early-game target scoring ignores capture speed

**Symptom**: P0 takes first neutral at turn ~40 while P1 takes one at ~20.
**Fix**: For `turn < 75`, use `score = production / capture_time` (pure speed). Blend 40/60 with value-score after turn 75.

## 5. Reading binary reward as ship count

**Symptom**: All rewards appear as `1.0` or `-1.0`, not actual ships.
**Fix**: Use `obs["planets"][n][5]` and `obs["fleets"][n][6]` for real ship counts. `step[i]["reward"]` is win/loss only.
