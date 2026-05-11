#!/bin/bash
# Orbit Wars morning status check
# Usage: bash morning_check.sh
COMP="orbit-wars"
SCORE_FILE=".last_score"
MY_TEAM="Joshua Fernando"
DATE=$(date "+%Y-%m-%d %H:%M")

echo "========================================"
echo "  Orbit Wars Morning Check — $DATE"
echo "========================================"
echo ""

# ---------- 1. Leaderboard ----------
echo "[LEADERBOARD]"
BOARD=$(.venv/bin/kaggle competitions leaderboard "$COMP" -s 2>&1) || BOARD="(fetch failed)"
if echo "$BOARD" | grep -qi "error\|not found\|fetch failed"; then
    echo "  (leaderboard unavailable)"
else
    MYLINE=$(echo "$BOARD" | grep -i "$MY_TEAM" || true)
    if [ -n "$MYLINE" ]; then
        ROWNUM=$(echo "$BOARD" | grep -in "$MY_TEAM" | head -1 | cut -d: -f1)
        # Subtract 2: 1 for header, 1 for separator line (kaggle prints ----)
        POS=$((ROWNUM - 2))
        [ "$POS" -lt 1 ] && POS=$((ROWNUM - 1))
        echo "  Position : #$POS"
        echo "  Entry    : $(echo "$MYLINE" | xargs)"
    else
        echo "  '$MY_TEAM' not found yet"
        echo "  Top entries:"
        echo "$BOARD" | head -5 | sed 's/^/    /'
    fi
fi
echo ""

# ---------- 2. Latest submission ----------
echo "[LATEST SUBMISSION]"
read CUR_SCORE CUR_STATUS CUR_DATE < <(.venv/bin/python3 - <<'PYEOF'
import sys
sys.path.insert(0, '.')
try:
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    subs = api.competition_submissions("orbit-wars")
    if not subs:
        print("? ? ?")
        sys.exit(0)
    s = subs[0]
    score  = getattr(s, '_public_score',  None) or getattr(s, 'publicScore',  '?')
    status = getattr(s, '_status',        None) or getattr(s, 'status',       '?')
    ref    = getattr(s, '_ref',           None) or getattr(s, 'ref',          '?')
    date_  = getattr(s, '_date',          None) or getattr(s, 'date',         '?')
    status_str = str(status).replace('SubmissionStatus.','').replace('submissionstatus.','')
    print(f"{score} {status_str} {date_}")
except Exception as e:
    print(f"? error ?")
PYEOF
)
echo "  Score: $CUR_SCORE  |  Status: $CUR_STATUS  |  Date: $CUR_DATE"
echo ""

# ---------- 3. Rating delta ----------
echo "[RATING DELTA (24h)]"
if [ -f "$SCORE_FILE" ]; then
    LAST_SCORE=$(cat "$SCORE_FILE" | tr -d '[:space:]')
    if [[ "$CUR_SCORE" =~ ^[0-9] ]] && [[ "$LAST_SCORE" =~ ^[0-9] ]]; then
        DELTA=$(.venv/bin/python3 -c "d=$CUR_SCORE-$LAST_SCORE; print(f'{d:+.1f}')" 2>/dev/null || echo "?")
        echo "  Current: $CUR_SCORE  |  Previous: $LAST_SCORE  |  Delta: $DELTA"
    else
        echo "  Scores unavailable for delta"
    fi
else
    echo "  No .last_score file — first run, delta available tomorrow"
fi
if [[ "$CUR_SCORE" =~ ^[0-9] ]]; then echo "$CUR_SCORE" > "$SCORE_FILE"; fi
echo ""

# ---------- 4. Failed submissions ----------
echo "[FAILED SUBMISSIONS]"
.venv/bin/python3 - <<'PYEOF'
import sys
sys.path.insert(0, '.')
try:
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    subs = api.competition_submissions("orbit-wars")
    failed = [s for s in subs if 'fail' in str(getattr(s, '_status', '')).lower() or 'error' in str(getattr(s, '_status', '')).lower()]
    if failed:
        for s in failed[:5]:
            ref   = getattr(s, '_ref',  '?')
            date_ = getattr(s, '_date', '?')
            print(f"  ref={ref}  date={date_}  FAILED")
    else:
        print("  None")
except Exception as e:
    print(f"  Error: {e}")
PYEOF
echo ""

# ---------- 5. Episode count ----------
echo "[EPISODE COUNT — latest submission]"
.venv/bin/python3 - <<'PYEOF'
import sys
sys.path.insert(0, '.')
try:
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    subs = api.competition_submissions("orbit-wars")
    if not subs:
        print("  No submissions")
        sys.exit(0)
    sub = subs[0]
    sub_id = sub._ref
    episodes = api.competition_list_episodes(sub_id)
    n = len(episodes)
    if not n:
        print(f"  Sub {sub_id}: no episodes yet")
        sys.exit(0)
    wins = losses = draws = 0
    for ep in episodes:
        for ag in ep._agents:
            if getattr(ag, '_submission_id', None) == sub_id:
                r = getattr(ag, '_reward', None)
                if r == 1:
                    wins += 1
                elif r == -1:
                    losses += 1
                else:
                    draws += 1
    print(f"  Sub {sub_id}: {n} episodes  W/L/D: {wins}/{losses}/{draws}")
except Exception as e:
    print(f"  Error: {e}")
PYEOF

echo ""
echo "========================================"
