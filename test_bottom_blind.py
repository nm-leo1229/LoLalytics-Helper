from types import SimpleNamespace

import pytest

from lobby_manager import ChampionScraperApp


def profile(matchups, early=550, late=550):
    # Seven bins of 1,000 games. The two early and two late bins vary independently.
    return {"time": [[1000, wins] for wins in [550, early, early, 550, late, late, 550]],
            "matchups": {name: {"win_rate": wr, "popularity": pop, "games": games}
                         for name, wr, pop, games in matchups}}


def test_cards_use_reciprocal_rates_pooled_time_baseline_and_live_bans():
    from bottom_blind import rank_bottom_cards

    profiles = {
        "ezreal": profile([("zeri", 57, 50, 2000), ("draven", 43, 50, 2000)], early=610, late=490),
        "zeri": profile([("ezreal", 53, 50, 500), ("draven", 55, 50, 500)], early=490, late=610),
        "draven": profile([("ezreal", 67, 50, 2000), ("zeri", 55, 50, 500)]),
    }
    assert [card.champion for card in rank_bottom_cards(profiles)] == ["zeri"]
    early, late = rank_bottom_cards(profiles, {"draven"})
    # 57 vs 53 centers to 52. The smaller 500-game sample shrinks it halfway to 50.
    assert (early.champion, early.floor, early.early, early.late) == ("ezreal", 51, 4, -4)
    assert (late.champion, late.floor, late.early, late.late) == ("zeri", 49, -4, 4)
    assert rank_bottom_cards(profiles, {"draven", "zeri"}) == []


def test_tail_uses_only_the_fraction_of_the_boundary_opponent_inside_worst_20_percent():
    from bottom_blind import weighted_matchup_floor

    assert weighted_matchup_floor([(55, 60), (48, 30), (44, 10)]) == pytest.approx(46)


@pytest.mark.parametrize("reverse", [[], [("corki", 55, 50, 149)]])
def test_unobserved_popular_opponents_cannot_make_a_candidate_look_safe(reverse):
    from bottom_blind import rank_bottom_cards

    profiles = {
        "corki": profile([("jhin", 55, 50, 500), ("draven", 55, 50, 500)], early=650),
        "jhin": profile([("corki", 55, 50, 500), ("draven", 55, 50, 500)]),
        "draven": profile(reverse + [("jhin", 55, 50, 500)]),
    }
    assert rank_bottom_cards(profiles) == []
    assert [c.champion for c in rank_bottom_cards(profiles, {"draven"})] == ["corki"]


def test_tag_and_card_list_agree_when_only_bans_change():
    app = ChampionScraperApp.__new__(ChampionScraperApp)
    app.canonical_lookup = {"corki": "corki"}
    app.banned_champions = set()
    app.bottom_blind_profiles = {
        "corki": profile([("jhin", 55, 50, 500), ("draven", 40, 50, 500)], early=650),
        "draven": profile([("corki", 65, 50, 500), ("jhin", 55, 50, 500)]),
        "jhin": profile([("corki", 55, 50, 500), ("draven", 55, 50, 500)]),
    }
    app.ban_labels = {}
    app.client_watcher = SimpleNamespace(resolve_champion_id=lambda cid: "draven")
    app.resolve_champion_name = str.lower
    app.format_display_name = str.title
    app._normalize_client_entries = lambda entries: []
    app._populate_side_from_client = lambda side, entries: False
    refreshes = []
    app.update_banpick_recommendations = lambda: refreshes.append(app._qualifies_for_pre_pick_tag("Corki", "bottom"))
    assert not app._qualifies_for_pre_pick_tag("Corki", "bottom")
    assert app._apply_client_snapshot({"enemyBans": [119]})
    assert app._qualifies_for_pre_pick_tag("Corki", "bottom")
    assert app._apply_client_snapshot({"enemyBans": []})
    assert refreshes == [True, False]


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
    app.bottom_blind_profiles = {
        "ezreal": profile([("zeri", 57, 50, 2000), ("draven", 43, 50, 2000)], early=610, late=490),
        "zeri": profile([("ezreal", 53, 50, 500), ("draven", 55, 50, 500)], early=490, late=610),
        "draven": profile([("ezreal", 67, 50, 2000), ("zeri", 55, 50, 500)]),
    }
    app.blind_snapshots = {lane: {"profiles": app.bottom_blind_profiles, "collected_on": "2026-11-24"}
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
    assert set(app.bottom_blind_cards()) == {"zeri"}
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
