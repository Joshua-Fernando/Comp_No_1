"""
Replay analyzer for Orbit Wars episode JSON files.
Usage: python replay_analyzer.py <replay.json> [<replay2.json> ...]
"""

import json
import math
import sys
from collections import defaultdict

CENTER_X, CENTER_Y = 50.0, 50.0
SUN_RADIUS = 10.0
CHECKPOINT_TURNS = [0, 100, 200, 300, 400, 500]


def fleet_speed(n: int) -> float:
    if n <= 1:
        return 1.0
    return 1.0 + 5.0 * (math.log(n) / math.log(1000)) ** 1.5


def path_hits_sun(x1, y1, x2, y2, margin=1.5) -> bool:
    danger = SUN_RADIUS + margin
    dx, dy = x2 - x1, y2 - y1
    fx, fy = x1 - CENTER_X, y1 - CENTER_Y
    a = dx*dx + dy*dy
    if a < 1e-9:
        return math.hypot(fx, fy) < danger
    t = -(fx*dx + fy*dy) / a
    t = max(0.0, min(1.0, t))
    return math.hypot(fx + t*dx, fy + t*dy) < danger


def get_obs(step_agents, player):
    """Get observation from a step, trying both player indices."""
    for ag in step_agents:
        obs = ag.get("observation", {})
        if obs.get("player") == player:
            return obs
    # Fallback: use step[player]
    if player < len(step_agents):
        return step_agents[player].get("observation", {})
    return {}


