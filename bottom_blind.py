"""라인별 선픽의 불리한 상성과 종료 시간대별 상대 성적."""

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import median


STYLE_LANES = ("top", "middle", "bottom", "support")
MIN_OPPONENT_POPULARITY = 1.5
MIN_MATCHUP_GAMES = 150
PRIOR_GAMES = 500
TAIL_SHARE = 0.20
MIN_FLOOR = 49.0
# 궁극기나 공격 대상 없이 이동기로 거리를 벌릴 수 있는 원딜과 바텀 직스.
# 이 태그는 후보 자격에만 쓰며 개별 챔피언에 점수를 주지 않는다.
MOBILE_BOTTOM = frozenset({
    "caitlyn", "corki", "ezreal", "kalista", "lucian", "smolder",
    "tristana", "vayne", "zeri", "ziggs",
})


def valid_profile(profile):
    if not isinstance(profile, dict):
        return False
    bins = profile.get("time")
    matchups = profile.get("matchups")
    if not isinstance(bins, list) or len(bins) != 7 or not isinstance(matchups, dict) or not matchups:
        return False
    for pair in bins:
        if not isinstance(pair, list) or len(pair) != 2:
            return False
        games, wins = pair
        if type(games) is not int or type(wins) is not int or not 0 <= wins <= games:
            return False
    return all(isinstance(row, dict) and type(row.get("games")) is int and row["games"] > 0
               and all(isinstance(row.get(key), (int, float)) and 0 <= row[key] <= 100
                       for key in ("win_rate", "popularity")) for row in matchups.values())


def snapshot_path(data_dir, lane):
    if lane not in STYLE_LANES:
        raise ValueError(f"Unsupported phase-analysis lane: {lane}")
    return Path(data_dir, "blind_pick", f"{lane}.json")


def load_lane_snapshot(data_dir, lane):
    try:
        with snapshot_path(data_dir, lane).open(encoding="utf-8") as handle:
            snapshot = json.load(handle)
        profiles = snapshot.get("profiles") if isinstance(snapshot, dict) else None
        if isinstance(profiles, dict) and profiles and all(map(valid_profile, profiles.values())):
            return snapshot
    except (OSError, ValueError):
        pass
    return {}


def load_bottom_snapshot(data_dir):
    return load_lane_snapshot(data_dir, "bottom")


@dataclass(frozen=True)
class LaneCard:
    champion: str
    floor: float
    early: float
    late: float

    @property
    def early_style(self):
        return self.early >= self.late


def common_opponent_weights(profiles):
    opponents = {name for profile in profiles.values() for name in profile["matchups"]}
    weights = {}
    for opponent in opponents:
        rates = [profile["matchups"].get(opponent, {}).get("popularity", 0)
                 for name, profile in profiles.items() if name != opponent]
        if rates:
            weight = median(rates)
            if weight > MIN_OPPONENT_POPULARITY:
                weights[opponent] = weight
    return weights


def weighted_matchup_floor(matchups):
    """픽률 질량의 하위 20%만 평균하며 경계에 걸친 상대는 일부만 센다."""
    tail_weight = sum(weight for _, weight in matchups) * TAIL_SHARE
    remaining = tail_weight
    total = 0.0
    for win_rate, weight in sorted(matchups):
        take = min(weight, remaining)
        total += take * win_rate
        remaining -= take
        if remaining <= 0:
            break
    return total / tail_weight


def matchup_floor(champion, profiles, weights, banned):
    matchups = []
    for opponent, weight in weights.items():
        if opponent == champion or opponent in banned:
            continue
        forward = profiles[champion]["matchups"].get(opponent)
        reverse = profiles.get(opponent, {}).get("matchups", {}).get(champion)
        if not forward or not reverse:
            return None
        games = min(forward["games"], reverse["games"])
        if games < MIN_MATCHUP_GAMES:
            return None
        # 두 Master+ 관점에 공통으로 붙은 승률 상승분을 상쇄한다.
        delta = (forward["win_rate"] - reverse["win_rate"]) / 2
        rate = 50 + delta * games / (games + PRIOR_GAMES)
        matchups.append((rate, weight))
    return weighted_matchup_floor(matchups) if matchups else None


