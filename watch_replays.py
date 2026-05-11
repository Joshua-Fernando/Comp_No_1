#!/usr/bin/env python3
"""
watch_replays.py — Post-submission validation loop.
Fetches the 10 most recent episodes for the latest submission, downloads
each replay, and prints a summary table.

Usage:
    .venv/bin/python watch_replays.py [--submission-id ID] [--n N]
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

COMPETITION = "orbit-wars"
REPLAY_DIR  = Path("replays")
MY_TEAM     = "Joshua Fernando"


# ── kaggle API helpers ────────────────────────────────────────────────────────

def get_api():
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    return api


def get_latest_submission_id(api) -> int:
    subs = api.competition_submissions(COMPETITION)
    if not subs:
        print("No submissions found.", file=sys.stderr)
        sys.exit(1)
    return subs[0]._ref


def get_episodes(api, submission_id: int, n: int) -> list:
    eps = api.competition_list_episodes(submission_id)
    return eps[:n]


def download_replay(api, episode_id: int) -> dict:
    out = REPLAY_DIR / f"{episode_id}.json"
    if out.exists():
        return json.loads(out.read_bytes())

    from kagglesdk.competitions.types.competition_api_service import ApiGetEpisodeReplayRequest
    with api.build_kaggle_client() as kaggle:
        req = ApiGetEpisodeReplayRequest()
        req.episode_id = episode_id
        resp = kaggle.competitions.competition_api_client.get_episode_replay(req)

    REPLAY_DIR.mkdir(exist_ok=True)
    out.write_bytes(resp.content)
    return json.loads(resp.content)


# ── replay analysis ───────────────────────────────────────────────────────────

def _obs(step, pid):
    """Get observation from a step for player pid."""
    for ag in step:
        o = ag.get("observation", {})
        if o.get("player") == pid:
            return o
    if pid < len(step):
        return step[pid].get("observation", {})
    return {}


def _planet_counts(obs, n_players):
    planets = obs.get("planets", [])
    return [sum(1 for p in planets if p[1] == pid) for pid in range(n_players)]


def _total_ships(obs, pid):
    planets = obs.get("planets", [])
    fleets  = obs.get("fleets",  [])
    return (sum(p[5] for p in planets if p[1] == pid) +
            sum(f[6] for f in fleets   if f[1] == pid))


def analyze(data: dict, my_pid: int) -> dict:
    steps     = data["steps"]
    rewards   = data.get("rewards", [0, 0])
    n_turns   = len(steps)
    opp_pid   = 1 - my_pid

    # Outcome
    r_me, r_op = rewards[my_pid], rewards[opp_pid]
    if r_me > r_op:
        result = "WIN"
    elif r_me < r_op:
        result = "LOSS"
    else:
        result = "DRAW"

    # Planet counts at t50 / t100
    def pcount_at(t, pid):
        idx = min(t, n_turns - 1)
        return _planet_counts(_obs(steps[idx], 0), 2)[pid]

    my_pl_50  = pcount_at(50,  my_pid)
    opp_pl_50 = pcount_at(50,  opp_pid)
    my_pl_100 = pcount_at(100, my_pid)

    # Fleet launches per player (count unique fleet ids seen per owner)
    seen_ids  = set()
    fleet_counts   = defaultdict(int)
    fleet_ships    = defaultdict(list)

    for step in steps:
        obs = _obs(step, 0)
        for f in obs.get("fleets", []):
            fid, owner, *_, fships = f[0], f[1], f[6]
            if fid not in seen_ids:
                seen_ids.add(fid)
                fleet_counts[owner] += 1
                fleet_ships[owner].append(f[6])

    my_fleets  = fleet_counts[my_pid]
    opp_fleets = fleet_counts[opp_pid]
    my_avg     = (sum(fleet_ships[my_pid]) / my_fleets) if my_fleets else 0.0

    # Margin
    final_obs_me  = _obs(steps[-1], my_pid)
    final_obs_opp = _obs(steps[-1], opp_pid)
    margin = _total_ships(final_obs_me, my_pid) - _total_ships(final_obs_opp, opp_pid)

    return dict(
        result=result,
        my_pl_50=my_pl_50,
        opp_pl_50=opp_pl_50,
        my_pl_100=my_pl_100,
        my_fleets=my_fleets,
        opp_fleets=opp_fleets,
        my_avg_fleet=my_avg,
        margin=margin,
        stuck=(my_pl_50 == 1),
    )


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission-id", type=int, default=None)
    parser.add_argument("--n", type=int, default=10, help="episodes to fetch (default 10)")
    args = parser.parse_args()

    api = get_api()

    sub_id = args.submission_id or get_latest_submission_id(api)
    print(f"Submission ID: {sub_id}")

    episodes = get_episodes(api, sub_id, args.n)
    print(f"Episodes found: {len(episodes)}")

    if not episodes:
        print("No episodes to analyze.")
        return

    # Determine my submission ID so we can find my agent index per episode
    subs = api.competition_submissions(COMPETITION)
    my_sub_id = sub_id

    rows = []
    for ep in episodes:
        ep_id = ep._id
        agents = ep._agents  # list of dicts

        # Find my agent index in this episode
        my_idx = None
        for ag in agents:
            sub = ag._submission_id if hasattr(ag, "_submission_id") else ag.get("submissionId")
            if sub == my_sub_id:
                my_idx = ag._index if hasattr(ag, "_index") else ag.get("index")
                break
        if my_idx is None:
            print(f"  ep {ep_id}: can't find my agent, skipping")
            continue

        print(f"  ep {ep_id}: downloading...", end="", flush=True)
        try:
            data = download_replay(api, ep_id)
        except Exception as e:
            print(f" FAILED ({e})")
            continue

        stats = analyze(data, my_idx)
        stats["ep_id"] = ep_id
        rows.append(stats)
        print(f" {stats['result']}")

    if not rows:
        print("No rows to summarize.")
        return

    # ── table ────────────────────────────────────────────────────────────────
    W = [10, 6, 9, 10, 11, 12, 10, 8]
    hdr = (f"{'ep_id':>10}  {'result':>6}  "
           f"{'my_pl_50':>9}  {'opp_pl_50':>10}  "
           f"{'my_fleets':>11}  {'opp_fleets':>12}  "
           f"{'avg_sz':>10}  {'margin':>8}")
    sep = "─" * len(hdr)
    print(f"\n{sep}")
    print(hdr)
    print(sep)
    for r in rows:
        margin_str = f"{r['margin']:+d}"
        print(f"{r['ep_id']:>10}  {r['result']:>6}  "
              f"{r['my_pl_50']:>9}  {r['opp_pl_50']:>10}  "
              f"{r['my_fleets']:>11}  {r['opp_fleets']:>12}  "
              f"{r['my_avg_fleet']:>10.1f}  {margin_str:>8}")
    print(sep)

    # ── summary ──────────────────────────────────────────────────────────────
    total  = len(rows)
    wins   = sum(1 for r in rows if r["result"] == "WIN")
    losses = sum(1 for r in rows if r["result"] == "LOSS")
    draws  = sum(1 for r in rows if r["result"] == "DRAW")
    avg_sz = sum(r["my_avg_fleet"] for r in rows) / total
    stuck  = sum(1 for r in rows if r["stuck"])

    print(f"\nWin rate: {wins}/{total}  ({wins}W/{losses}L/{draws}D)")
    print(f"Avg fleet size: {avg_sz:.1f}")
    print(f"Stuck-at-1-planet count: {stuck}/{total}")


if __name__ == "__main__":
    main()
