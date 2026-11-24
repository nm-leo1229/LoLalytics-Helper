"""통계 분석 탭의 계산(banpick_stats) 검증: 손으로 답을 알 수 있는 작은 데이터로 확인한다 (창을 띄우지 않는다)."""
from banpick_stats import lane_plan, table_inflations, worst_matchups


def entry(win, games=100_000):
    return {"win_rate": f"{win:.2f}", "games": f"{games:,}"}


def test_solo_lane_plan_removes_inflation_and_bans_the_counter():
    # strong 은 counter 에게만 지고(40%) 나머지를 이긴다(56%). 파일의 승률은 모두 2.5 씩 부풀려 넣는다.
    truth = {("strong", "counter"): 40, ("strong", "other1"): 56, ("strong", "other2"): 56, ("strong", "other3"): 56,
             ("counter", "other1"): 44, ("counter", "other2"): 44, ("counter", "other3"): 44,
             ("other1", "other2"): 50, ("other1", "other3"): 50, ("other2", "other3"): 50}
    truth.update({(b, a): 100 - win for (a, b), win in list(truth.items())})
    names = sorted({a for a, _ in truth})
    data = {(a, "top"): {"counters": {"top": {b.title(): entry(truth[a, b] + 2.5) for b in names if b != a}}} for a in names}

    plan = lane_plan(data, "top")

    assert plan["first"] == "strong"
    assert plan["ban"] == "counter"  # 선픽이 가장 불리한 상대
    # 선픽 점수: counter 를 밴하고 남은 상대 중 최저 승률 56. 부풀린 2.5 는 빠져야 한다
    assert plan["pick"]["strong"][2] == "counter" and abs(plan["pick"]["strong"][0] - 56.0) < 0.2
    assert lane_plan(data, "top", ignored={"other1"})["second"] != "other1"
    assert abs(table_inflations(data)["counters", "top", "top"] - 2.5) < 1e-9
    assert worst_matchups(data, "top") == plan["pick"]  # 선픽 카드 탭과 통계 분석 탭은 같은 점수를 쓴다
    # 형식이 틀어진 파일·칸은 건너뛰고 나머지로 같은 결과를 낸다
    broken = {**data, ("list", "top"): [], ("note",): {}, ("other3", "top"): {"counters": {"top": {**data["other3", "top"]["counters"]["top"], "Bad": "N/A"}}}}
    assert lane_plan(broken, "top")["first"] == "strong" and table_inflations(broken) == table_inflations(data)
    # 종류별 선픽: AP 목록에 있는 챔피언 중 1위와 없는 챔피언 중 1위 (밴할 챔피언은 건너뛴다)
    assert lane_plan(data, "top", ap={"strong"})["by_damage"][0][1] != "counter"
    assert lane_plan(data, "top", ap={"counter", "other2"})["by_damage"] == [("AD", "strong"), ("AP", "other2")]


def test_duo_lane_plan_undoes_partner_skew():
    # paired 는 good 서포터와 90% 를 함께해서 맞라인 승률이 높아 보일 뿐이고, 평균적인 서포터 분포에서는 solid 가 더 낫다.
    fillers = ["filler1", "filler2", "filler3"]
    with_support = {"paired": {"good": (60, 90_000), "plain": (48, 10_000)},
                    "solid": {"good": (56, 50_000), "plain": (56, 50_000)},
                    **{filler: {"good": (50, 50_000), "plain": (50, 50_000)} for filler in fillers}}
    versus = {("paired", "solid"): 51, **{(adc, filler): 56 for adc in ("paired", "solid") for filler in fillers},
              **{(a, b): 50 for a in fillers for b in fillers if a < b}}
    versus.update({(b, a): 100 - win for (a, b), win in list(versus.items())})
    data = {}
    for adc, partners in with_support.items():
        data[adc, "bottom"] = {
            "counters": {"bottom": {b.title(): entry(win) for (a, b), win in versus.items() if a == adc},
                         "support": {support.title(): entry(50) for support in partners}},
            "synergy": {"support": {support.title(): entry(*stat) for support, stat in partners.items()}}}
    for support, other in (("good", "plain"), ("plain", "good")):
        data[support, "support"] = {
            "counters": {"support": {other.title(): entry(50)}, "bottom": {adc.title(): entry(50) for adc in with_support}},
            "synergy": {"bottom": {adc.title(): entry(*partners[support]) for adc, partners in with_support.items()}}}

    plan = lane_plan(data, "bottom")

    assert plan["first"] == "solid"  # 선픽 점수 56: paired 를 밴하고 남은 상대(filler) 에게 56
    # paired: solid 를 밴하고 남은 상대에게 56, 여기에 서포터 분포를 반반으로 되돌린 차이 (60 + 48) / 2 - (60 * 0.9 + 48 * 0.1) = -4.8 을 더한다
    assert abs(plan["pick"]["paired"][0] - 51.2) < 0.3
