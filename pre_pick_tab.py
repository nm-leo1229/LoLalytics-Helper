import tkinter as tk

from banpick_stats import MIN_CANDIDATE_SHARE, MIN_OPPONENT_SHARE
from common import LANES
from weight_settings_tab import LANE_DISPLAY_NAMES

PRE_PICK_MIN_WIN_RATE = 49.0  # 가장 불리한 상대에게도 이 승률(%) 이상이면 선픽 카드 (부풀림을 뺀 승률이라 50 을 넘는 챔피언은 거의 없다)


def add_lane_lists_tab(notebook, title, rows_of, footer):
    """5개 라인의 목록을 한 화면에 나란히 놓은 탭을 붙인다. rows_of(lane) 은 그 라인 목록의 줄들, footer 는 아래 설명 글."""
    tab = tk.Frame(notebook)
    notebook.add(tab, text=title)
    columns = tk.Frame(tab)
    columns.pack(fill="both", expand=True, padx=10, pady=(10, 5))
    columns.grid_rowconfigure(0, weight=1)
    for index, lane in enumerate(LANES):
        columns.grid_columnconfigure(index, weight=1)
        frame = tk.LabelFrame(columns, text=LANE_DISPLAY_NAMES[lane])
        frame.grid(row=0, column=index, sticky="nsew", padx=3)
        listbox = tk.Listbox(frame, exportselection=False)
        listbox.pack(fill="both", expand=True, padx=5, pady=5)
        # 한 줄씩 넣는다: 탭은 백그라운드 스레드(preload_all_champion_data)에서 만들어지고, Python 3.13 tkinter 는
        # 다른 스레드에서 인자가 64개를 넘는 Tk 호출을 하면 프로세스가 죽는다 (insert(END, *rows) 로 64줄이면 앱이 꺼짐)
        for row in rows_of(lane):
            listbox.insert(tk.END, row)
    tk.Label(tab, text=footer, anchor="w", justify="left").pack(fill="x", padx=10, pady=(0, 10))


class PrePickTab:
    """라인별로 챔피언을 가장 불리한 상대 승률이 높은 순으로 세우고 선픽 카드에 ★ 를 붙인다 (5개 라인을 한 화면에)."""

    def __init__(self, notebook, app_context):
        add_lane_lists_tab(
            notebook, "선픽 카드", lambda lane: self._rows(app_context, lane),
            f"★ 선픽 카드 (숫자가 {PRE_PICK_MIN_WIN_RATE:g}% 이상) · 숫자: 가장 불리한 상대(괄호 안)에게 거두는 승률\n"
            f"통계 분석 탭과 같은 값입니다: 부풀림을 빼고 표본이 적은 상성은 평균 쪽으로 당김 · "
            f"픽 점유율 {MIN_CANDIDATE_SHARE:.0%} 이상인 챔피언과 {MIN_OPPONENT_SHARE:.1%} 이상인 상대만 봄")

    @staticmethod
    def _rows(app, lane):
        """그 라인 챔피언을 가장 불리한 상대에게 거두는 승률이 높은 순으로 '49.71  Ekko ★  (Lissandra)' 꼴로 돌려준다."""
        rows = sorted((-win, app.format_display_name(champion), app.format_display_name(opponent))
                      for champion, (win, opponent) in app.pre_pick_worst.get(lane, {}).items())
        return [f"{-win:.2f}  {name}" + (" ★" if -win >= PRE_PICK_MIN_WIN_RATE else "") + f"  ({opponent})" for win, name, opponent in rows]