def phase_scores(profiles):
    """5분 구간별 라인 평균을 먼저 구한다. 밴과 후보 제한은 이 기준선을 바꾸지 않는다."""
    baselines = {}
    for index in (1, 2, 4, 5):
        pairs = [profile["time"][index] for profile in profiles.values()]
        total_games = sum(games for games, _ in pairs)
        if not total_games:
            return {}
        baselines[index] = sum(wins for _, wins in pairs) / total_games

    scores = {}
    for champion, profile in profiles.items():
        bins = profile["time"]
        if any(bins[index][0] == 0 for index in baselines):
            continue
        deltas = [100 * (bins[i][1] - bins[i][0] * baseline) / (bins[i][0] + PRIOR_GAMES)
                  for i, baseline in baselines.items()]
        early = (deltas[0] + deltas[1]) / 2
        late = (deltas[2] + deltas[3]) / 2
        scores[champion] = (early, late)
    return scores


def rank_lane_cards(profiles, lane, banned=frozenset()):
    if lane not in STYLE_LANES:
        return []
    weights = common_opponent_weights(profiles)
    cards = []
    for champion, (early, late) in phase_scores(profiles).items():
        if champion in banned or (lane == "bottom" and champion not in MOBILE_BOTTOM) or max(early, late) <= 0:
            continue
        floor = matchup_floor(champion, profiles, weights, banned)
        if floor is not None and floor >= MIN_FLOOR:
            cards.append(LaneCard(champion, floor, early, late))
    return sorted(cards, key=lambda card: (not card.early_style, -max(card.early, card.late),
                                           -card.floor, card.champion))


def best_ban(champion, profiles, weights, banned=frozenset()):
    """champion 을 선픽할 때 하나 더 밴하면 불리한 상성 평균이 가장 오르는 상대와 그때의 평균. 올릴 상대가 없으면 None."""
    banned = set(banned)
    options = [(floor, opponent) for opponent in sorted(weights) if opponent != champion and opponent not in banned
               for floor in [matchup_floor(champion, profiles, weights, banned | {opponent})] if floor is not None]
    current = matchup_floor(champion, profiles, weights, banned)
    floor, opponent = max(options, default=(None, None))
    return (opponent, floor) if opponent and (current is None or floor > current) else None


def style_pick_rows(lane, profiles, banned=(), name=str):
    """라인 칸에 표시할 유형별 1순위. 기준 미달이면 해당 유형은 비워 둔다."""
    if lane not in STYLE_LANES:
        return []
    cards = rank_lane_cards(profiles, lane, banned)
    weights = common_opponent_weights(profiles)
    rows = []
    for early_style, label in ((True, "초중반형 선픽"), (False, "후반형 선픽")):
        card = next((c for c in cards if c.early_style == early_style), None)
        if card is None:
            rows.append(f"{label}  " + ("조건 충족 없음" if profiles else "시간대 자료 없음"))
            continue
        floor = f"{card.floor:.2f}%"
        if banned:
            base = matchup_floor(card.champion, profiles, weights, ())
            floor = ("표본 부족" if base is None else f"{base:.2f}%") + " → " + floor
        rows.extend([f"{label}  {name(card.champion)}",
                     f"  15–25분 {card.early:+.2f}%p · 30–40분 {card.late:+.2f}%p",
                     f"  불리한 상성 {floor}"])
        ban = best_ban(card.champion, profiles, weights, banned)
        if ban:
            rows.append(f"  추천 밴 {name(ban[0])} → 불리한 상성 {ban[1]:.2f}%")
    return rows
