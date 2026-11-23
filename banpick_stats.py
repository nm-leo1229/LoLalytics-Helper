"""통계만으로 라인별 밴픽 설계(선픽·대안·후픽·밴)를 계산한다. `python banpick_stats.py` 로 바로 볼 수 있다.

수집한 승률은 마스터 이상 필터 때문에 양쪽 합이 100% 가 아니라 약 105% 다. 그래서 두 챔피언의 파일을 함께 써서 부풀림을 빼고,
표본이 적은 칸은 평균 쪽으로 당긴 승률로 계산한다 (앱의 다른 화면에 보이는 원본 승률보다 약 2.5%p 낮다).
"""
import itertools
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from common import LANES, resolve_resource_path

DUO_PARTNER = {"bottom": "support", "support": "bottom"}  # 2대2 라인은 상대 짝과의 상성, 아군 짝과의 시너지도 본다
MIN_CANDIDATE_SHARE = 0.010  # 후보: 그 라인 픽 점유율이 이 이상인 챔피언 (추천 제외 목록은 뺀다)
MIN_OPPONENT_SHARE = 0.015  # 상대·짝: 그 라인 픽 점유율이 이 이상인 챔피언만 본다 
SAMPLE_OVERLAP = 0.6  # 같은 대결을 두 파일이 약 65% 겹쳐 세므로, 두 파일의 게임 수 합에 이만큼만 곱해 표본으로 본다
EFFECT_VARIANCE = 2.0  # 챔피언 자체 강함의 사전 분산(%p²): 표본이 아주 적은 챔피언의 평균을 50% 쪽으로 당긴다
FIRST_PICK_GONE = 0.2  # 선픽이 밴되거나 뺏기는 판의 비율 (밴률 데이터가 없어 둔 가정)
CARD_COST = 0.05  # 후픽 카드 하나는 전체 승률을 이만큼(%p) 올려야 넣는다
MAX_CARDS = 3
OTHERS = ""  # 점유율이 낮아 하나로 묶은 '그 밖의 챔피언' 칸


def load_data(data_dir):
    """{(챔피언, 라인): 파일 내용}"""
    return {tuple(path.stem.rsplit("_", 1)): json.loads(path.read_text(encoding="utf-8")) for path in Path(data_dir).glob("*_*.json")}


def _number(text):
    try:
        return float(str(text).replace(",", ""))
    except ValueError:
        return None


def _key(name):
    """데이터 안의 표시 이름을 파일 이름으로 바꾼다 (scraper.normalize_champion_name 과 같은 규칙. scraper 는 빌드에서 빠져 있어 가져다 쓸 수 없다)."""
    lowered = name.lower().strip()
    return {"nunu & willump": "nunu", "renata glasc": "renata"}.get(lowered) or lowered.replace("'", "").replace(".", "").replace(" ", "")


def _table(data, lane, kind, other):
    """{챔피언: {상대나 짝: (승률, 게임 수)}}: lane 파일들의 kind("counters"/"synergy") 안 other 라인 칸"""
    table = {}
    for (champion, file_lane), content in data.items():
        if file_lane != lane:
            continue
        table[champion] = row = {}
        for name, entry in content.get(kind, {}).get(other, {}).items():
            win, games = _number(entry.get("win_rate")), _number(entry.get("games"))
            if win is not None and games:
                row[_key(name)] = (win, games)
    return table


def _shares(table):
    """{챔피언: 그 라인 픽 점유율}. table 은 같은 라인 상대 표"""
    games = {champion: sum(n for _, n in row.values()) for champion, row in table.items()}
    total = sum(games.values())
    return {champion: n / total for champion, n in games.items()}


def _inflation(mine, theirs):
    """한 표의 승률에 얹힌 평균 부풀림: 같은 대결을 양쪽에서 본 두 승률의 합이 100 을 넘는 만큼의 절반"""
    both = [(win + theirs[x][a][0], games + theirs[x][a][1])
            for a, row in mine.items() for x, (win, games) in row.items() if a in theirs.get(x, {})]
    total = sum(games for _, games in both)
    return (sum(wins * games for wins, games in both) / total - 100) / 2 if total else 0.0


def table_inflations(data):
    """{(kind, 파일의 라인, 칸의 라인): 평균 부풀림}: 앱이 화면과 점수에 쓰는 승률에서 뺄 값"""
    tables = {(kind, lane, other): _table(data, lane, kind, other)
              for kind in ("counters", "synergy") for lane in LANES for other in LANES}
    return {(kind, lane, other): _inflation(table, tables[kind, other, lane]) for (kind, lane, other), table in tables.items()}


