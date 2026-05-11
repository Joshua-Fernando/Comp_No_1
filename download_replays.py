#!/usr/bin/env python3
"""
download_replays.py — Download replays + agent logs for recent episodes.
Usage: .venv/bin/python download_replays.py [--submission-id ID] [--n N]
"""

import argparse
import csv
import json
import sys
from pathlib import Path

from kaggle.api.kaggle_api_extended import KaggleApi
from kagglesdk.competitions.types.competition_api_service import (
    ApiGetEpisodeReplayRequest,
    ApiGetEpisodeAgentLogsRequest,
)

COMPETITION = "orbit-wars"
REPLAY_DIR  = Path("replays")
LOG_DIR     = Path("logs")


def get_api():
    api = KaggleApi()
    api.authenticate()
    return api


def download_replay(api, episode_id: int) -> bytes:
    out = REPLAY_DIR / f"{episode_id}.json"
    if out.exists():
        return out.read_bytes()
    REPLAY_DIR.mkdir(exist_ok=True)
    with api.build_kaggle_client() as k:
        req = ApiGetEpisodeReplayRequest()
        req.episode_id = episode_id
        resp = k.competitions.competition_api_client.get_episode_replay(req)
    out.write_bytes(resp.content)
    return resp.content


def download_agent_log(api, episode_id: int, agent_index: int) -> Path:
    out = LOG_DIR / f"{episode_id}_agent{agent_index}.json"
    if out.exists():
        return out
    LOG_DIR.mkdir(exist_ok=True)
    with api.build_kaggle_client() as k:
        req = ApiGetEpisodeAgentLogsRequest()
        req.episode_id = episode_id
        req.agent_index = agent_index
        resp = k.competitions.competition_api_client.get_episode_agent_logs(req)
    out.write_bytes(resp.content)
    return out


def total_ships(obs, pid):
    return (sum(p[5] for p in obs.get("planets", []) if p[1] == pid) +
            sum(f[6] for f in obs.get("fleets",  []) if f[1] == pid))


def parse_result(data: dict, my_pid: int):
    steps   = data["steps"]
    rewards = data.get("rewards", [0, 0])
    opp_pid = 1 - my_pid

    r_me, r_op = rewards[my_pid], rewards[opp_pid]
    if r_me > r_op:
        result = "WIN"
    elif r_me < r_op:
        result = "LOSS"
    else:
        result = "DRAW"

    final = steps[-1]
    obs = {}
    for ag in final:
        o = ag.get("observation", {})
        if o.get("player") == 0:
            obs = o
            break
    margin = total_ships(obs, my_pid) - total_ships(obs, opp_pid)
    return result, margin


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission-id", type=int, default=None)
    parser.add_argument("--n", type=int, default=20)
    args = parser.parse_args()

    api = get_api()

    # Get submission ID
    if args.submission_id:
        sub_id = args.submission_id
    else:
        subs = api.competition_submissions(COMPETITION)
        if not subs:
            print("No submissions found.", file=sys.stderr)
            sys.exit(1)
        sub_id = subs[0]._ref
    print(f"Submission: {sub_id}")

    # Get episodes
    episodes = api.competition_list_episodes(sub_id)[:args.n]
    print(f"Episodes: {len(episodes)}")

    rows = []
    for ep in episodes:
        ep_id = ep._id

        # Find my agent index and opponent name
        my_idx = None
        opp_name = "?"
        for ag in ep._agents:
            if ag._submission_id == sub_id:
                my_idx = ag._index
            else:
                opp_name = ag._team_name or "?"
        if my_idx is None:
            print(f"  {ep_id}: my agent not found, skip")
            continue

        # Download replay
        print(f"  {ep_id}: replay...", end="", flush=True)
        try:
            raw = download_replay(api, ep_id)
            data = json.loads(raw)
            replay_path = str(REPLAY_DIR / f"{ep_id}.json")
        except Exception as e:
            print(f" replay FAILED: {e}")
            rows.append(dict(ep_id=ep_id, opponent=opp_name, result="ERR",
                             margin=0, replay_path="", log_path=""))
            continue

        result, margin = parse_result(data, my_idx)
        print(f" {result}", end="", flush=True)

        # Download agent log for losses
        log_path = ""
        if result == "LOSS":
            print(f" log...", end="", flush=True)
            try:
                lp = download_agent_log(api, ep_id, my_idx)
                log_path = str(lp)
                print(" ok", end="")
            except Exception as e:
                print(f" log FAILED: {e}", end="")
        print()

        rows.append(dict(ep_id=ep_id, opponent=opp_name, result=result,
                         margin=margin, replay_path=replay_path, log_path=log_path))

    # Print table
    print()
    print(f"{'ep_id':>12}  {'opponent':<22}  {'result':>6}  {'margin':>8}  {'log?':>4}")
    print("-" * 62)
    for r in rows:
        has_log = "yes" if r["log_path"] else ""
        print(f"{r['ep_id']:>12}  {r['opponent']:<22}  {r['result']:>6}  {r['margin']:>+8}  {has_log:>4}")

    wins   = sum(1 for r in rows if r["result"] == "WIN")
    losses = sum(1 for r in rows if r["result"] == "LOSS")
    draws  = sum(1 for r in rows if r["result"] == "DRAW")
    print(f"\nW/L/D: {wins}/{losses}/{draws} of {len(rows)}")

    # Save CSV
    csv_path = Path("download_summary.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ep_id","opponent","result","margin","replay_path","log_path"])
        w.writeheader()
        w.writerows(rows)
    print(f"Saved: {csv_path}")


if __name__ == "__main__":
    main()
