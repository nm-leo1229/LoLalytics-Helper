"""추천 표의 '카운터 N위', '시너지 N위' 태그에 쓰는 순위 계산 검증 (창을 띄우지 않는다)."""
from lobby_manager import ChampionScraperApp


def test_rank_counters_ranks_lowest_enemy_win_rate_first_among_pick_rate_1_or_more():
    # 다리우스(탑)의 카운터 목록 일부. 승률은 다리우스가 그 챔피언을 상대로 거둔 승률이다.
    darius_top = {
        "Wukong": {"win_rate": "47.81", "popularity": "0.97"},     # 승률은 가장 낮지만 픽률 1% 미만이라 제외
        "Teemo": {"win_rate": "49.20", "popularity": "1.00"},      # 픽률이 기준값과 같으면 포함
        "Vayne": {"win_rate": "48.95", "popularity": "2.00"},
        "Urgot": {"win_rate": "49.48", "popularity": "1.51"},      # 4위라 표시하지 않는다
        "Gangplank": {"win_rate": "49.03", "popularity": "2.71"},
        "Yasuo": {"win_rate": "58.98", "popularity": "1.54"},
    }

    assert ChampionScraperApp.rank_counters(darius_top, set(darius_top)) == {"Vayne": 1, "Gangplank": 2, "Teemo": 3}


def test_rank_counters_skips_champions_the_table_cannot_recommend():
    darius_top = {
        "Vayne": {"win_rate": "48.95", "popularity": "2.00"},      # 밴되어 추천할 수 없다
        "Gangplank": {"win_rate": "49.03", "popularity": "2.71"},
        "Teemo": {"win_rate": "49.20", "popularity": "2.19"},
        "Urgot": {"win_rate": "49.48", "popularity": "1.51"},
    }

    ranks = ChampionScraperApp.rank_counters(darius_top, {"Gangplank", "Teemo", "Urgot"})

    assert ranks == {"Gangplank": 1, "Teemo": 2, "Urgot": 3}


def test_rank_synergies_ranks_highest_win_rate_first_among_pick_rate_3_or_more():
    # 노틸러스(서폿)와 함께한 원딜 목록 일부. 승률은 둘이 같은 팀일 때의 승률이다.
    nautilus_bottom = {
        "Seraphine": {"win_rate": "56.63", "pick_rate": "0.99"},      # 승률은 가장 높지만 픽률 3% 미만이라 제외
        "Nilah": {"win_rate": "55.12", "pick_rate": "2.99"},          # 기준에 조금 못 미쳐도 제외
        "Tristana": {"win_rate": "52.67", "pick_rate": "3.00"},       # 픽률이 기준값과 같으면 포함
        "Samira": {"win_rate": "55.33", "pick_rate": "6.85"},
        "Miss Fortune": {"win_rate": "52.41", "pick_rate": "3.37"},   # 4위라 표시하지 않는다
        "Jinx": {"win_rate": "54.92", "pick_rate": "4.72"},
    }

    ranks = ChampionScraperApp.rank_synergies(nautilus_bottom, set(nautilus_bottom))

    assert ranks == {"Samira": 1, "Jinx": 2, "Tristana": 3}


def test_rank_synergies_keeps_list_order_when_win_rates_tie():
    # 엘리스(서폿)와 함께한 정글 목록 일부. 데이터 목록은 픽률이 높은 순으로 들어 있다.
    elise_jungle = {
        "Kayn": {"win_rate": "52.76", "pick_rate": "3.25"},
        "Wukong": {"win_rate": "52.76", "pick_rate": "3.07"},      # 케인과 승률이 같다
        "Nocturne": {"win_rate": "53.11", "pick_rate": "3.40"},
    }

    ranks = ChampionScraperApp.rank_synergies(elise_jungle, set(elise_jungle))

    assert ranks == {"Nocturne": 1, "Kayn": 2, "Wukong": 3}