def worst_matchups(data, lane):
    """{챔피언: (가장 불리한 상대에게 거두는 승률, 그 상대)}: 선픽 카드 판정에 쓴다. 챔피언·상대의 범위는 통계 분석과 같다."""
    same = _table(data, lane, "counters", lane)
    share = _shares(same)
    versus = _shrunk(_corrected(same, same, False))
    popular = [b for b in share if share[b] >= MIN_OPPONENT_SHARE]
    return {a: min((versus(a, b), b) for b in popular if b != a) for a in share if share[a] >= MIN_CANDIDATE_SHARE}


def _corrected(mine, theirs, same_team):
    """{(챔피언, 상대나 짝): (부풀림을 뺀 승률 - 50, 유효 게임 수)}. mine[a][x] 와 theirs[x][a] 는 같은 대결을 양쪽에서 본 값이다.

    상대끼리는 두 승률의 차이로 보면 부풀림이 지워지고, 같은 편끼리는 둘 다 부풀어 있어 평균 부풀림을 뺀다."""
    inflation = _inflation(mine, theirs)
    cells = {}
    for a, x, win, games, other in ((a, x, win, games, theirs.get(x, {}).get(a)) for a, row in mine.items() for x, (win, games) in row.items()):
        if not other:
            cells[a, x] = (win - 50 - inflation, games)
        elif same_team:
            cells[a, x] = ((win + other[0]) / 2 - 50 - inflation, SAMPLE_OVERLAP * (games + other[1]))
        else:
            cells[a, x] = ((win - other[0]) / 2, SAMPLE_OVERLAP * (games + other[1]))
    return cells


def _shrunk(cells):
    """win(행, 열): 칸을 '행 챔피언의 강함 + 열 챔피언의 강함 + 둘만의 상성'으로 나누고, 상성을 표본 오차만큼 0 쪽으로 당긴 승률."""
    rows, cols = defaultdict(list), defaultdict(list)
    for (row, col), (value, games) in cells.items():
        rows[row].append((col, value, 2500 / games))  # 2500/n: 승률 50% 근처에서 한 칸의 표본 분산(%p²)
        cols[col].append((row, value, 2500 / games))
    row_effect, col_effect = dict.fromkeys(rows, 0.0), dict.fromkeys(cols, 0.0)
    matchup_variance = 1.0  # 둘만의 상성이 흩어진 정도(%p²). 아래에서 데이터로 잰다
    for _ in range(8):
        for effect, other, groups in ((row_effect, col_effect, rows), (col_effect, row_effect, cols)) * 5:
            for key, items in groups.items():
                weights = [1 / (noise + matchup_variance) for _, _, noise in items]
                effect[key] = (sum(weight * (value - other[partner]) for weight, (partner, value, _) in zip(weights, items))
                               / (sum(weights) + 1 / EFFECT_VARIANCE))
        excess = [((value - row_effect[row] - col_effect[col]) ** 2 - 2500 / games, (2500 / games + matchup_variance) ** -2)
                  for (row, col), (value, games) in cells.items()]
        matchup_variance = max(sum(gap * weight for gap, weight in excess) / sum(weight for _, weight in excess), 1e-6)

    def win(row, col):
        expected = row_effect.get(row, 0.0) + col_effect.get(col, 0.0)
        value, games = cells.get((row, col), (expected, 1))
        return 50 + expected + (value - expected) * matchup_variance / (matchup_variance + 2500 / games)
    return win


def _counter_pick_tilt(table, share, win):
    """상대가 내 픽을 보고 카운터를 골라 오는 정도. 상성이 벌어진 조합이 기대보다 얼마나 자주 나오는지로 잰다 (쏠림이 없으면 0)."""
    total = sum(games for row in table.values() for _, games in row.values())
    points = [((win(a, b) - 50) ** 2, math.log(games / total / (share[a] * share[b])))
              for a, row in table.items() for b, (_, games) in row.items()
              if a < b and min(share[a], share.get(b, 0.0)) >= MIN_OPPONENT_SHARE]
    if len({gap for gap, _ in points}) < 2:  # 조합이 없거나 상성 격차가 모두 같으면 잴 수 없다
        return 0.0
    return math.sqrt(2 * max(statistics.linear_regression(*zip(*points)).slope, 0.0))


