"""
Orbit Wars — Agent v11
======================
Base: v10 (v2 + compute_send overshoot)
Change: replace accumulation-biased send logic with fire-every-turn logic.
  - should_launch: launch if we can capture it, period. No buffer, no waiting.
  - compute_send: early game = needed+3 (minimal), late = max(needed, 40% avail)
Motivated by loss analysis: opponents fire every 1-2 turns vs my every 3-5.
All 5 sampled losses were 4-player games; expansion rate > fleet size.
"""

import math
from kaggle_environments.envs.orbit_wars.orbit_wars import Planet, Fleet

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CENTER_X, CENTER_Y = 50.0, 50.0
SUN_RADIUS         = 10.0
BOARD_SIZE         = 100.0
MAX_SPEED          = 6.0
GARRISON_FRAC      = 0.20
MIN_SHIPS_TO_SEND  = 3
GAME_LENGTH        = 500

# ---------------------------------------------------------------------------
# Physics helpers
# ---------------------------------------------------------------------------

def fleet_speed(num_ships: int) -> float:
    if num_ships <= 1:
        return 1.0
    return 1.0 + (MAX_SPEED - 1.0) * (math.log(num_ships) / math.log(1000)) ** 1.5


def travel_time(sx, sy, dx, dy, n: int) -> float:
    return math.hypot(dx - sx, dy - sy) / fleet_speed(n)


def path_hits_sun(x1, y1, x2, y2, margin: float = 1.5) -> bool:
    danger = SUN_RADIUS + margin
    dx, dy = x2 - x1, y2 - y1
    fx, fy = x1 - CENTER_X, y1 - CENTER_Y
    a = dx*dx + dy*dy
    if a < 1e-9:
        return math.hypot(fx, fy) < danger
    t = -(fx*dx + fy*dy) / a
    t = max(0.0, min(1.0, t))
    return math.hypot(fx + t*dx, fy + t*dy) < danger


def safe_angle(sx, sy, dx, dy) -> float:
    direct = math.atan2(dy - sy, dx - sx)
    if not path_hits_sun(sx, sy, dx, dy):
        return direct
    dist = math.hypot(dx - sx, dy - sy)
    for deg in range(5, 91, 5):
        for sign in (1, -1):
            angle = direct + sign * math.radians(deg)
            wx = max(2.0, min(BOARD_SIZE - 2.0, sx + math.cos(angle) * dist * 0.6))
            wy = max(2.0, min(BOARD_SIZE - 2.0, sy + math.sin(angle) * dist * 0.6))
            if not path_hits_sun(sx, sy, wx, wy) and not path_hits_sun(wx, wy, dx, dy):
                return angle
    return direct

# ---------------------------------------------------------------------------
# Aim-ahead for orbiting planets
# ---------------------------------------------------------------------------

def predict_planet_pos(planet: Planet, turns: float, ang_vel: float):
    cx, cy = CENTER_X, CENTER_Y
    dx, dy = planet.x - cx, planet.y - cy
    orb_r = math.hypot(dx, dy)
    if orb_r + planet.radius >= 50.0:
        return planet.x, planet.y
    future = math.atan2(dy, dx) + ang_vel * turns
    return cx + orb_r * math.cos(future), cy + orb_r * math.sin(future)


def aim_ahead(src: Planet, tgt: Planet, n: int, ang_vel: float) -> tuple:
    ex, ey = tgt.x, tgt.y
    for _ in range(8):
        t = math.hypot(ex - src.x, ey - src.y) / fleet_speed(n)
        ex, ey = predict_planet_pos(tgt, t, ang_vel)
    return safe_angle(src.x, src.y, ex, ey), ex, ey

# ---------------------------------------------------------------------------
# Combat math
# ---------------------------------------------------------------------------

def ships_to_capture(src: Planet, tgt: Planet, committed_already: int = 0) -> int:
    est = max(tgt.ships + 1, MIN_SHIPS_TO_SEND)
    t = travel_time(src.x, src.y, tgt.x, tgt.y, est)
    garrison = tgt.ships + (tgt.production * t if tgt.owner >= 0 else 0)
    return max(int(garrison) - committed_already + 1, MIN_SHIPS_TO_SEND)

# ---------------------------------------------------------------------------
# Target scoring
# ---------------------------------------------------------------------------

