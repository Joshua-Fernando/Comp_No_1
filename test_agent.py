#!/usr/bin/env python3
"""
Orbit Wars — test harness
  • 5 games vs built-in 'random' bot  (seeds 0–4)
  • 3 games vs self                   (seeds 0–2)
Reports: win/loss/draw, avg final score, avg score differential, exceptions.

--diagnose: run seeds 0–2 self-play and print fleet launches + side-by-side 0–75 tables
"""

import argparse
import math
from kaggle_environments import make

RANDOM_SEEDS   = list(range(5))
SELF_SEEDS     = list(range(3))
MY_AGENT       = "main.py"
DIAGNOSE_TURNS = list(range(0, 76, 5))   # every 5 turns, 0–75


def final_stats(obs, player_id: int) -> dict:
    """Extract ship counts and planet stats from an observation dict."""
    planets = obs.get("planets", [])
    fleets  = obs.get("fleets",  [])
    owned   = [p for p in planets if p[1] == player_id]
    ships_on_planets = sum(p[5] for p in owned)
    ships_in_fleets  = sum(f[6] for f in fleets if f[1] == player_id)
    production       = sum(p[6] for p in owned)
    return {
        "ships":       ships_on_planets + ships_in_fleets,
        "on_planets":  ships_on_planets,
        "in_fleets":   ships_in_fleets,
        "planets":     len(owned),
        "production":  production,
    }


def run_game(agent_a: str, agent_b: str, seed: int):
    """
    Run one game to completion.
    Returns (reward_a, reward_b, stats_a, stats_b, exceptions, env).
    reward_* is the binary +1/-1 (win/loss). stats_* are actual ship counts.
    All are None if the game crashed before finishing.
    """
    env = make("orbit_wars", configuration={"seed": seed}, debug=True)
    errors = []

    try:
        env.run([agent_a, agent_b])
    except Exception as exc:
        errors.append(f"game crash: {exc}")
        return None, None, None, None, errors, env

    for turn, step in enumerate(env.steps):
        for pid, agent_label in ((0, "my_agent"), (1, "opponent")):
            if len(step) <= pid:
                continue
            status = step[pid].get("status", "")
            if status == "ERROR":
                info = step[pid].get("info", {})
                errors.append(f"turn {turn} [{agent_label}] ERROR: {info}")

    final    = env.steps[-1]
    reward_a = float(final[0].get("reward") or 0)
    reward_b = float(final[1].get("reward") or 0)

    obs_a = final[0].get("observation") or {}
    obs_b = final[1].get("observation") or {}
    stats_a = final_stats(obs_a, 0)
    stats_b = final_stats(obs_b, 1)

    return reward_a, reward_b, stats_a, stats_b, errors, env


def infer_target(obs, src_id: int, fleet_angle: float) -> str:
    """Guess which planet a fleet is heading toward from its launch angle."""
    planets = obs.get("planets", [])
    src = next((p for p in planets if p[0] == src_id), None)
    if src is None:
        return "?"
    sx, sy = src[2], src[3]
    best, best_diff = None, math.inf
    for p in planets:
        if p[0] == src_id:
            continue
        direct = math.atan2(p[3] - sy, p[2] - sx)
        diff = abs(math.atan2(math.sin(fleet_angle - direct),
                              math.cos(fleet_angle - direct)))
        if diff < best_diff:
            best_diff, best = diff, p
    if best and best_diff < 0.5:
        owner_str = f"P{best[1]}" if best[1] >= 0 else "neu"
        return f"pl{best[0]:>2}({owner_str} sh={best[5]} pr={best[6]})"
    return f"angle={fleet_angle:.2f}"


def collect_game_data(env):
    """Returns (snapshots, fleet_launches) for turns 0–75 of a completed game."""
    snapshots = []
    for t in DIAGNOSE_TURNS:
        if t >= len(env.steps):
            break
        obs = env.steps[t][0].get("observation") or {}
        s0 = final_stats(obs, 0)
        s1 = final_stats(obs, 1)
        snapshots.append((t, s0["planets"], s1["planets"], s0["ships"], s1["ships"]))

    fleet_launches = []
    prev_ids: set = set()
    for t in range(min(76, len(env.steps))):
        obs = env.steps[t][0].get("observation") or {}
        fleets = obs.get("fleets", [])
        for f in fleets:
            if f[0] not in prev_ids:
                tgt = infer_target(obs, f[5], f[4])
                fleet_launches.append((t, f[1], f[6], f[5], tgt))
        prev_ids = {f[0] for f in fleets}

    return snapshots, fleet_launches