def _state_chances(enemy_flags):
    """{(자리마다 이미 골랐는지): 확률}. 내가 고르는 순간 다른 자리(상대/아군)가 보이는지를 픽 순서 1-2-2-2-2-1 과 무작위 자리로 센다."""
    blue, red = (1, 4, 5, 8, 9), (2, 3, 6, 7, 10)
    counts = Counter()
    for mine, theirs in ((blue, red), (red, blue)):
        for me, *allies in itertools.permutations(mine, 1 + enemy_flags.count(False)):
            for enemies in itertools.permutations(theirs, enemy_flags.count(True)):
                turns = {True: iter(enemies), False: iter(allies)}
                counts[tuple(next(turns[enemy]) < me for enemy in enemy_flags)] += 1
    return {state: count / sum(counts.values()) for state, count in counts.items()}


def _mean(values, weights):
    return sum(values[key] * weight for key, weight in weights.items()) / sum(weights.values())


class _Lane:
    """한 라인의 계산. 요인 = 내가 고를 때 이미 보일 수도 있는 다른 자리: (상대인지, 라인, {챔피언: 점유율}, {후보: {챔피언: 승률 기여}})"""

    def __init__(self, data, lane, ignored):
        same = _table(data, lane, "counters", lane)
        self.share = _shares(same)
        versus = _shrunk(_corrected(same, same, False))
        self.tilt = _counter_pick_tilt(same, self.share, versus)
        self.candidates = sorted(a for a in same if a not in ignored and self.share[a] >= MIN_CANDIDATE_SHARE)
        self.factors = [self._factor(True, lane, self.share, {a: {b: versus(a, b) for b in same} for a in self.candidates})]
        # 챔피언마다 자주 만나는 짝·상대가 다르다 (자야는 라칸, 제리는 유미). 평균적인 분포로 되돌렸을 때의 승률 변화를 더해 둔다.
        self.base = dict.fromkeys(self.candidates, 0.0)
        partner = DUO_PARTNER.get(lane)
        if partner:
            partner_share = _shares(_table(data, partner, "counters", partner))
            for enemy, kind in ((True, "counters"), (False, "synergy")):
                mine = _table(data, lane, kind, partner)
                win = _shrunk(_corrected(mine, _table(data, partner, kind, lane), not enemy))
                gaps = {}
                for a in self.candidates:
                    wins = {x: win(a, x) for x in partner_share}
                    usual = _mean(wins, partner_share)
                    met = {x: mine[a][x][1] for x in partner_share if x in mine[a]}  # a 가 실제로 만난 분포
                    self.base[a] += usual - _mean(wins, met or partner_share)
                    gaps[a] = {x: value - usual for x, value in wins.items()}
                self.factors.append(self._factor(enemy, partner, partner_share, gaps))
        self.states = _state_chances([factor[0] for factor in self.factors])
        # 상태(무엇이 보이는지)마다 가능한 문맥(보이는 챔피언의 조합)과, 그 문맥에서 후보가 얻는 승률 기여
        self.contexts, self.scores = {}, {}
        for state in self.states:
            known = [factor for factor, seen in zip(self.factors, state) if seen]
            self.contexts[state] = contexts = list(itertools.product(*(factor[2] for factor in known)))
            self.scores[state] = {
                a: [-math.inf if state[0] and context[0] == a  # 상대가 먼저 가져간 챔피언은 못 고른다
                    else sum(factor[3][a][x] for factor, x in zip(known, context)) for context in contexts]
                for a in self.candidates}

    @staticmethod
    def _factor(enemy, lane, share, terms):
        """요인 하나. 점유율이 낮은 챔피언은 OTHERS 한 칸으로 묶어, 보이는 조합의 수를 줄이면서 평균은 그대로 둔다."""
        shown = {x: part for x, part in share.items() if part >= MIN_OPPONENT_SHARE}
        rest = {x: part for x, part in share.items() if x not in shown}
        grouped = {}
        for a, row in terms.items():
            grouped[a] = {x: row[x] for x in shown}
            if rest:
                grouped[a][OTHERS] = _mean(row, {x: part for x, part in rest.items() if x != a} or rest)
        return enemy, lane, dict(shown, **({OTHERS: sum(rest.values())} if rest else {})), grouped

    def _world(self, banned):
        """밴을 반영해 상태마다 (문맥별 확률, {후보: 안 보이는 자리의 기대 기여 합})"""
        weights = []
        for _, _, champions, _ in self.factors:
            left = {x: share for x, share in champions.items() if x not in banned}
            total = sum(left.values())
            weights.append({x: share / total for x, share in left.items()})
        hidden = [{a: self._hidden(index, a, weights[index]) for a in self.candidates} for index in range(len(self.factors))]
        world = {}
        for state, chance in self.states.items():
            seen = [weight for weight, known in zip(weights, state) if known]
            odds = [chance * math.prod(weight.get(x, 0.0) for weight, x in zip(seen, context)) for context in self.contexts[state]]
            offsets = {a: self.base[a] + sum(h[a] for h, known in zip(hidden, state) if not known)
                       for a in self.candidates if a not in banned}
            world[state] = (odds, offsets)
        return world

    def _hidden(self, index, a, weights):
        """아직 안 보이는 자리의 기대 기여. 같은 라인 상대는 내 픽을 보고 고르므로 나를 잘 잡는 쪽으로 쏠린다."""
        terms = self.factors[index][3][a]
        if index == 0:
            weights = {b: weight * math.exp(-self.tilt * (terms[b] - 50)) for b, weight in weights.items() if b != a}
        return _mean(terms, weights)

    def _best(self, world, pool):
        """상태·문맥마다 풀이 낼 수 있는 최고 승률. 풀이 전부 막히면(상대가 먼저 가져감) 평범한 픽 50% 로 본다."""
        best = {}
        for state, (_, offsets) in world.items():
            rows = [[offsets[a] + score for score in self.scores[state][a]] for a in pool]
            best[state] = [top if top > -math.inf else 50.0 for top in map(max, zip(*rows))]
        return best

    def _blind(self, world, a):
        """상대 쪽이 아무도 안 보일 때 a 를 고르는 승률 (아군 짝은 픽 순서에 따라 보이기도 한다)"""
        total = chance = 0.0
        for state, (odds, offsets) in world.items():
            if not any(seen and factor[0] for seen, factor in zip(state, self.factors)):
                total += sum(odd * (offsets[a] + score) for odd, score in zip(odds, self.scores[state][a]))
                chance += sum(odds)
        return total / chance

    def plan(self, first, ban=None, cards=None):
        """first 를 선픽으로 둔 설계. cards 를 주면 후픽 카드를 새로 고르지 않고 그대로 쓴다 (밴 후보끼리 비교할 때)."""
        banned = {ban} - {None}
        # 선픽을 쓸 수 있는 판과, 선픽이 밴되거나 뺏겨 대안으로 가는 판
        worlds = [(1 - FIRST_PICK_GONE, self._world(banned)), (FIRST_PICK_GONE, self._world(banned | {first}))]
        second = max((a for a in self.candidates if a not in banned | {first}), key=lambda a: self._blind(worlds[1][1], a))
        bests = [self._best(worlds[0][1], [first, second]), self._best(worlds[1][1], [second])]

        def gain(card):
            return sum(weight * odd * (offsets[card] + score - top)
                       for (weight, world), best in zip(worlds, bests)
                       for state, (odds, offsets) in world.items()
                       for odd, score, top in zip(odds, self.scores[state][card], best[state]) if offsets[card] + score > top)

        picked = []
        for _ in range(MAX_CARDS):
            rest = [a for a in (self.candidates if cards is None else cards)
                    if a not in banned | {first, second} and a not in dict(picked)]
            if not rest:
                break
            value, card = max((gain(a), a) for a in rest)
            if cards is None and value < CARD_COST:
                break
            picked.append((card, value))
            for (_, world), best in zip(worlds, bests):
                for state, (_, offsets) in world.items():
                    best[state] = [max(pair) for pair in zip(best[state], (offsets[card] + score for score in self.scores[state][card]))]
        value = sum(weight * odd * top for (weight, world), best in zip(worlds, bests)
                    for state, (odds, _) in world.items() for odd, top in zip(odds, best[state]))
        return {"first": first, "second": second, "ban": ban, "cards": picked,
                "score": value - CARD_COST * len(picked),  # 카드 수가 다른 설계끼리 견줄 때 쓰는 값
                "uses": self._uses(worlds[0][1], [first, second] + [card for card, _ in picked])}

    def _uses(self, world, pool):
        """{선픽이 아닌 풀 챔피언: [(상대인지, 라인, 보인 챔피언, 그때 승률)]}: 한 자리만 보일 때 선픽 대신 꺼내는 경우 (자주·크게 이득인 순으로 셋)"""
        found = defaultdict(list)
        for state, (odds, offsets) in world.items():
            if sum(state) != 1:
                continue
            enemy, lane, _, _ = self.factors[state.index(True)]
            for (x,), odd, values in zip(self.contexts[state], odds, zip(*(self.scores[state][a] for a in pool))):
                values = [offsets[a] + value for a, value in zip(pool, values)]
                top = max(values)
                if x != OTHERS and odd and top > values[0]:
                    found[pool[values.index(top)]].append((odd * (top - values[0]), (enemy, lane, x, top)))
        return {a: [use for _, use in sorted(uses, reverse=True)[:3]] for a, uses in found.items()}

    def solve(self):
        world = self._world(set())
        ranking = sorted(((self._blind(world, a), a) for a in self.candidates), reverse=True)
        first = ranking[0][1]
        cards = [card for card, _ in self.plan(first)["cards"]]
        bans = sorted({x for _, _, champions, _ in self.factors for x in champions} - {first, OTHERS})
        ban = max(bans, key=lambda x: self.plan(first, x, cards)["score"])
        versus = self.factors[0][3][first]
        worst = min((b for b in versus if b not in (OTHERS, ban, first)), key=versus.get)
        return {**self.plan(first, ban), "blind": {a: blind for blind, a in ranking}, "worst": (worst, versus[worst]),
                "ranking": [(a, blind, self.share[a]) for blind, a in ranking[:5]]}


