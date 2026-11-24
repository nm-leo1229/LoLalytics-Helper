import tkinter as tk
from tkinter import ttk

from banpick_stats import MIN_CANDIDATE_SHARE, lane_plan, plan_rows
from bottom_blind import MIN_FLOOR, STYLE_LANES, phase_scores, style_pick_rows
from common import LANES
from pre_pick_tab import add_lane_lists
from weight_settings_tab import LANE_DISPLAY_NAMES

FOOTER = (
    f"유형별 선픽은 자주 만나는 상대 중 불리한 쪽 20%의 평균 승률이 {MIN_FLOOR:g}% 이상인 후보에서 고릅니다.\n"
    "15–25분과 30–40분은 그 시간에 끝난 경기의 라인 평균 대비 승률 차이입니다. 불리한 상성의 화살표는 밴 없음 → 밴 적용입니다.\n"
    f"종합 설계는 추천 제외 목록을 반영하고 점유율 {MIN_CANDIDATE_SHARE:.0%} 이상을 봅니다. 선픽·대안 점수는 최악의 상대 하나를 밴한 뒤 남은 최저 승률입니다.\n"
    "AD·AP는 피해 유형별 선픽입니다. 후픽의 +값은 준비했을 때의 전체 승률 이득(%p), 들여 쓴 줄은 그 상황에서의 승률입니다."
)


class StatsTab:
    def __init__(self, notebook, app):
        self.app = app
        self.plan_lines = {}
        tab = tk.Frame(notebook)
        notebook.add(tab, text="통계 분석")
        controls = tk.Frame(tab)
        controls.pack(side="bottom", fill="x", padx=10, pady=(0, 6))
        self.status = tk.Label(controls, anchor="w")
        self.status.pack(side="left")
        champions = {name for snapshot in app.blind_snapshots.values() for name in snapshot.get("profiles", {})}
        self.ban_names = {app.format_display_name(name): name for name in champions}
        self.extra_ban = ttk.Combobox(controls, state="readonly", width=15, values=["없음", *sorted(self.ban_names)])
        self.extra_ban.current(0)
        self.extra_ban.pack(side="right")
        tk.Label(controls, text="유형별 선픽에 추가할 밴").pack(side="right", padx=4)

        for lane in LANES:
            try:
                plan = lane_plan(app.lane_files, lane, app.ignored_champions, app.ap_champions)
                profiles = app.blind_snapshots.get(lane, {}).get("profiles", {})
                phases = phase_scores(profiles) if lane in STYLE_LANES else None
                self.plan_lines[lane] = plan_rows(plan, LANE_DISPLAY_NAMES, app.format_display_name, phases)
            except Exception as error:
                self.plan_lines[lane] = [f"종합 설계를 계산하지 못했습니다: {error!r}"]
        self.lane_lists = add_lane_lists(tab, self.plan_lines.get, FOOTER)
        self.extra_ban.bind("<<ComboboxSelected>>", lambda _: self.refresh_styles())
        tab.after_idle(self.refresh_styles)

    def refresh_styles(self):
        bans = set(self.app.banned_champions)
        extra = self.ban_names.get(self.extra_ban.get())
        if extra:
            bans.add(extra)
        for lane in STYLE_LANES:
            profiles = self.app.blind_snapshots.get(lane, {}).get("profiles", {})
            prefix = style_pick_rows(lane, profiles, bans, self.app.format_display_name)
            box = self.lane_lists[lane]
            # 종합 설계와 그 스크롤 위치는 유지하고 시간대별 선픽 문구만 갱신한다.
            position = box.yview()[0]
            old_count = box.size() - len(self.plan_lines[lane])
            if old_count:
                box.delete(0, old_count - 1)
            for row in reversed(prefix + [""]):
                box.insert(0, row)
            box.yview_moveto(position)
        labels = ", ".join(self.app.format_display_name(name) for name in sorted(bans)) or "없음"
        dates = sorted({s["collected_on"] for s in self.app.blind_snapshots.values() if s.get("collected_on")})
        self.status.configure(text=f"유형별 선픽 · 글로벌 마스터+ 최근 30일 · 수집 {', '.join(dates) or '자료 없음'} · 적용 밴 {labels}")


def add_stats_tab(notebook, app):
    return StatsTab(notebook, app)