def score_target(src: Planet, tgt: Planet, turn: int, committed: int) -> float:
    needed = ships_to_capture(src, tgt, committed)
    t = travel_time(src.x, src.y, tgt.x, tgt.y, needed)
    turns_left = max(0.0, GAME_LENGTH - turn - t)

    value = tgt.production * turns_left
    if tgt.owner == -1:
        value *= 1.4

    dist = math.hypot(tgt.x - src.x, tgt.y - src.y)
    return value / (needed + dist * 0.5 + 1.0)

# ---------------------------------------------------------------------------
# Threat detection
# ---------------------------------------------------------------------------

def incoming_enemy_ships(planet: Planet, fleets: list, player: int) -> int:
    total = 0
    for f in fleets:
        if f.owner == player or f.owner == -1:
            continue
        dx = planet.x - f.x
        dy = planet.y - f.y
        dist = math.hypot(dx, dy)
        if dist < 1e-3:
            continue
        dot = (dx/dist)*math.cos(f.angle) + (dy/dist)*math.sin(f.angle)
        if dot > 0.85:
            total += f.ships
    return total

# ---------------------------------------------------------------------------
# Launch gate: fire if capturable, no waiting for comfort margin
# ---------------------------------------------------------------------------

def should_launch(step, available, target):
    if available < target.ships + 1:
        return False  # can't overcome current garrison, skip
    return True       # capturable — fire immediately

# ---------------------------------------------------------------------------
# Fleet size: minimal overshoot to keep ships available for next-turn launches
# ---------------------------------------------------------------------------

def compute_send(available: int, needed: int, step: int) -> int:
    if step < 120:
        return min(available, needed + 3)
    else:
        return min(available, max(needed, int(available * 0.4)))

# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

def agent(obs):
    moves = []

    if isinstance(obs, dict):
        player      = obs.get("player", 0)
        raw_planets = obs.get("planets", [])
        raw_fleets  = obs.get("fleets", [])
        ang_vel     = obs.get("angular_velocity", 0.03)
        comet_ids   = set(obs.get("comet_planet_ids", []))
        turn        = obs.get("step", 0)
    else:
        player      = obs.player
        raw_planets = obs.planets
        raw_fleets  = obs.fleets
        ang_vel     = obs.angular_velocity
        comet_ids   = set(getattr(obs, "comet_planet_ids", []))
        turn        = getattr(obs, "step", 0)

    planets = [Planet(*p) for p in raw_planets]
    fleets  = [Fleet(*f)  for f in raw_fleets]

    my_planets = [p for p in planets if p.owner == player]
    targets    = [p for p in planets if p.owner != player]

    if not targets or not my_planets:
        return moves

    committed = {}
    for f in fleets:
        if f.owner != player:
            continue
        for p in targets:
            dx, dy = p.x - f.x, p.y - f.y
            dist = math.hypot(dx, dy)
            if dist < 1e-3:
                continue
            if (dx/dist)*math.cos(f.angle) + (dy/dist)*math.sin(f.angle) > 0.9:
                committed[p.id] = committed.get(p.id, 0) + f.ships

    live_committed = dict(committed)

    for mine in my_planets:
        threat = incoming_enemy_ships(mine, fleets, player)
        garrison_needed = max(int(mine.ships * GARRISON_FRAC), threat + 5, MIN_SHIPS_TO_SEND)
        available = mine.ships - garrison_needed

        if available < MIN_SHIPS_TO_SEND:
            continue

        scored = []
        for tgt in targets:
            if tgt.id in comet_ids:
                continue
            already = live_committed.get(tgt.id, 0)
            if not should_launch(turn, available, tgt):
                continue
            needed = ships_to_capture(mine, tgt, already)
            if needed > available:
                continue
            s = score_target(mine, tgt, turn, already)
            scored.append((s, tgt, needed))

        if not scored:
            candidates = [p for p in my_planets if p.id != mine.id]
            if candidates:
                at_risk = min(
                    candidates,
                    key=lambda p: p.ships - incoming_enemy_ships(p, fleets, player)
                )
                send = available // 2
                if send >= MIN_SHIPS_TO_SEND:
                    angle = safe_angle(mine.x, mine.y, at_risk.x, at_risk.y)
                    moves.append([mine.id, angle, send])
            continue

        scored.sort(key=lambda x: -x[0])
        _, best, needed = scored[0]
        send = compute_send(available, needed, turn)
        angle, _, _ = aim_ahead(mine, best, send, ang_vel)
        moves.append([mine.id, angle, send])
        live_committed[best.id] = live_committed.get(best.id, 0) + send

    return moves
