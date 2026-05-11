#!/usr/bin/env python3
"""
daily_review.py — Download and analyze recent episodes.
Picks 3 notable games: closest loss, worst loss, best win.
Saves replays to ./replays/YYYY-MM-DD/.
Usage: .venv/bin/python daily_review.py [--submission-id ID] [--n N]
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from kaggle.api.kaggle_api_extended import KaggleApi
from kagglesdk.competitions.types.competition_api_service import ApiGetEpisodeReplayRequest

COMPETITION = "orbit-wars"


def get_api():
    api = KaggleApi()
    api.authenticate()
    return api


def download_replay(api, episode_id: int, out_dir: Path) -> bytes:
    out = out_dir / f"{episode_id}.json"
    if out.exists():
        return out.read_bytes()
    out_dir.mkdir(parents=True, exist_ok=True)
    with api.build_kaggle_client() as k:
        req = ApiGetEpisodeReplayRequest()
        req.episode_id = episode_id
        resp = k.competitions.competition_api_client.get_episode_replay(req)
    out.write_bytes(resp.content)
    return resp.content


def total_ships(obs, pid):
    return (sum(p[5] for p in obs.get("planets", []) if p[1] == pid) +
            sum(f[6] for f in obs.get("fleets",  []) if f[1] == pid))


def parse_result(data: dict, my_pid: int):
    rewards = data.get("rewards", [0, 0])
    opp_pid = 1 - my_pid
    r_me, r_op = rewards[my_pid], rewards[opp_pid]
    if r_me > r_op:
        result = "WIN"
    elif r_me < r_op:
        result = "LOSS"
    else:
        result = "DRAW"

    final = data["steps"][-1]
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
    parser.add_argument("--n", type=int, default=50,
                        help="Episodes to scan (default 50 ≈ last 24h)")
    args = parser.parse_args()

    api = get_api()
    today_dir = Path("replays") / date.today().isoformat()

    if args.submission_id:
        sub_id = args.submission_id
    else:
        subs = api.competition_submissions(COMPETITION)
        if not subs:
            print("No submissions found.", file=sys.stderr)
            sys.exit(1)
        sub_id = subs[0]._ref
    print(f"Submission: {sub_id}")
    print(f"Replay dir: {today_dir}/")

    episodes = api.competition_list_episodes(sub_id)[:args.n]
    print(f"Scanning {len(episodes)} episodes...\n")

    rows = []
    for ep in episodes:
        ep_id = ep._id
        my_idx = None
        opp_name = "?"
        opp_score = None
        for ag in ep._agents:
            if getattr(ag, '_submission_id', None) == sub_id:
                my_idx = ag._index
            else:
                opp_name = getattr(ag, '_team_name', None) or "?"
                opp_score = getattr(ag, '_score', None)
        if my_idx is None:
            continue

        print(f"  {ep_id}...", end="", flush=True)
        try:
            raw  = download_replay(api, ep_id, today_dir)
            data = json.loads(raw)
        except Exception as e:
            print(f" FAILED: {e}")
            continue

        result, margin = parse_result(data, my_idx)
        print(f" {result} margin={margin:+d}")
        rows.append(dict(ep_id=ep_id, result=result, margin=margin,
                         opponent=opp_name, opp_score=opp_score))

    if not rows:
        print("No episodes parsed.")
        return

    losses = [r for r in rows if r["result"] == "LOSS"]
    wins   = [r for r in rows if r["result"] == "WIN"]

    picks = {}

    if losses:
        closest = min(losses, key=lambda r: abs(r["margin"]))
        picks["closest_loss"] = closest

        worst = min(losses, key=lambda r: r["margin"])
        if worst["ep_id"] != closest["ep_id"]:
            picks["worst_loss"] = worst

    if wins:
        # "best win vs higher-rated" — use opp_score if available, else largest margin
        scored_wins = [w for w in wins if w["opp_score"] is not None]
        if scored_wins:
            best = max(scored_wins, key=lambda w: w["opp_score"])
        else:
            best = max(wins, key=lambda w: w["margin"])
        picks["best_win"] = best

    print(f"\n{'=' * 60}")
    print(f"  DAILY REVIEW — {date.today().isoformat()}")
    print(f"{'=' * 60}")
    print(f"  {'Label':<18}  {'ep_id':>12}  {'result':>6}  {'margin':>8}  {'opponent':<22}  {'opp_score':>10}")
    print(f"  {'-'*18}  {'-'*12}  {'-'*6}  {'-'*8}  {'-'*22}  {'-'*10}")
    for label, r in picks.items():
        opp_sc = str(r["opp_score"]) if r["opp_score"] is not None else "unknown"
        print(f"  {label:<18}  {r['ep_id']:>12}  {r['result']:>6}  {r['margin']:>+8}  {r['opponent']:<22}  {opp_sc:>10}")

    total = len(rows)
    n_wins   = sum(1 for r in rows if r["result"] == "WIN")
    n_losses = sum(1 for r in rows if r["result"] == "LOSS")
    n_draws  = sum(1 for r in rows if r["result"] == "DRAW")
    print(f"\n  W/L/D: {n_wins}/{n_losses}/{n_draws} of {total} scanned")
    print(f"  Replays saved to: {today_dir}/")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
