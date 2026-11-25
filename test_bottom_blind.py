from types import SimpleNamespace

import pytest

from lobby_manager import ChampionScraperApp


def profile(matchups, early=550, late=550):
    # Seven bins of 1,000 games. The two early and two late bins vary independently.
    return {"time": [[1000, wins] for wins in [550, early, early, 550, late, late, 550]],
            "matchups": {name: {"win_rate": wr, "popularity": pop, "games": games}
                         for name, wr, pop, games in matchups}}


def test_cards_use_reciprocal_rates_pooled_time_baseline_and_live_bans():
    from bottom_blind import rank_lane_cards

    profiles = {
        "ezreal": profile([("zeri", 57, 50, 2000), ("draven", 43, 50, 2000)], early=610, late=490),
        "zeri": profile([("ezreal", 53, 50, 500), ("draven", 55, 50, 500)], early=490, late=610),
        "draven": profile([("ezreal", 67, 50, 2000), ("zeri", 55, 50, 500)]),
    }
    assert [card.champion for card in rank_lane_cards(profiles, "bottom")] == ["zeri"]
    early, late = rank_lane_cards(profiles, "bottom", {"draven"})
    # 57 vs 53 centers to 52. The smaller 500-game sample shrinks it halfway to 50.
    assert (early.champion, early.floor, early.early, early.late) == ("ezreal", 51, 4, -4)
    assert (late.champion, late.floor, late.early, late.late) == ("zeri", 49, -4, 4)
    assert rank_lane_cards(profiles, "bottom", {"draven", "zeri"}) == []


def test_tail_uses_only_the_fraction_of_the_boundary_opponent_inside_worst_20_percent():
    from bottom_blind import weighted_matchup_floor

    assert weighted_matchup_floor([(55, 60), (48, 30), (44, 10)]) == pytest.approx(46)


@pytest.mark.parametrize("reverse", [[], [("corki", 55, 50, 149)]])
def test_unobserved_popular_opponents_cannot_make_a_candidate_look_safe(reverse):
    from bottom_blind import rank_lane_cards

    profiles = {
        "corki": profile([("jhin", 55, 50, 500), ("draven", 55, 50, 500)], early=650),
        "jhin": profile([("corki", 55, 50, 500), ("draven", 55, 50, 500)]),
        "draven": profile(reverse + [("jhin", 55, 50, 500)]),
    }
    assert rank_lane_cards(profiles, "bottom") == []
    assert [c.champion for c in rank_lane_cards(profiles, "bottom", {"draven"})] == ["corki"]


@pytest.fixture
def stats_root():
    import gc
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()
    # Tk 객체의 마지막 참조는 다음 테스트의 데이터 수집 스레드가 아닌 UI 스레드에서 정리한다.
    gc.collect()


def test_stats_tab_compares_bans_without_changing_live_recommendations(stats_root):
    from tkinter import ttk
    from stats_tab import add_stats_tab

    app = ChampionScraperApp.__new__(ChampionScraperApp)
    profiles = {
        "ezreal": profile([("zeri", 57, 50, 2000), ("draven", 43, 50, 2000)], early=610, late=490),
        "zeri": profile([("ezreal", 53, 50, 500), ("draven", 55, 50, 500)], early=490, late=610),
        "draven": profile([("ezreal", 67, 50, 2000), ("zeri", 55, 50, 500)]),
    }
    app.blind_snapshots = {lane: {"profiles": profiles, "collected_on": "2026-11-24"}
                           for lane in ("top", "middle", "bottom", "support")}
    app.banned_champions = set()
    app.lane_files = {}
    app.ignored_champions = {"ezreal"}
    app.ap_champions = set()
    app.format_display_name = str.title
    app.ban_labels = {}
    app.client_watcher = SimpleNamespace(resolve_champion_id=lambda cid: "draven")
    app.resolve_champion_name = str.lower
    app._normalize_client_entries = lambda entries: []
    app._populate_side_from_client = lambda side, entries: False
    app.update_banpick_recommendations = lambda: None
    root = stats_root
    notebook = ttk.Notebook(root)
    stats = app.stats_tab = add_stats_tab(notebook, app)
    assert notebook.tab(0, "text") == "통계 분석"
    root.update()
    def lines(lane):
        return stats.lane_lists[lane].get(0, "end")

    for lane in ("top", "middle", "bottom", "support"):
        assert any("후반형" in row and "Zeri" in row for row in lines(lane))
    assert all("후반형" not in row and "초중반형" not in row for row in lines("jungle"))
    stats.extra_ban.set("Draven")
    stats.extra_ban.event_generate("<<ComboboxSelected>>")
    root.update()
    assert any("초중반형" in row and "Ezreal" in row for row in lines("bottom"))
    assert any("40.40%" in row and "51.00%" in row for row in lines("bottom"))
    assert app.banned_champions == set()  # 추가 밴은 비교용이라 픽창 밴에 들어가지 않는다
    stats.extra_ban.current(0)
    stats.extra_ban.event_generate("<<ComboboxSelected>>")
    app._apply_client_snapshot({"enemyBans": [119]})
    assert any("51.00%" in row for row in lines("bottom"))
    app._apply_client_snapshot({})
    assert not any("51.00%" in row for row in lines("bottom"))



def test_phase_picks_use_all_non_bottom_champions_and_keep_jungle_out():
    from bottom_blind import rank_lane_cards

    profiles = {
        "darius": profile([("kayle", 55, 50, 1000)], early=640, late=480),
        "kayle": profile([("darius", 55, 50, 1000)], early=460, late=620),
    }
    for lane in ("top", "middle", "support"):
        cards = rank_lane_cards(profiles, lane)
        assert [(c.champion, c.early_style) for c in cards] == [("darius", True), ("kayle", False)]
    assert rank_lane_cards(profiles, "bottom") == []
    assert rank_lane_cards(profiles, "jungle") == []


def test_style_pick_recommends_the_ban_that_raises_its_floor_most():
    from bottom_blind import style_pick_rows

    # ezreal 은 draven 에게 밀리고 zeri 를 이긴다 (jhin 은 이미 밴): draven 을 밴하면 불리한 상성 평균이 가장 오른다.
    profiles = {
        "ezreal": profile([("draven", 50, 30, 5000), ("jhin", 52, 30, 5000), ("zeri", 58, 30, 5000)], early=650),
        "draven": profile([("ezreal", 52, 30, 5000), ("jhin", 52, 30, 5000), ("zeri", 52, 30, 5000)]),
        "jhin": profile([("ezreal", 54, 30, 5000), ("draven", 52, 30, 5000), ("zeri", 52, 30, 5000)]),
        "zeri": profile([("ezreal", 46, 30, 5000), ("draven", 52, 30, 5000), ("jhin", 52, 30, 5000)]),
    }
    rows = style_pick_rows("bottom", profiles, {"jhin"})
    assert rows[0] == "초중반형 선픽  ezreal"
    assert rows[3].startswith("  추천 밴 draven → 불리한 상성 ")
    # 이미 밴된 상대는 다시 추천하지 않는다
    assert not any("추천 밴 jhin" in row for row in rows)