def diagnose_multi_seed(seeds: list):
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  Diagnose: Agent vs Self — seeds {seeds}, turns 0–75")
    print(sep)

    all_data = {}
    for seed in seeds:
        print(f"\n  [seed={seed}] running...", end="", flush=True)
        ra, rb, sa, sb, errors, env = run_game(MY_AGENT, MY_AGENT, seed)
        if sa and sb:
            outcome = "WIN " if sa["ships"] > sb["ships"] else "LOSS"
            print(f"  {outcome}  my={sa['ships']}  opp={sb['ships']}")
        else:
            print("  CRASHED")
        snapshots, fleet_launches = collect_game_data(env)
        all_data[seed] = (snapshots, fleet_launches)

    # Fleet launches per seed
    for seed in seeds:
        snapshots, fleet_launches = all_data[seed]
        print(f"\n  Fleet launches — seed={seed}:")
        print(f"  {'turn':>4}  P  {'ships':>5}  from   target")
        print(f"  {'----':>4}  -  {'-----':>5}  ----   ------")
        for t, owner, ships, src, tgt in fleet_launches:
            print(f"  {t:>4}  {owner}  {ships:>5}  pl{src:<2}   {tgt}")

    # Side-by-side snapshot table
    col_w   = 22
    hdr_row = "  |  ".join(f"{'seed='+str(s)+':':<6} p0pl p1pl  p0sh  p1sh" for s in seeds)
    div_row = "  |  ".join("-" * col_w for _ in seeds)
    print(f"\n  {'turn':>4}  {hdr_row}")
    print(f"  {'----':>4}  {div_row}")

    max_rows = max(len(all_data[s][0]) for s in seeds)
    for i in range(max_rows):
        parts = []
        t_val = ""
        for seed in seeds:
            rows = all_data[seed][0]
            if i < len(rows):
                t, p0pl, p1pl, p0sh, p1sh = rows[i]
                t_val = t
                parts.append(f"       {p0pl:>4} {p1pl:>4}  {p0sh:>4}  {p1sh:>4}")
            else:
                parts.append(" " * col_w)
        print(f"  {t_val:>4}  {'  |  '.join(parts)}")

    # Auto-analysis
    print(f"\n  Analysis:")
    for seed in seeds:
        rows = all_data[seed][0]
        row_25 = next((r for r in rows if r[0] == 25), None)
        row_50 = next((r for r in rows if r[0] == 50), None)
        flags = []
        if row_25 and row_25[1] < 2:
            flags.append(f"P0 still 1 planet at t25")
        if row_50:
            ratio = row_50[3] / max(row_50[4], 1)
            if ratio < 0.8:
                flags.append(f"P0 ships at t50 = {ratio:.0%} of P1 (want ≥80%)")
            else:
                flags.append(f"P0 ships at t50 = {ratio:.0%} of P1 OK")
        print(f"    seed={seed}: {', '.join(flags) if flags else 'OK'}")


def evaluate(agent_a: str, agent_b: str, seeds: list, label: str):
    sep = "=" * 62
    print(f"\n{sep}")
    print(f"  {label}")
    print(sep)

    wins = losses = draws = crashed = 0
    ships_a_list, diffs = [], []
    all_errors = []

    for seed in seeds:
        ra, rb, sa, sb, errors, env = run_game(agent_a, agent_b, seed)

        for msg in errors:
            all_errors.append(f"  seed={seed}  {msg}")

        if ra is None:
            crashed += 1
            print(f"  seed={seed}:  CRASHED")
            continue

        diff = sa["ships"] - sb["ships"]
        diffs.append(diff)
        ships_a_list.append(sa["ships"])

        if ra > rb:
            outcome = "WIN "
            wins += 1
        elif rb > ra:
            outcome = "LOSS"
            losses += 1
        else:
            outcome = "DRAW"
            draws += 1

        print(f"  seed={seed}:  {outcome}"
              f"  my={sa['ships']:6d} (pl={sa['ships'] - sa['in_fleets']:5d} fl={sa['in_fleets']:5d}"
              f"  planets={sa['planets']:2d}  prod={sa['production']:3d})"
              f"  opp={sb['ships']:6d} (pl={sb['ships'] - sb['in_fleets']:5d} fl={sb['in_fleets']:5d}"
              f"  planets={sb['planets']:2d}  prod={sb['production']:3d})"
              f"  diff={diff:+d}")

    total    = wins + losses + draws
    wr       = wins / total * 100 if total else 0.0
    avg_sc   = sum(ships_a_list) / len(ships_a_list) if ships_a_list else 0.0
    avg_diff = sum(diffs)        / len(diffs)        if diffs        else 0.0

    print(f"\n  Games completed : {total}  (crashed: {crashed})")
    print(f"  Win / Loss / Draw: {wins} / {losses} / {draws}  ({wr:.0f}% win rate)")
    print(f"  Avg final ships  : {avg_sc:.0f}")
    print(f"  Avg ship diff    : {avg_diff:+.0f}")

    if all_errors:
        print(f"\n  Exceptions ({len(all_errors)}):")
        for msg in all_errors:
            print(f"   {msg}")

    return wins, losses, draws, avg_diff


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnose", action="store_true",
                        help="Run seeds 0–2 self-play, print fleet logs + side-by-side 0–75 tables")
    args = parser.parse_args()

    if args.diagnose:
        diagnose_multi_seed([0, 1, 2])
        return

    rw, rl, rd, r_diff = evaluate(
        MY_AGENT, "random", RANDOM_SEEDS,
        "Agent vs Random — 5 games (seeds 0–4)"
    )
    evaluate(
        MY_AGENT, MY_AGENT, SELF_SEEDS,
        "Agent vs Self — 3 games (seeds 0–2)"
    )

    sign = "+" if r_diff >= 0 else ""
    print(f"\n{'=' * 62}")
    print(f"W/L/D vs random: {rw}/{rl}/{rd} | avg ship diff: {sign}{r_diff:.0f}")
    print(f"{'=' * 62}")


if __name__ == "__main__":
    main()
