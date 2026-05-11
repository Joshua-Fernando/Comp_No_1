#!/usr/bin/env python3
"""
benchmark.py — Standard pass/fail benchmark for Orbit Wars agent.
  10 vs-random (seeds 0-9), 5 self-play (seeds 0-4)
  PASS: vs-random >= 8/10 AND self-play >= 2/5
  Exit 0 = PASS, Exit 1 = FAIL
Usage: .venv/bin/python benchmark.py [--agent main_v11.py]
"""

import argparse
import sys
from kaggle_environments import make

RANDOM_SEEDS  = list(range(10))
SELF_SEEDS    = list(range(5))
RANDOM_THRESH = 8
SELF_THRESH   = 2
IDLE_THRESH   = 5   # idle turns per game target


def count_idle_turns(env, player_id=0, avail_proxy=38):
    """
    Turns where agent launched nothing despite having a large reserve.
    avail_proxy=38: with 20% garrison, ships=38 → available≈30.
    """
    idle = 0
    for step in env.steps[:-1]:
        if len(step) <= player_id:
            continue
        action = step[player_id].get("action") or []
        if action:
            continue
        obs = step[player_id].get("observation") or {}
        for p in obs.get("planets", []):
            if p[1] == player_id and p[5] >= avail_proxy:
                idle += 1
                break
    return idle


def run_game(agent_a, agent_b, seed):
    env = make("orbit_wars", configuration={"seed": seed}, debug=True)
    try:
        env.run([agent_a, agent_b])
    except Exception as exc:
        return None, None, None, str(exc)

    final    = env.steps[-1]
    reward_a = float(final[0].get("reward") or 0)
    reward_b = float(final[1].get("reward") or 0)
    obs_a    = final[0].get("observation") or {}

    planets = obs_a.get("planets", [])
    fleets  = obs_a.get("fleets",  [])
    ships_a = sum(p[5] for p in planets if p[1] == 0) + sum(f[6] for f in fleets if f[1] == 0)
    ships_b = sum(p[5] for p in planets if p[1] == 1) + sum(f[6] for f in fleets if f[1] == 1)
    idle    = count_idle_turns(env, player_id=0)
    return reward_a, reward_b, ships_a - ships_b, idle


def evaluate(agent_a, agent_b, seeds, label, thresh):
    print(f"\n{'=' * 62}")
    print(f"  {label}  (pass threshold: {thresh}/{len(seeds)})")
    print(f"{'=' * 62}")
    wins = losses = draws = 0
    idle_list = []

    for seed in seeds:
        ra, rb, diff, idle = run_game(agent_a, agent_b, seed)
        if ra is None:
            print(f"  seed={seed}: CRASHED ({diff})")
            losses += 1
            continue
        if ra > rb:
            result = "WIN "; wins += 1
        elif rb > ra:
            result = "LOSS"; losses += 1
        else:
            result = "DRAW"; draws += 1
        marker = "" if ra > rb else " !"
        idle_flag = f" idle={idle}" + (" *" if idle > IDLE_THRESH else "")
        print(f"  seed={seed}: {result}  diff={diff:+d}{marker}{idle_flag}")
        idle_list.append(idle)

    total    = wins + losses + draws
    passed   = wins >= thresh
    avg_idle = sum(idle_list) / len(idle_list) if idle_list else 0
    status   = "PASS" if passed else "FAIL"
    idle_ok  = avg_idle <= IDLE_THRESH
    print(f"\n  W/L/D: {wins}/{losses}/{draws}  [{status}]")
    print(f"  Avg idle turns/game: {avg_idle:.1f}  (target <{IDLE_THRESH})  [{'OK' if idle_ok else 'HIGH'}]")
    return wins, losses, draws, passed, avg_idle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", default="main.py",
                        help="Agent file to benchmark (default: main.py)")
    args = parser.parse_args()
    agent = args.agent

    rw, rl, rd, r_pass, r_idle = evaluate(agent, "random", RANDOM_SEEDS,
                                           f"vs Random — {len(RANDOM_SEEDS)} games  [{agent}]",
                                           RANDOM_THRESH)
    sw, sl, sd, s_pass, s_idle = evaluate(agent, agent, SELF_SEEDS,
                                           f"vs Self   — {len(SELF_SEEDS)} games  [{agent}]",
                                           SELF_THRESH)

    overall    = r_pass and s_pass
    idle_avg   = (r_idle * len(RANDOM_SEEDS) + s_idle * len(SELF_SEEDS)) / (len(RANDOM_SEEDS) + len(SELF_SEEDS))
    idle_pass  = idle_avg <= IDLE_THRESH
    verdict    = "PASS — safe to submit" if overall else "FAIL — do NOT submit"

    print(f"\n{'=' * 62}")
    print(f"  Agent     : {agent}")
    print(f"  vs-random : {rw}/{len(RANDOM_SEEDS)}  {'OK' if r_pass else f'FAIL (need {RANDOM_THRESH})'}")
    print(f"  self-play : {sw}/{len(SELF_SEEDS)}   {'OK' if s_pass else f'FAIL (need {SELF_THRESH})'}")
    print(f"  idle turns: {idle_avg:.1f}/game  {'OK' if idle_pass else f'HIGH (target <{IDLE_THRESH})'}")
    print(f"\n  VERDICT: {verdict}")
    print(f"{'=' * 62}")

    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
