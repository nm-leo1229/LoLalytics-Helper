import tkinter as tk

from banpick_stats import MIN_CANDIDATE_SHARE, MIN_OPPONENT_SHARE
from common import LANES
from weight_settings_tab import LANE_DISPLAY_NAMES

PRE_PICK_MIN_WIN_RATE = 49.0  # 가장 불리한 상대 하나를 밴한 뒤 남은 상대 모두에게 이 승률(%) 이상이면 선픽 카드


def add_lane_lists(tab, rows_of, footer, lanes=LANES):
    """라인별 목록과 설명을 주어진 탭에 붙인다."""
    columns = tk.Frame(tab)
    columns.pack(fill="both", expand=True, padx=10, pady=(10, 5))
    columns.grid_rowconfigure(0, weight=1)
    lists = {}
    for index, lane in enumerate(lanes):
        columns.grid_columnconfigure(index, weight=1)
        frame = tk.LabelFrame(columns, text=LANE_DISPLAY_NAMES[lane])
        frame.grid(row=0, column=index, sticky="nsew", padx=3)
        listbox = tk.Listbox(frame, exportselection=False)
        lists[lane] = listbox
        listbox.pack(fill="both", expand=True, padx=5, pady=5)
        # 한 줄씩 넣는다: 탭은 백그라운드 스레드(preload_all_champion_data)에서 만들어지고, Python 3.13 tkinter 는
        # 다른 스레드에서 인자가 64개를 넘는 Tk 호출을 하면 프로세스가 죽는다 (insert(END, *rows) 로 64줄이면 앱이 꺼짐)
        for row in rows_of(lane):
            listbox.insert(tk.END, row)
    tk.Label(tab, text=footer, anchor="w", justify="left").pack(fill="x", padx=10, pady=(0, 10))
    return lists


class PrePickTab:
    def __init__(self, notebook, app):
        tab = tk.Frame(notebook)
        notebook.add(tab, text="선픽 카드")
        footer = (f"★ 가장 불리한 상대 하나를 밴한 뒤 남은 상대 중 최저 승률이 {PRE_PICK_MIN_WIN_RATE:g}% 이상 "
                  f"· 괄호는 밴할 상대 → 그다음 상대 · 후보 점유율 {MIN_CANDIDATE_SHARE:.0%} 이상, "
                  f"상대 점유율 {MIN_OPPONENT_SHARE:.1%} 이상")
        add_lane_lists(tab, lambda lane: self._rows(app, lane), footer)

    @staticmethod
    def _rows(app, lane):
        """그 라인 챔피언을 밴 하나를 쓴 뒤 가장 불리한 상대에게 거두는 승률이 높은 순으로 '50.02  Ekko ★  (밴 Lissandra → Akshan)' 꼴로 돌려준다."""
        name = app.format_display_name
        rows = sorted((-win, name(champion), name(ban), name(opponent))
                      for champion, (win, opponent, ban) in app.pre_pick_worst.get(lane, {}).items())
        return [f"{-win:.2f}  {champion}" + (" ★" if -win >= PRE_PICK_MIN_WIN_RATE else "") + f"  (밴 {ban} → {opponent})"
                for win, champion, ban, opponent in rows]
