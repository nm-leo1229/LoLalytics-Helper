"""scraper.py 의 수집 대상 선정 검증 (브라우저 없이 실행)."""
import pytest
import json
import os

pytest.importorskip("undetected_chromedriver")  # 수집용 패키지가 없는 환경에서는 건너뛴다
import scraper


def test_filter_by_pick_rate_keeps_champions_at_or_above_minimum():
    rows = [
        ["/lol/fiora/build/?tier=master_plus&patch=30", "5.22"],            # 주 레인은 링크에 lane 이 없다
        ["/lol/corki/build/?lane=top&tier=master_plus&patch=30", "0.50"],   # 기준값과 같으면 수집한다
        ["/lol/ahri/build/?lane=top&tier=master_plus&patch=30", "0.47"],    # 기준 미만은 버린다
    ]

    assert scraper.filter_by_pick_rate(rows) == ["fiora", "corki"]


def test_generate_url_asks_for_master_plus_over_the_last_30_days():
    assert scraper.generate_url("fiora", "top") == (
        "https://lolalytics.com/lol/fiora/build/?lane=top&tier=master_plus&patch=30")


def bottom_page():
    # Qwik references are base 36 indexes, including references inside arrays and dictionaries.
    objs = [
        {"champion": "1", "tier": "2", "patch": "3", "region": "4", "lane": "5", "mode": "6"},
        "corki", "master_plus", "30", "all", "bottom", "ranked",
        {"time": "8", "timeWin": "9"},
        {str(i): "a" for i in range(1, 8)}, {str(i): "b" for i in range(1, 8)}, 900, 470,
        {"champPath": "d", "champId": "e"}, {"222": "f"}, {"jinx": "g"}, "jinx", 222,
        {lane: "i" for lane in scraper.LANES}, 45,
        {lane: "k" for lane in scraper.LANES}, ["l"], ["g", "m", "n", "n", "o", "p"],
        53.2, 0, 4.3, 300,
    ]
    return json.dumps({"objs": objs})


def test_extracts_matching_bottom_profile_with_exact_duration_counts():
    data = scraper.extract_lane_profile(bottom_page(), "corki", "bottom")
    assert data["time"] == [[900, 470]] * 7
    assert data["matchups"] == {"jinx": {"win_rate": 53.2, "popularity": 4.3, "games": 300}}
    with pytest.raises(ValueError):
        scraper.extract_lane_profile(bottom_page(), "zeri", "bottom")


def test_partial_collection_preserves_complete_snapshot(tmp_path):
    from bottom_blind import load_bottom_snapshot

    scraper.collect_lane_snapshot("bottom", ["corki"], lambda name: bottom_page(), tmp_path)
    before = load_bottom_snapshot(tmp_path)
    assert set(before["profiles"]) == {"corki"}
    with pytest.raises(ValueError):
        scraper.collect_lane_snapshot("bottom", ["corki", "zeri"], lambda name: bottom_page(), tmp_path)
    assert load_bottom_snapshot(tmp_path) == before
    assert load_bottom_snapshot(tmp_path / "legacy").get("profiles", {}) == {}


@pytest.mark.skipif(os.name != "nt", reason="Windows Chrome installation")
def test_scraper_selects_installed_chrome_major_unless_overridden(monkeypatch):
    import winreg
    from contextlib import nullcontext

    monkeypatch.delenv("SCRAPER_CHROME_VERSION_MAIN", raising=False)
    monkeypatch.setattr(winreg, "OpenKey", lambda *args: nullcontext(None))
    monkeypatch.setattr(winreg, "QueryValueEx", lambda *args: ("157.0.8103.79", winreg.REG_SZ))
    assert scraper.chrome_major_version() == 157
    monkeypatch.setenv("SCRAPER_CHROME_VERSION_MAIN", "156")
    assert scraper.chrome_major_version() == 156


def test_mid_snapshot_reads_mid_opponents_and_rejects_wrong_role(tmp_path):
    from bottom_blind import load_lane_snapshot
    data = json.loads(bottom_page())
    data["objs"][5] = "middle"
    data["objs"][19]["bottom"] = "i"  # Only the middle matchup list is meaningful.
    state = json.dumps(data)
    scraper.collect_lane_snapshot("middle", ["corki"], lambda _: state, tmp_path)
    assert load_lane_snapshot(tmp_path, "middle")["profiles"]["corki"]["matchups"]["jinx"]["games"] == 300
    assert not load_lane_snapshot(tmp_path, "bottom")
    with pytest.raises(ValueError):
        scraper.extract_lane_profile(state, "corki", "top")
