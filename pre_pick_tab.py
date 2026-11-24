import tkinter as tk
from tkinter import ttk

from bottom_blind import MIN_FLOOR
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


class BottomBlindPanel(tk.LabelFrame):
    """선픽 카드와 통계 분석이 같은 바텀 판정을 보여 준다."""

    def __init__(self, parent, app):
        super().__init__(parent, text="바텀 선픽 · 게임 시간대별")
        self.app = app
        header = tk.Frame(self)
        header.pack(fill="x", padx=6, pady=3)
        self.status = tk.Label(header, anchor="w")
        self.status.pack(side="left")
        grid = tk.Frame(self)
        grid.pack(fill="x", padx=6)
        headings = {"name": "챔피언", "style": "선픽 유형"}
        headings.update(floor="불리한 상성 · 밴 적용", early="15–25분 종료", late="30–40분 종료")
        self.table = ttk.Treeview(grid, columns=tuple(headings), show="headings", height=4)
        for field, label in headings.items():
            self.table.heading(field, text=label)
            self.table.column(field, width=115, anchor="center")
        scroll = ttk.Scrollbar(grid, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.table.pack(fill="x", expand=True)
        tk.Label(self, anchor="w", justify="left",
                 text=f"자력 이동기가 있는 후보 중 자주 만나는 상대의 하위 20% 상성이 {MIN_FLOOR:g}% 이상인 카드입니다. "
                      "시간대 수치는 해당 시간에 끝난 경기의 바텀 평균 대비 보정 승률 차이입니다.").pack(fill="x", padx=6, pady=3)
        self.after_idle(self.refresh_bottom)

    def refresh_bottom(self):
        profiles = self.app.bottom_blind_profiles
        live_bans = self.app.banned_champions
        cards = self.app.bottom_blind_cards().values()
        self.table.delete(*self.table.get_children())
        for card in cards:
            values = [self.app.format_display_name(card.champion), "초중반형" if card.early_style else "후반형"]
            values.extend((f"{card.floor:.2f}%", f"{card.early:+.2f}%p", f"{card.late:+.2f}%p"))
            self.table.insert("", "end", values=values)
        if profiles:
            bans = ", ".join(self.app.format_display_name(name) for name in sorted(live_bans))
            status = f"{self.app.bottom_blind_date} 수집 · 글로벌 마스터+ 30일 · 픽창 밴 {bans or '없음'}"
            if not cards:
                status += " · 조건을 충족하는 카드 없음"
        else:
            status = "바텀 선픽 통계가 없습니다. scraper.py를 실행해 시간대와 상성 데이터를 수집하세요."
        self.status.configure(text=status)


class PrePickTab:
    def __init__(self, notebook, app):
        tab = tk.Frame(notebook)
        notebook.add(tab, text="선픽 카드")
        self.bottom_panel = BottomBlindPanel(tab, app)
        self.bottom_panel.pack(fill="x", padx=10, pady=(10, 0))
        footer = (f"★ 가장 불리한 상대 하나를 밴한 뒤 남은 상대 중 최저 승률이 {PRE_PICK_MIN_WIN_RATE:g}% 이상 "
                  f"· 괄호는 밴할 상대 → 그다음 상대 · 후보 점유율 {MIN_CANDIDATE_SHARE:.0%} 이상, "
                  f"상대 점유율 {MIN_OPPONENT_SHARE:.1%} 이상")
        add_lane_lists(tab, lambda lane: self._rows(app, lane), footer, [lane for lane in LANES if lane != "bottom"])

    @staticmethod
    def _rows(app, lane):
        """그 라인 챔피언을 밴 하나를 쓴 뒤 가장 불리한 상대에게 거두는 승률이 높은 순으로 '50.02  Ekko ★  (밴 Lissandra → Akshan)' 꼴로 돌려준다."""
        name = app.format_display_name
        rows = sorted((-win, name(champion), name(ban), name(opponent))
                      for champion, (win, opponent, ban) in app.pre_pick_worst.get(lane, {}).items())
        return [f"{-win:.2f}  {champion}" + (" ★" if -win >= PRE_PICK_MIN_WIN_RATE else "") + f"  (밴 {ban} → {opponent})"
                for win, champion, ban, opponent in rows]
