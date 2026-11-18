import json
import tkinter as tk
from tkinter import messagebox, ttk

from common import LANES, AutocompletePopup, resolve_resource_path
from weight_settings_tab import LANE_DISPLAY_NAMES

MY_CHAMPIONS_FILE = resolve_resource_path("my_champions.json")


def load_my_champions():
    """(내 챔피언만 추천 여부, {라인: {정식 이름 소문자}})"""
    try:
        with open(MY_CHAMPIONS_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):  # 없거나 깨진 파일 (ValueError 는 JSON·인코딩 오류 둘 다)
        data = {}
    data = data if isinstance(data, dict) else {}
    lanes = data.get("lanes") if isinstance(data.get("lanes"), dict) else {}
    return data.get("enabled") is True, {
        lane: {name.lower() for name in lanes.get(lane) or [] if isinstance(name, str) and name}
        if isinstance(lanes.get(lane) or [], list) else set()
        for lane in LANES
    }


class MyChampionsTab:
    """라인별로 내가 하는 챔피언을 모아 두는 탭. 켜 두면 추천 표에 이 챔피언들만 나온다."""

    def __init__(self, notebook, app_context):
        self.app = app_context
        self.tab = tk.Frame(notebook)
        notebook.add(self.tab, text="내 챔피언")
        self.listboxes = {}
        self._build_ui()
        self.refresh()
        self.app.my_champions_only_var.trace_add("write", lambda *_: self._changed())

    def _build_ui(self):
        top = tk.Frame(self.tab)
        top.pack(fill="x", padx=10, pady=(10, 5))
        self.entry = tk.Entry(top, width=25)
        self.entry.pack(side="left")
        self.lane_var = tk.StringVar(value=LANE_DISPLAY_NAMES[LANES[0]])
        ttk.Combobox(top, textvariable=self.lane_var, values=[LANE_DISPLAY_NAMES[lane] for lane in LANES],
                     state="readonly", width=8).pack(side="left", padx=(5, 0))
        tk.Button(top, text="추가", command=self.add_champion).pack(side="left", padx=(5, 0))
        tk.Button(top, text="선택 제거", command=self.remove_selected).pack(side="left", padx=(5, 0))
        tk.Checkbutton(top, text="내 챔피언만 추천", variable=self.app.my_champions_only_var).pack(side="left", padx=(20, 0))
        # 자동완성에서 고르면(Enter·클릭) 그 챔피언을 바로 추가하고, 자동완성이 Enter 를 쓰지 않았을 때만 입력값을 추가한다
        self.autocomplete = AutocompletePopup(self.entry, self.app.get_autocomplete_candidates,
                                              on_select=lambda _v: self.add_champion())
        self.entry.bind("<Return>", lambda _e: self.add_champion(), add="+")

        columns = tk.Frame(self.tab)
        columns.pack(fill="both", expand=True, padx=10, pady=5)
        columns.grid_rowconfigure(0, weight=1)
        for index, lane in enumerate(LANES):
            columns.grid_columnconfigure(index, weight=1)
            frame = tk.LabelFrame(columns, text=LANE_DISPLAY_NAMES[lane])
            frame.grid(row=0, column=index, sticky="nsew", padx=3)
            listbox = tk.Listbox(frame, exportselection=False)
            listbox.pack(fill="both", expand=True, padx=5, pady=5)
            listbox.bind("<Delete>", lambda _e: self.remove_selected())
            listbox.bind("<<ListboxSelect>>", lambda _e, lane=lane: self._keep_selection_in(lane))
            self.listboxes[lane] = listbox

        tk.Label(
            self.tab,
            text="'내 챔피언만 추천'을 켜면 추천 표에 내 라인에 넣어 둔 챔피언만 나옵니다 (챔피언 추천 탭의 같은 체크박스와 연동).",
            anchor="w",
        ).pack(fill="x", padx=10, pady=(0, 10))

    def _keep_selection_in(self, lane):
        """선택은 한 라인 칸에만 남긴다 (다른 칸에 남은 선택까지 지워지지 않게)."""
        if self.listboxes[lane].curselection():
            for other, listbox in self.listboxes.items():
                if other != lane:
                    listbox.selection_clear(0, tk.END)

    def refresh(self):
        for lane, listbox in self.listboxes.items():
            listbox.delete(0, tk.END)
            for name in sorted(self.app.my_champions[lane], key=self._display):
                listbox.insert(tk.END, self._display(name))

    def _display(self, normalized):
        canonical = self.app.canonical_lookup.get(normalized, normalized)
        return self.app.display_lookup.get(canonical, canonical.title())

    def add_champion(self):
        query = self.entry.get().strip()
        if not query:
            return
        canonical = self.app.resolve_champion_name(query)
        if not canonical:
            messagebox.showerror("내 챔피언", f"'{query}' 챔피언을 찾을 수 없습니다.")
            return
        lane = next(lane for lane in LANES if LANE_DISPLAY_NAMES[lane] == self.lane_var.get())
        self.app.my_champions[lane].add(canonical.lower())
        self.entry.delete(0, tk.END)
        self._changed()

    def remove_selected(self):
        removed = False
        for lane, listbox in self.listboxes.items():
            names = sorted(self.app.my_champions[lane], key=self._display)
            for index in listbox.curselection():
                self.app.my_champions[lane].discard(names[index])
                removed = True
        if removed:
            self._changed()

    def _changed(self):
        try:
            with open(MY_CHAMPIONS_FILE, "w", encoding="utf-8") as handle:
                json.dump({"enabled": self.app.my_champions_only_var.get(),
                           "lanes": {lane: sorted(names) for lane, names in self.app.my_champions.items()}},
                          handle, ensure_ascii=False, indent=2)
        except OSError as error:
            print(f"[WARN] Failed to persist my champions: {error}")
        self.refresh()
        self.app.update_banpick_recommendations()