def lane_plan(data, lane, ignored=(), ap=()):
    """한 라인의 설계: 선픽 first(가장 불리한 상대 worst), 대안 second, 밴 ban, 후픽 cards[(챔피언, 올리는 승률)], 꺼낼 때 uses, 선픽 순위 ranking.

    딜러 라인은 by_damage[("AD", 챔피언), ("AP", 챔피언)] 도 준다: 아군 조합이 한쪽으로 쏠릴 때 고를 종류별 선픽 1위. ap 는 AP 딜러 이름들."""
    plan = _Lane(data, lane, set(ignored)).solve()
    if lane != "support":  # 딜러 라인은 팀의 AD·AP 균형을 맞춰 골라야 한다
        # ponytail: AP 딜러 목록에 없으면 AD 로 본다 (탱커도 AD 쪽에 낀다). AD 딜러 목록이 생기면 그것으로 가른다
        plan["by_damage"] = [(label, next((a for a in plan["blind"] if (a in ap) == is_ap), None))  # blind 는 승률이 높은 순
                             for label, is_ap in (("AD", False), ("AP", True))]
    return plan


def plan_rows(plan, lane_names, name=str):
    """설계를 화면에 한 줄씩 보여줄 글로 바꾼다. lane_names 는 {라인: 표시 이름}, name 은 챔피언 표시 이름 함수"""
    rows = [f"선픽  {name(plan['first'])}  {plan['blind'][plan['first']]:.1f}",
            f"  불리한 상대 {name(plan['worst'][0])}  {plan['worst'][1]:.1f}",
            f"대안  {name(plan['second'])}  {plan['blind'][plan['second']]:.1f}",
            f"밴  {name(plan['ban'])}"]
    rows += [f"{label} 선픽  {name(champion)}  {plan['blind'][champion]:.1f}" for label, champion in plan.get("by_damage", []) if champion]
    gains = dict(plan["cards"])
    for champion in [plan["second"]] + list(gains):
        uses = plan["uses"].get(champion)
        if champion in gains:
            rows += ["", f"후픽  {name(champion)}  +{gains[champion]:.2f}"]
        elif uses:
            rows += ["", f"대안 {name(champion)} 도 꺼낼 때"]
        for enemy, lane, x, win in uses or []:
            rows.append(f"  {'상대' if enemy else '아군'} {lane_names[lane]} {name(x)}  {win:.1f}")
    rows += ["", "선픽 순위 (픽 점유율)"]
    rows += [f"  {name(champion)}  {blind:.1f}  ({share * 100:.1f}%)" for champion, blind, share in plan["ranking"]]
    return rows


if __name__ == "__main__":
    from weight_settings_tab import LANE_DISPLAY_NAMES

    champion_data = load_data(resolve_resource_path("data"))
    with open(resolve_resource_path("ignored_champions.json"), encoding="utf-8") as handle:
        ignored_names = json.load(handle)
    with open(resolve_resource_path("ap_champions.json"), encoding="utf-8") as handle:
        ap_names = {_key(ap_name) for ap_name in json.load(handle)}
    for lane_name in LANES:
        print(f"[{LANE_DISPLAY_NAMES[lane_name]}]")
        print("\n".join(plan_rows(lane_plan(champion_data, lane_name, ignored_names, ap_names), LANE_DISPLAY_NAMES)), end="\n\n")
