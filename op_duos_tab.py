import tkinter as tk
from tkinter import ttk
import json
from pathlib import Path
from common import LANES

HIGHLIGHT_WIN_RATE = 54.0
HIGHLIGHT_PICK_RATE = 2.0
HIGHLIGHT_MIN_GAMES = 900
HIGHLIGHT_LIMIT = 50

LANE_DISPLAY_NAMES = {
    "top": "탑",
    "jungle": "정글",
    "middle": "미드",
    "bottom": "바텀",
    "support": "서포터"
}

class OpDuosTab:
    def __init__(self, notebook, app_context, data_dir: Path):
        self.notebook = notebook
        self.app = app_context
        self.data_dir = data_dir
        
        self.tab = tk.Frame(self.notebook)
        self.notebook.add(self.tab, text="OP 조합")
        
        self.synergy_highlights = []
        self.highlight_tree = None
        self.highlight_pick_entry = None
        self.highlight_games_entry = None
        
        self._build_ui()

    def _build_ui(self):
        self.highlight_frame = tk.LabelFrame(self.tab, text="OP 듀오")
        self.highlight_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        tk.Button(
            self.highlight_frame,
            text="Reset Highlights",
            command=self.reset_highlights_tab
        ).pack(anchor="ne", padx=5, pady=(5, 0))

        # Lane selection row
        lane_row = tk.Frame(self.highlight_frame)
        lane_row.pack(fill="x", padx=5, pady=(5, 0))
        
        tk.Label(lane_row, text="나의 라인:").pack(side="left", padx=(0, 5))
        self.my_lane_var = tk.StringVar(value="bottom")
        my_lane_combo = ttk.Combobox(lane_row, textvariable=self.my_lane_var, values=LANES, state="readonly", width=10)
        my_lane_combo.pack(side="left", padx=(0, 15))
        my_lane_combo.bind("<<ComboboxSelected>>", lambda _e: self.populate_synergy_highlights())
        
        tk.Label(lane_row, text="함께할 라인:").pack(side="left", padx=(0, 5))
        self.partner_lane_var = tk.StringVar(value="support")
        partner_lane_combo = ttk.Combobox(lane_row, textvariable=self.partner_lane_var, values=LANES, state="readonly", width=10)
        partner_lane_combo.pack(side="left", padx=(0, 15))
        partner_lane_combo.bind("<<ComboboxSelected>>", lambda _e: self.populate_synergy_highlights())

        controls_row = tk.Frame(self.highlight_frame)
        controls_row.pack(fill="x", padx=5, pady=(5, 0))
        
        tk.Label(controls_row, text="Pick Rate ≥").pack(side="left")
        self.highlight_pick_entry = tk.Entry(controls_row, width=6)
        self.highlight_pick_entry.pack(side="left", padx=(2, 10))
        self.highlight_pick_entry.insert(0, str(HIGHLIGHT_PICK_RATE))
        
        tk.Label(controls_row, text="Games ≥").pack(side="left")
        self.highlight_games_entry = tk.Entry(controls_row, width=8)
        self.highlight_games_entry.pack(side="left", padx=(2, 10))
        self.highlight_games_entry.insert(0, str(HIGHLIGHT_MIN_GAMES))
        
        self.highlight_refresh_button = tk.Button(controls_row, text="Refresh", command=self.populate_synergy_highlights)
        self.highlight_refresh_button.pack(side="right")

        self.highlight_tree = ttk.Treeview(
            self.highlight_frame,
            columns=("Duo", "Win Rate", "Pick Rate", "Games"),
            show="headings",
            height=12
        )
        self.highlight_tree.heading("Duo", text="Duo")
        self.highlight_tree.heading("Win Rate", text="Win Rate")
        self.highlight_tree.heading("Pick Rate", text="Pick Rate")
        self.highlight_tree.heading("Games", text="Games")
        self.highlight_tree.column("Duo", width=260, anchor="w")
        self.highlight_tree.column("Win Rate", width=80, anchor="center")
        self.highlight_tree.column("Pick Rate", width=80, anchor="center")
        self.highlight_tree.column("Games", width=100, anchor="center")
        self.highlight_tree.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.populate_synergy_highlights()

    def populate_synergy_highlights(self):
        try:
            pick_rate_threshold = float(self.highlight_pick_entry.get())
        except ValueError:
            pick_rate_threshold = HIGHLIGHT_PICK_RATE
            self.highlight_pick_entry.delete(0, tk.END)
            self.highlight_pick_entry.insert(0, str(pick_rate_threshold))

        try:
            games_threshold = int(self.highlight_games_entry.get())
        except ValueError:
            games_threshold = HIGHLIGHT_MIN_GAMES
            self.highlight_games_entry.delete(0, tk.END)
            self.highlight_games_entry.insert(0, str(games_threshold))

        self.synergy_highlights = self.load_synergy_highlights(
            pick_rate_threshold,
            games_threshold
        )
        
        for item in self.highlight_tree.get_children():
            self.highlight_tree.delete(item)
            
        for entry in self.synergy_highlights:
            self.highlight_tree.insert(
                "",
                "end",
                values=(
                    entry["duo"],
                    f"{entry['win']:.2f}",
                    f"{entry['pick']:.2f}",
                    f"{entry['games']:,}"
                )
            )

    def load_synergy_highlights(self, pick_threshold, games_threshold):
        highlights = []
        if not self.data_dir.exists():
            return highlights

        my_lane = self.my_lane_var.get() if hasattr(self, "my_lane_var") else "bottom"
        partner_lane = self.partner_lane_var.get() if hasattr(self, "partner_lane_var") else "support"
        
        if not my_lane or my_lane not in LANES:
            my_lane = "bottom"
        if not partner_lane or partner_lane not in LANES:
            partner_lane = "support"
        
        if my_lane == partner_lane:
            return highlights

        # 나의 라인에 해당하는 데이터 파일 찾기
        lane_file_pattern = f"*_{my_lane}.json"
        for path in self.data_dir.glob(lane_file_pattern):
            try:
                with path.open("r", encoding="utf-8") as file:
                    payload = json.load(file)
            except (IOError, json.JSONDecodeError):
                continue

            stem = path.stem
            if stem.endswith(f"_{my_lane}"):
                stem = stem[:-(len(my_lane) + 1)]
                
            # Accessing app method
            if self.app.is_champion_ignored(stem):
                continue
                
            # Accessing app method
            my_champ_name = self.app.format_display_name(stem)

            # 함께할 라인의 시너지 데이터 가져오기
            partner_entries = payload.get("synergy", {}).get(partner_lane, {})
            for entry in partner_entries.values():
                partner_name = entry.get("Name") or entry.get("name")
                if not partner_name:
                    continue
                    
                # Accessing app method
                if self.app.is_champion_ignored(partner_name):
                    continue
                
                # Accessing app static methods (or methods)
                win_rate = self.app.parse_float(str(entry.get("win_rate", "")).replace("%", ""))
                pick_rate = self.app.parse_float(str(entry.get("pick_rate", "")).replace("%", ""))
                games = self.app.parse_int(entry.get("games"))

                if win_rate < HIGHLIGHT_WIN_RATE or pick_rate < pick_threshold or games < games_threshold:
                    continue

                highlights.append({
                    "duo": f"{my_champ_name} + {partner_name}",
                    "win": win_rate,
                    "pick": pick_rate,
                    "games": games
                })

        highlights.sort(key=lambda item: (item["win"], item["pick"]), reverse=True)
        return highlights[:HIGHLIGHT_LIMIT]

    def reset_highlights_tab(self):
        self.highlight_pick_entry.delete(0, tk.END)
        self.highlight_pick_entry.insert(0, str(HIGHLIGHT_PICK_RATE))
        self.highlight_games_entry.delete(0, tk.END)
        self.highlight_games_entry.insert(0, str(HIGHLIGHT_MIN_GAMES))
        self.populate_synergy_highlights()

    def reset_highlight_tree(self):
        if self.highlight_tree:
            for item in self.highlight_tree.get_children():
                self.highlight_tree.delete(item)

