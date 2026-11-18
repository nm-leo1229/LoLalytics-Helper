"""scraper.py 의 수집 대상 선정 검증 (브라우저 없이 실행)."""
import pytest

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
