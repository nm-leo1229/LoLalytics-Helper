"""선픽 카드 판정에 쓰는 '가장 불리한 상대 승률' 계산 검증 (창을 띄우지 않는다)."""
from lobby_manager import ChampionScraperApp


def test_worst_matchup_win_rate_uses_only_opponents_above_pick_rate_1_5():
    # 승률은 이 챔피언이 그 상대를 상대로 거둔 승률이다.
    lane_entries = {
        "Wukong": {"win_rate": "45.00", "popularity": "1.49"},  # 픽률 1.5 미만이라 제외
        "Teemo": {"win_rate": "46.00", "popularity": "1.50"},   # 픽률이 기준값과 같아도 제외
        "Vayne": {"win_rate": "50.44", "popularity": "2.00"},
        "Sett": {"win_rate": "49.70", "popularity": "1.51"},
    }

    assert ChampionScraperApp.worst_matchup_win_rate(lane_entries) == 49.70


def test_worst_matchup_win_rate_is_none_without_popular_opponents():
    assert ChampionScraperApp.worst_matchup_win_rate({"Teemo": {"win_rate": "40.00", "popularity": "1.50"}}) is None
    assert ChampionScraperApp.worst_matchup_win_rate({}) is None
