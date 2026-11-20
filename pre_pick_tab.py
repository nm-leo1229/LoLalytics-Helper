import tkinter as tk

from common import LANES
from weight_settings_tab import LANE_DISPLAY_NAMES

PRE_PICK_MIN_POPULARITY = 1.5  # 같은 라인 상대 중 픽률(%)이 이보다 높은 상대만 본다
PRE_PICK_MIN_WIN_RATE = 50.0  # 그 상대 모두에게 이 승률(%) 이상이면 선픽 카드


class PrePickTab:
    """라인별로 챔피언을 가장 불리한 상대 승률이 높은 순으로 세우고 선픽 카드에 ★ 를 붙인다 (5개 라인을 한 화면에)."""

    def __init__(self, notebook, app_context, data_dir):
        self.app = app_context
        tab = tk.Frame(notebook)
        notebook.add(tab, text="선픽 카드")
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
            for row in self._rows(data_dir, lane):
                listbox.insert(tk.END, row)
        tk.Label(
            tab,
            text=f"★ 선픽 카드 (숫자가 {PRE_PICK_MIN_WIN_RATE:g}% 이상) · "
                 f"숫자: 같은 라인에서 픽률 {PRE_PICK_MIN_POPULARITY:g}%가 넘는 상대들에게 거둔 승률 중 가장 낮은 값",
            anchor="w",
        ).pack(fill="x", padx=10, pady=(0, 10))

    def _rows(self, data_dir, lane):
        """그 라인 챔피언을 가장 불리한 상대 승률이 높은 순으로 '50.44  Gangplank ★' 꼴로 돌려준다."""
        rows = []
        for path in data_dir.glob(f"*_{lane}.json"):
            champion = path.stem[:-len(lane) - 1]
            dataset = self.app._get_recommend_counter_dataset(champion, lane)
            worst = self.app.worst_matchup_win_rate(dataset[lane]) if dataset else None
            if worst is not None:
                rows.append((worst, self.app.format_display_name(champion)))
        return [f"{worst:.2f}  {name}" + (" ★" if worst >= PRE_PICK_MIN_WIN_RATE else "")
                for worst, name in sorted(rows, key=lambda row: (-row[0], row[1]))]
