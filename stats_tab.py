from banpick_stats import MIN_CANDIDATE_SHARE, lane_plan, plan_rows
from pre_pick_tab import add_lane_lists_tab
from weight_settings_tab import LANE_DISPLAY_NAMES

FOOTER = (
    "숫자는 승률(%)입니다. 부풀림을 빼고 표본이 적은 상성은 평균 쪽으로 당긴 값입니다 · 선픽·대안 옆: 선픽 카드 탭과 같은 선픽 점수\n"
    "후픽 옆 +숫자: 그 챔피언을 준비하면 오르는 전체 승률(%p) · 들여 쓴 줄: 그 챔피언이 보이면 선픽 대신 꺼낼 때의 승률\n"
    "AD 선픽·AP 선픽: 아군 조합이 한쪽으로 쏠릴 때 고를 종류별 1위 (AP 는 AP 딜러 목록 ap_champions.json 의 챔피언, AD 는 그 밖의 챔피언)\n"
    f"후보: 추천 제외 목록에 없고 그 라인 픽 점유율이 {MIN_CANDIDATE_SHARE:.0%} 이상인 챔피언 · 밴: 선픽이 가장 불리한 상대\n"
    "추천 제외 목록이나 AP 딜러 목록을 바꾸면 다시 실행해야 반영됩니다 · 계산식은 banpick_stats.py"
)


def add_stats_tab(notebook, app):
    """통계만으로 계산한 라인별 밴픽 설계(선픽·대안·밴·후픽)를 5개 라인 한 화면에 보여주는 탭을 붙인다."""
    def rows(lane):
        try:
            plan = lane_plan(app.lane_files, lane, app.ignored_champions, app.ap_champions)
            return plan_rows(plan, LANE_DISPLAY_NAMES, app.format_display_name)
        except Exception as error:  # 이 탭은 다른 탭들과 같은 스레드에서 만들어진다: 데이터가 없거나 깨져도 앱은 떠야 한다
            return [f"계산하지 못했습니다: {error!r}"]

    add_lane_lists_tab(notebook, "통계 분석", rows, FOOTER)