def analyze_replay(path: str):
    with open(path) as f:
        data = json.load(f)

    steps = data["steps"]
    n_turns = len(steps)
    n_players = len(steps[0])
    agent_names = [a.get("Name", f"P{i}") for a, i in
                   zip(data["info"].get("Agents", []), range(n_players))]
    final_rewards = data.get("rewards", [0] * n_players)

    print(f"\n{'='*70}")
    print(f"Episode: {data['info'].get('EpisodeId', '?')}  |  {path.split('/')[-1]}")
    print(f"Players: {', '.join(f'{n} (P{i})' for i, n in enumerate(agent_names))}")
    print(f"Turns played: {n_turns} / 500")
    print(f"Final rewards: {dict(zip(agent_names, final_rewards))}")

    # --- 1. Final ship counts ---
    final_step = steps[-1]
    print(f"\n{'─'*40}")
    print("FINAL SHIP COUNTS:")
    for pid in range(n_players):
        obs = get_obs(final_step, pid)
        planets = obs.get("planets", [])
        fleets  = obs.get("fleets",  [])
        pl_ships = sum(p[5] for p in planets if p[1] == pid)
        fl_ships = sum(f[6] for f in fleets  if f[1] == pid)
        n_planets = sum(1 for p in planets if p[1] == pid)
        print(f"  {agent_names[pid]}: {pl_ships+fl_ships} ships  "
              f"({pl_ships} on planets, {fl_ships} in fleets)  |  {n_planets} planets")

    # --- 2. Planet count snapshots ---
    print(f"\n{'─'*40}")
    print("PLANET COUNT PER TURN (using P0 obs):")
    hdr = f"{'turn':>5}  " + "  ".join(f"{n[:12]:>12}" for n in agent_names)
    print(f"  {hdr}")
    obs0_first = get_obs(steps[0], 0)
    total_planets = len(obs0_first.get("planets", []))

    for ck in CHECKPOINT_TURNS:
        if ck >= n_turns:
            idx = n_turns - 1
            label = f"{ck}*"
        else:
            idx = ck
            label = str(ck)
        obs = get_obs(steps[idx], 0)
        planets = obs.get("planets", [])
        counts = [sum(1 for p in planets if p[1] == pid) for pid in range(n_players)]
        neutral = sum(1 for p in planets if p[1] == -1)
        row = "  ".join(f"{c:>12}" for c in counts)
        print(f"  {label:>5}  {row}  (neu={neutral})")

    # --- 3. Fleet launches and ship counts per player ---
    print(f"\n{'─'*40}")
    print("FLEET LAUNCHES:")

    launches_per_player = defaultdict(list)   # pid -> list of fleet sizes
    seen_fleet_ids = set()
    actions_per_player = defaultdict(int)

    # Track actions (moves emitted by agents)
    for t, step_agents in enumerate(steps):
        for pid, ag in enumerate(step_agents):
            action = ag.get("action") or []
            for move in action:
                if isinstance(move, list) and len(move) >= 3:
                    actions_per_player[pid] += 1

    # Track fleet appearances as proxy for launches
    for t, step_agents in enumerate(steps):
        obs = get_obs(step_agents, 0)
        fleets = obs.get("fleets", [])
        for f in fleets:
            fid = f[0]
            if fid not in seen_fleet_ids:
                seen_fleet_ids.add(fid)
                owner = f[1]
                ships = f[6]
                launches_per_player[owner].append(ships)

    for pid in range(n_players):
        fleet_sizes = launches_per_player[pid]
        if not fleet_sizes:
            print(f"  {agent_names[pid]}: 0 fleets")
            continue
        total_ships = sum(fleet_sizes)
        n_fleets = len(fleet_sizes)
        avg_size = total_ships / n_fleets
        small = sum(1 for s in fleet_sizes if s <= 10)
        large = sum(1 for s in fleet_sizes if s > 50)
        print(f"  {agent_names[pid]}: {n_fleets} fleets, {total_ships} total ships launched")
        print(f"    avg fleet size: {avg_size:.1f}  |  small(≤10): {small}  large(>50): {large}")
        print(f"    size distribution: "
              f"≤5:{sum(1 for s in fleet_sizes if s<=5)}  "
              f"6-20:{sum(1 for s in fleet_sizes if 6<=s<=20)}  "
              f"21-50:{sum(1 for s in fleet_sizes if 21<=s<=50)}  "
              f">50:{large}")

    # --- 4. Sun-loss detection ---
    print(f"\n{'─'*40}")
    print("SUN LOSS DETECTION (fleets on sun-crossing trajectories):")

    sun_risk_ships = defaultdict(int)
    sun_risk_fleets = defaultdict(int)
    prev_fleet_ids = set()

    for t, step_agents in enumerate(steps):
        obs = get_obs(step_agents, 0)
        fleets = obs.get("fleets", [])
        cur_ids = {f[0] for f in fleets}

        for f in fleets:
            fid, owner, fx, fy, angle, from_pid, fships = f
            vx = math.cos(angle)
            vy = math.sin(angle)
            # Project path 200 units ahead
            ex, ey = fx + vx * 200, fy + vy * 200
            if path_hits_sun(fx, fy, ex, ey, margin=0.5):
                sun_risk_fleets[owner] += 1
                sun_risk_ships[owner] += fships

        prev_fleet_ids = cur_ids

    for pid in range(n_players):
        rf = sun_risk_fleets[pid]
        rs = sun_risk_ships[pid]
        print(f"  {agent_names[pid]}: {rf} fleet-turns on sun-crossing path "
              f"(cumulative ships at risk: {rs})")
    print("  (Note: fleet-turns is per-turn count, not unique fleets)")

    # --- 5. Behavioral patterns ---
    print(f"\n{'─'*40}")
    print("BEHAVIORAL PATTERNS:")

    # Check if any player used many-small-fleet strategy
    for pid in range(n_players):
        fleet_sizes = launches_per_player[pid]
        if not fleet_sizes:
            continue
        n_fleets = len(fleet_sizes)
        avg = sum(fleet_sizes) / n_fleets if n_fleets else 0
        small_frac = sum(1 for s in fleet_sizes if s <= 10) / n_fleets if n_fleets else 0

        pattern = []
        if small_frac > 0.6:
            pattern.append(f"SWARM STRATEGY (≥60% small fleets, avg={avg:.1f})")
        elif avg > 60:
            pattern.append(f"HEAVY FLEET STRATEGY (avg size={avg:.1f})")
        else:
            pattern.append(f"BALANCED fleets (avg={avg:.1f})")

        # Check aggression timing: when did they first attack an enemy planet?
        first_attack_turn = None
        owned_by = defaultdict(lambda: -1)
        obs0 = get_obs(steps[0], 0)
        for p in obs0.get("planets", []):
            owned_by[p[0]] = p[1]

        for t, step_agents in enumerate(steps[1:], 1):
            obs = get_obs(step_agents, 0)
            for p in obs.get("planets", []):
                prev_owner = owned_by[p[0]]
                new_owner = p[1]
                if prev_owner != new_owner and new_owner == pid and prev_owner != -1:
                    first_attack_turn = t
                    break
                owned_by[p[0]] = new_owner
            if first_attack_turn is not None:
                break

        if first_attack_turn:
            pattern.append(f"first enemy capture at turn {first_attack_turn}")

        # Early expansion: planets owned at turn 50
        t50 = min(50, n_turns - 1)
        obs50 = get_obs(steps[t50], 0)
        pl_at_50 = sum(1 for p in obs50.get("planets", []) if p[1] == pid)
        pattern.append(f"{pl_at_50} planets at t50")

        print(f"  {agent_names[pid]}: {' | '.join(pattern)}")

    # --- 6. Production race ---
    print(f"\n{'─'*40}")
    print("PRODUCTION RACE (prod/turn at checkpoints):")
    hdr2 = f"{'turn':>5}  " + "  ".join(f"{n[:12]:>12}" for n in agent_names)
    print(f"  {hdr2}")
    for ck in [0, 50, 100, 150, 200, 300, 400]:
        if ck >= n_turns:
            idx, label = n_turns - 1, f"{ck}*"
        else:
            idx, label = ck, str(ck)
        obs = get_obs(steps[idx], 0)
        planets = obs.get("planets", [])
        prods = [sum(p[6] for p in planets if p[1] == pid) for pid in range(n_players)]
        row = "  ".join(f"{pr:>12}" for pr in prods)
        print(f"  {label:>5}  {row}")


if __name__ == "__main__":
    files = sys.argv[1:]
    if not files:
        import glob
        files = sorted(glob.glob("/home/kali/Documents/comp/replays/*.json"))
    if not files:
        print("Usage: python replay_analyzer.py <replay.json> ...")
        sys.exit(1)
    for path in files:
        analyze_replay(path)
