import tkinter as tk
from tkinter import messagebox, ttk
import json
import os
import re
import sys
from pathlib import Path
from collections import defaultdict

LANES = ['top', 'jungle', 'middle', 'bottom', 'support']


def resolve_resource_path(*path_parts: str) -> str:
    relative_path = os.path.join(*path_parts)
    candidates = []

    if getattr(sys, 'frozen', False):
        executable_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(executable_dir, relative_path))

        mei_dir = getattr(sys, '_MEIPASS', None)
        if mei_dir:
            candidates.append(os.path.join(mei_dir, relative_path))

    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(script_dir, relative_path))
    candidates.append(os.path.abspath(relative_path))

    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if os.path.exists(candidate):
            return candidate

    return candidates[0]


ALIAS_FILE = resolve_resource_path("champion_aliases.json")
DATA_DIR = Path(resolve_resource_path("data"))
HIGHLIGHT_WIN_RATE = 54.0
HIGHLIGHT_PICK_RATE = 2.0
HIGHLIGHT_MIN_GAMES = 900
HIGHLIGHT_LIMIT = 50
COUNTER_LOW_GAMES_DEFAULT = 1500
SYNERGY_LOW_GAMES_DEFAULT = 1500
LOW_SAMPLE_COLOR = "#888888"
NORMAL_SAMPLE_COLOR = "#111111"
WARNING_ICON = "⚠"
BANPICK_DEFAULT_LANES = ['jungle', 'bottom', 'support', 'middle', 'top']
BANPICK_MIN_GAMES_DEFAULT = 900
BANPICK_PICK_RATE_OVERRIDE = 1.5
LANE_WEIGHT_DEEP = 1.0
LANE_WEIGHT_SHALLOW = 0.5
LANE_WEIGHT_DEFAULT = 0.3
LANE_WEIGHT_MAP = {
    'bottom': {
        'bottom': LANE_WEIGHT_DEEP,
        'support': LANE_WEIGHT_DEEP,
        'jungle': LANE_WEIGHT_SHALLOW,
        'middle': LANE_WEIGHT_DEFAULT,
        'top': LANE_WEIGHT_DEFAULT
    },
    'support': {
        'support': LANE_WEIGHT_DEEP,
        'bottom': LANE_WEIGHT_DEEP,
        'jungle': LANE_WEIGHT_SHALLOW,
        'middle': LANE_WEIGHT_SHALLOW,
        'top': LANE_WEIGHT_SHALLOW
    },
    'jungle': {
        'jungle': LANE_WEIGHT_DEEP,
        'middle': LANE_WEIGHT_DEEP,
        'top': LANE_WEIGHT_DEEP,
        'bottom': LANE_WEIGHT_SHALLOW,
        'support': LANE_WEIGHT_SHALLOW
    },
    'middle': {
        'middle': LANE_WEIGHT_DEEP,
        'jungle': LANE_WEIGHT_DEEP,
        'top': LANE_WEIGHT_SHALLOW,
        'bottom': LANE_WEIGHT_DEFAULT,
        'support': LANE_WEIGHT_SHALLOW
    },
    'top': {
        'top': LANE_WEIGHT_DEEP,
        'jungle': LANE_WEIGHT_DEEP,
        'middle': LANE_WEIGHT_SHALLOW,
        'bottom': LANE_WEIGHT_DEFAULT,
        'support': LANE_WEIGHT_SHALLOW
    }
}

CHOSEONG_LIST = [
    "ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ",
    "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"
]


def extract_choseong(text: str) -> str:
    choseong = []
    for char in text:
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3:
            index = (code - 0xAC00) // 588
            choseong.append(CHOSEONG_LIST[index])
        elif char.isalpha() or char.isdigit():
            choseong.append(char.lower())
    return "".join(choseong)


def alias_variants(alias: str, include_initials: bool = True) -> set[str]:
    variants = set()
    candidate = alias.strip()
    if not candidate:
        return variants

    lower_candidate = candidate.lower()
    variants.add(lower_candidate)

    alnum_only = re.sub(r"[^0-9a-z가-힣]", "", lower_candidate)
    if alnum_only:
        variants.add(alnum_only)

    hangul_prefix_match = re.match(r"^[가-힣]+", candidate)
    if hangul_prefix_match:
        hangul_prefix = hangul_prefix_match.group(0)
        variants.add(hangul_prefix.lower())

    initials = extract_choseong(candidate)
    if include_initials and initials:
        variants.add(initials.lower())

    return variants


def contains_hangul_syllable(text: str) -> bool:
    return any(0xAC00 <= ord(ch) <= 0xD7A3 for ch in text)


def load_alias_tables():
    if not os.path.exists(ALIAS_FILE):
        print(f"[WARN] Alias file not found at {ALIAS_FILE}")
    try:
        with open(ALIAS_FILE, "r", encoding="utf-8") as handle:
            alias_data = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        alias_data = {}

    canonical_lookup = {}
    alias_lookup = {}
    display_lookup = {}
    autocomplete_values = set()

    for canonical_name, aliases in alias_data.items():
        normalized = canonical_name.lower()
        canonical_lookup[normalized] = canonical_name

        canonical_title = canonical_name.title()
        autocomplete_values.add(canonical_title)

        display_value = canonical_name.title()
        if isinstance(aliases, list) and aliases:
            display_value = next((alias for alias in aliases if alias and alias[0].isascii()), display_value)
            for alias in aliases:
                if alias:
                    autocomplete_values.add(alias.strip())
                for variant in alias_variants(alias):
                    alias_lookup.setdefault(variant, canonical_name)

        for variant in alias_variants(canonical_name):
            alias_lookup.setdefault(variant, canonical_name)
        alias_lookup.setdefault(normalized, canonical_name)
        display_lookup[canonical_name] = display_value

    autocomplete_list = sorted(value for value in autocomplete_values if value)
    return canonical_lookup, alias_lookup, display_lookup, autocomplete_list


class AutocompletePopup:
    def __init__(self, entry_widget, values_provider, on_select=None, max_results=8):
        self.entry = entry_widget
        self.values_provider = values_provider
        self.on_select = on_select
        self.max_results = max_results
        self.popup = None
        self.listbox = None
        self.hide_job = None

        self.entry.bind("<KeyRelease>", self._on_key_release, add="+")
        self.entry.bind("<Down>", self._on_entry_down, add="+")
        self.entry.bind("<Up>", self._on_entry_up, add="+")
        self.entry.bind("<Return>", self._on_entry_return, add="+")
        self.entry.bind("<FocusOut>", self._on_focus_out, add="+")
        self.entry.bind("<Destroy>", self._on_destroy, add="+")
        self.entry.bind("<Escape>", self._on_escape, add="+")

    def _on_key_release(self, event):
        if event.keysym in {"Return", "Escape", "Up", "Down"}:
            return
        self.show_suggestions()

    def _on_focus_out(self, _event):
        self.entry.after(150, self.hide_popup)

    def _on_destroy(self, _event):
        self.hide_popup()

    def _on_escape(self, _event):
        self.hide_popup()

    def _on_entry_down(self, _event):
        if not self._is_popup_visible():
            self.show_suggestions()
        if not self._is_popup_visible():
            return
        self._move_selection(1)
        return "break"

    def _on_entry_up(self, _event):
        if not self._is_popup_visible():
            self.show_suggestions()
        if not self._is_popup_visible():
            return
        self._move_selection(-1)
        return "break"

    def _on_entry_return(self, _event):
        if self._is_popup_visible():
            if self._apply_selection():
                return "break"
            return
        if self._apply_single_match():
            return "break"

    def show_suggestions(self):
        query = self.entry.get().strip()
        if not query:
            self.hide_popup()
            return

        matches = self._filter_matches(query)
        if not matches:
            self.hide_popup()
            return

        self._ensure_popup()
        self._update_listbox(matches)
        self._place_popup()

    def _filter_matches(self, query):
        lowered = query.lower()
        prefix_matches = []
        word_matches = []
        substring_matches = []

        def add_unique(bucket, value):
            if value not in bucket:
                bucket.append(value)

        for value in self.values_provider():
            candidate = value.lower()
            if candidate.startswith(lowered):
                add_unique(prefix_matches, value)
                continue

            words = re.split(r"[\s\-/]+", candidate)
            if any(word.startswith(lowered) for word in words if word):
                add_unique(word_matches, value)
                continue

            if len(lowered) >= 2 and lowered in candidate:
                add_unique(substring_matches, value)

            if len(prefix_matches) + len(word_matches) >= self.max_results:
                break

        combined = prefix_matches + word_matches
        if len(combined) < self.max_results:
            combined.extend(substring_matches)
        return combined[:self.max_results]

    def _ensure_popup(self):
        if self.popup and self.popup.winfo_exists():
            return

        self.popup = tk.Toplevel(self.entry)
        self.popup.wm_overrideredirect(True)
        self.popup.attributes("-topmost", True)

        self.listbox = tk.Listbox(self.popup, selectmode=tk.SINGLE)
        self.listbox.pack(fill="both", expand=True)
        self.listbox.bind("<ButtonRelease-1>", self._on_listbox_click)
        self.listbox.bind("<Return>", self._on_listbox_return)
        self.listbox.bind("<Escape>", lambda _: self.hide_popup())

    def _update_listbox(self, matches):
        self.listbox.delete(0, tk.END)
        for match in matches:
            self.listbox.insert(tk.END, match)
        self.listbox.select_set(0)
        self.listbox.activate(0)

    def _place_popup(self):
        if not self.popup:
            return
        self.popup.update_idletasks()
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        width = self.entry.winfo_width()
        height = min(self.listbox.size(), self.max_results) * 24 or 24
        self.popup.geometry(f"{width}x{height}+{x}+{y}")
        self.popup.deiconify()

    def _on_listbox_click(self, _event):
        self._apply_selection()

    def _on_listbox_return(self, _event):
        self._apply_selection()
        return "break"

    def _apply_selection(self):
        if not self.listbox:
            return False
        selection = self.listbox.curselection()
        if not selection:
            return False
        value = self.listbox.get(selection[0])
        return self._apply_value(value)

    def _apply_value(self, value):
        if not value:
            return False
        self.entry.delete(0, tk.END)
        self.entry.insert(0, value)
        self.entry.icursor(tk.END)
        self.entry.focus_set()
        self.hide_popup()
        if self.on_select:
            self.on_select(value)
        return True

    def _apply_single_match(self):
        query = self.entry.get().strip()
        if not query:
            return False
        unique = self.get_unique_match(query)
        if not unique:
            return False
        return self._apply_value(unique)

    def get_unique_match(self, query):
        if not query:
            return None
        matches = self._filter_matches(query)
        if len(matches) == 1:
            return matches[0]
        return None

    def _move_selection(self, offset):
        if not self.listbox:
            return
        size = self.listbox.size()
        if size == 0:
            return
        selection = self.listbox.curselection()
        index = selection[0] if selection else -1
        index = (index + offset) % size
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(index)
        self.listbox.activate(index)
        self.listbox.see(index)

    def _is_popup_visible(self):
        return bool(self.popup and self.popup.winfo_exists())

    def hide_popup(self):
        if self.popup and self.popup.winfo_exists():
            self.popup.destroy()
        self.popup = None
        self.listbox = None


class ChampionScraperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Champion Ban/Pick Helper")
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.notebook = ttk.Notebook(root)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.dashboard_tab = tk.Frame(self.notebook)
        self.notebook.add(self.dashboard_tab, text="Champion Picker")
        self.main_tab = tk.Frame(self.notebook)
        self.main_tab.grid_rowconfigure(6, weight=1)
        self.main_tab.grid_columnconfigure(5, weight=1)
        tk.Button(
            self.main_tab,
            text="Reset Main",
            command=self.reset_main_tab
        ).grid(row=0, column=3, sticky="e", padx=5, pady=5)
        self.notebook.add(self.main_tab, text="Counter & Synergy")
        self.all_data = {lane: {} for lane in LANES}
        self.synergy_data = {lane: {} for lane in LANES}
        (
            self.canonical_lookup,
            self.alias_lookup,
            self.display_lookup,
            self.autocomplete_candidates
        ) = load_alias_tables()
        self.counter_cache = {}
        self.synergy_cache = {}
        self.counter_listbox_map = {}
        self.synergy_listbox_map = {}
        self.synergy_highlights = []
        self.counter_typing_after_id = None
        self.synergy_typing_after_id = None
        self._lane_swap_guard = False

        # Counter controls
        self.counter_section = tk.LabelFrame(self.main_tab, text="Counter")
        self.counter_section.grid(row=1, column=0, columnspan=4, sticky="ew", padx=5, pady=(10, 0))
        self.counter_section.grid_columnconfigure(0, weight=1)
        self.counter_section.grid_columnconfigure(1, weight=1)
        self.counter_section.grid_columnconfigure(2, weight=0)
        self.counter_section.grid_columnconfigure(3, weight=0)

        self.name_entry = tk.Entry(self.counter_section, width=20)
        self.name_entry.grid(row=0, column=0, sticky="ew")
        self.name_entry.bind("<KeyRelease>", self.on_counter_input_changed)

        self.lane_combobox = ttk.Combobox(self.counter_section, values=LANES, state="readonly", width=10)
        self.lane_combobox.grid(row=0, column=1, sticky="ew")
        self.lane_combobox.set("Select Lane")
        self.lane_combobox.bind("<<ComboboxSelected>>", self.on_counter_lane_selected)

        self.search_button = tk.Button(self.counter_section, text="Load Counter", command=self.start_search)
        self.search_button.grid(row=0, column=2, sticky="ew")
        self.root.bind('<Return>', lambda _: self.start_search())

        self.counter_auto_load_var = tk.BooleanVar(value=True)
        self.counter_auto_check = tk.Checkbutton(
            self.counter_section,
            text="Auto Load",
            variable=self.counter_auto_load_var,
            command=self.on_counter_auto_toggle
        )
        self.counter_auto_check.grid(row=0, column=3, sticky="w", padx=(5, 0))
        self.counter_autocomplete = AutocompletePopup(
            self.name_entry,
            self.get_autocomplete_candidates,
            on_select=lambda _value: self.on_autocomplete_selection("counter")
        )

        tk.Label(self.counter_section, text="Loaded Counters:").grid(row=1, column=0, columnspan=2, sticky="wn")
        self.champion_listbox = tk.Listbox(self.counter_section, height=7)
        self.champion_listbox.grid(row=1, column=0, columnspan=2, sticky="wn", pady=25)
        self.champion_listbox.bind("<<ListboxSelect>>", self.on_counter_select)

        tk.Label(self.counter_section, text="Filter Data by Popularity:").grid(row=1, column=1, columnspan=2, sticky="wn")
        self.popularity_entry = tk.Entry(self.counter_section, width=17)
        self.popularity_entry.grid(row=1, column=1, columnspan=2, sticky="wn", pady=26)
        self.popularity_entry.insert(0, "1")

        self.filter_button = tk.Button(self.counter_section, text="Filter", command=self.filter_by_popularity)
        self.filter_button.grid(row=1, column=1, columnspan=2, sticky="ne", pady=25)

        self.counter_reliability_frame = tk.LabelFrame(self.counter_section, text="데이터 신뢰도")
        self.counter_reliability_frame.grid(row=2, column=0, columnspan=4, sticky="ew", padx=5, pady=(0, 5))
        tk.Label(self.counter_reliability_frame, text="최소 게임 수").grid(row=0, column=0, sticky="w")
        self.counter_min_games_entry = tk.Entry(self.counter_reliability_frame, width=10)
        self.counter_min_games_entry.grid(row=0, column=1, padx=(5, 10), sticky="w")
        self.counter_min_games_entry.insert(0, str(COUNTER_LOW_GAMES_DEFAULT))
        self.counter_min_games_entry.bind("<KeyRelease>", self.on_counter_threshold_change)
        self.counter_min_games_entry.bind("<FocusOut>", self.on_counter_threshold_change)
        tk.Label(
            self.counter_reliability_frame,
            text=f"{WARNING_ICON} 회색 = 데이터 부족"
        ).grid(row=0, column=2, sticky="w")

        self.lane_filter_frame = tk.LabelFrame(self.counter_section, text="Lane Filters")
        self.lane_filter_frame.grid(row=3, column=0, columnspan=4, sticky="ew", padx=5, pady=(0, 10))

        self.lane_vars = {}
        for idx, lane in enumerate(LANES):
            var = tk.BooleanVar(value=True)
            self.lane_vars[lane] = var
            checkbox = tk.Checkbutton(
                self.lane_filter_frame,
                text=lane.capitalize(),
                variable=var,
                command=self.update_lane_visibility
            )
            checkbox.grid(row=0, column=idx, padx=4, sticky="w")

        style = ttk.Style()
        style.configure('Treeview', rowheight=15)

        # Create Treeview for each lane
        self.treeviews = {}
        self.lane_frames = {}
        for lane in LANES:
            frame = tk.Frame(self.main_tab)
            tk.Label(frame, text=f"{lane.capitalize()} Counter:").pack(anchor="w")
            tree = ttk.Treeview(frame, columns=("Name", "Popularity", "Win Rate"), show='headings')
            tree.pack(expand=True, fill='both')
            tree.heading("Name", text="Name")
            tree.heading("Popularity", text="Popularity")
            tree.heading("Win Rate", text="Win Rate")
            tree.tag_configure("low_games", foreground=LOW_SAMPLE_COLOR)
            tree.tag_configure("normal_games", foreground=NORMAL_SAMPLE_COLOR)
            self.treeviews[lane] = tree
            self.lane_frames[lane] = frame

        self.update_lane_visibility()

        # Synergy controls
        self.synergy_section = tk.LabelFrame(self.main_tab, text="Ally Synergy")
        self.synergy_section.grid(row=3, column=0, columnspan=4, sticky="ew", padx=5, pady=(10, 0))
        self.synergy_section.grid_columnconfigure(0, weight=1)
        self.synergy_section.grid_columnconfigure(1, weight=1)
        self.synergy_section.grid_columnconfigure(2, weight=0)
        self.synergy_section.grid_columnconfigure(3, weight=0)

        self.ally_name_entry = tk.Entry(self.synergy_section, width=20)
        self.ally_name_entry.grid(row=0, column=0, sticky="ew")
        self.ally_name_entry.bind("<KeyRelease>", self.on_synergy_input_changed)

        self.ally_lane_combobox = ttk.Combobox(self.synergy_section, values=LANES, state="readonly", width=10)
        self.ally_lane_combobox.grid(row=0, column=1, sticky="ew")
        self.ally_lane_combobox.set("Select Lane")
        self.ally_lane_combobox.bind("<<ComboboxSelected>>", self.on_synergy_lane_selected)

        self.ally_search_button = tk.Button(self.synergy_section, text="Load Synergy", command=self.start_synergy_search)
        self.ally_search_button.grid(row=0, column=2, sticky="ew", padx=(5, 0))

        self.synergy_auto_load_var = tk.BooleanVar(value=True)
        self.synergy_auto_check = tk.Checkbutton(
            self.synergy_section,
            text="Auto Load",
            variable=self.synergy_auto_load_var,
            command=self.on_synergy_auto_toggle
        )
        self.synergy_auto_check.grid(row=0, column=3, sticky="w")
        self.synergy_autocomplete = AutocompletePopup(
            self.ally_name_entry,
            self.get_autocomplete_candidates,
            on_select=lambda _value: self.on_autocomplete_selection("synergy")
        )

        tk.Label(self.synergy_section, text="Loaded Synergy:").grid(row=1, column=0, columnspan=2, sticky="wn", pady=5)
        self.synergy_listbox = tk.Listbox(self.synergy_section, height=7)
        self.synergy_listbox.grid(row=1, column=0, columnspan=2, sticky="wn", pady=25)
        self.synergy_listbox.bind("<<ListboxSelect>>", self.on_synergy_select)

        tk.Label(self.synergy_section, text="Filter Synergy by Pick Rate:").grid(row=1, column=1, columnspan=2, sticky="wn")
        self.synergy_pick_rate_entry = tk.Entry(self.synergy_section, width=17)
        self.synergy_pick_rate_entry.grid(row=1, column=1, columnspan=2, sticky="wn", pady=26)
        self.synergy_pick_rate_entry.insert(0, "2")

        self.synergy_filter_button = tk.Button(self.synergy_section, text="Filter", command=self.filter_synergy)
        self.synergy_filter_button.grid(row=1, column=1, columnspan=2, sticky="ne", pady=25)

        self.synergy_reliability_frame = tk.LabelFrame(self.synergy_section, text="데이터 신뢰도")
        self.synergy_reliability_frame.grid(row=2, column=0, columnspan=4, sticky="ew", padx=5, pady=(0, 5))
        tk.Label(self.synergy_reliability_frame, text="최소 게임 수").grid(row=0, column=0, sticky="w")
        self.synergy_min_games_entry = tk.Entry(self.synergy_reliability_frame, width=10)
        self.synergy_min_games_entry.grid(row=0, column=1, padx=(5, 10), sticky="w")
        self.synergy_min_games_entry.insert(0, str(SYNERGY_LOW_GAMES_DEFAULT))
        self.synergy_min_games_entry.bind("<KeyRelease>", self.on_synergy_threshold_change)
        self.synergy_min_games_entry.bind("<FocusOut>", self.on_synergy_threshold_change)
        tk.Label(
            self.synergy_reliability_frame,
            text=f"{WARNING_ICON} 회색 = 데이터 부족"
        ).grid(row=0, column=2, sticky="w")

        self.synergy_lane_filter_frame = tk.LabelFrame(self.synergy_section, text="Synergy Lanes")
        self.synergy_lane_filter_frame.grid(row=3, column=0, columnspan=4, sticky="ew", padx=5, pady=(0, 10))

        self.synergy_lane_vars = {}
        for idx, lane in enumerate(LANES):
            var = tk.BooleanVar(value=True)
            self.synergy_lane_vars[lane] = var
            checkbox = tk.Checkbutton(
                self.synergy_lane_filter_frame,
                text=lane.capitalize(),
                variable=var,
                command=self.update_synergy_visibility
            )
            checkbox.grid(row=0, column=idx, padx=4, sticky="w")

        self.synergy_treeviews = {}
        self.synergy_frames = {}
        for lane in LANES:
            frame = tk.Frame(self.main_tab)
            tk.Label(frame, text=f"{lane.capitalize()} Synergy:").pack(anchor="w")
            tree = ttk.Treeview(frame, columns=("Name", "Pick Rate", "Win Rate"), show='headings')
            tree.pack(expand=True, fill='both')
            tree.heading("Name", text="Name")
            tree.heading("Pick Rate", text="Pick Rate")
            tree.heading("Win Rate", text="Win Rate")
            tree.tag_configure("low_games", foreground=LOW_SAMPLE_COLOR)
            tree.tag_configure("normal_games", foreground=NORMAL_SAMPLE_COLOR)
            self.synergy_treeviews[lane] = tree
            self.synergy_frames[lane] = frame

        self.update_synergy_visibility()
        self.build_dashboard_tab()
        self.build_highlights_tab()

    def build_dashboard_tab(self):
        self.banpick_slots = {"allies": [], "enemies": []}
        self.active_slot_var = tk.StringVar(value="")
        self.active_slot_var.trace_add("write", lambda *_: self.update_banpick_recommendations())
        container = tk.Frame(self.dashboard_tab)
        container.pack(fill="both", expand=True, padx=10, pady=10)
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)

        tk.Button(
            self.dashboard_tab,
            text="Reset Dashboard",
            command=self.reset_dashboard_tab
        ).pack(anchor="ne", padx=10, pady=(5, 0))

        left_column = self._create_banpick_column(container, "(Blue Side)", "allies")
        left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right_column = self._create_banpick_column(container, "(Red Side)", "enemies")
        right_column.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        recommend_frame = tk.LabelFrame(self.dashboard_tab, text="추천 챔피언")
        recommend_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        filter_frame = tk.Frame(recommend_frame)
        filter_frame.pack(fill="x", padx=5, pady=(5, 0))
        tk.Label(filter_frame, text="Min Games").pack(side="left")
        self.recommend_min_games_entry = tk.Entry(filter_frame, width=6)
        self.recommend_min_games_entry.insert(0, str(BANPICK_MIN_GAMES_DEFAULT))
        self.recommend_min_games_entry.pack(side="left", padx=(4, 0))
        self.recommend_min_games_entry.bind("<KeyRelease>", lambda _e: self.update_banpick_recommendations())
        self.recommend_min_games_entry.bind("<FocusOut>", lambda _e: self.update_banpick_recommendations())

        tk.Label(filter_frame, text="Pick Rate ≥").pack(side="left", padx=(10, 0))
        self.recommend_pick_rate_entry = tk.Entry(filter_frame, width=6)
        self.recommend_pick_rate_entry.insert(0, str(BANPICK_PICK_RATE_OVERRIDE))
        self.recommend_pick_rate_entry.pack(side="left", padx=(4, 0))
        self.recommend_pick_rate_entry.bind("<KeyRelease>", lambda _e: self.update_banpick_recommendations())
        self.recommend_pick_rate_entry.bind("<FocusOut>", lambda _e: self.update_banpick_recommendations())

        columns = ("Champion", "Score", "Synergy", "Counter")
        self.recommend_tree = ttk.Treeview(recommend_frame, columns=columns, show="headings", height=8)
        for col in columns:
            self.recommend_tree.heading(col, text=col)
            self.recommend_tree.column(col, anchor="center")
        self.recommend_tree.column("Champion", anchor="w", width=180)
        self.recommend_tree.column("Score", width=80)
        self.recommend_tree.column("Synergy", width=80)
        self.recommend_tree.column("Counter", width=80)
        scroll = tk.Scrollbar(recommend_frame, orient="vertical", command=self.recommend_tree.yview)
        scroll.pack(side="right", fill="y")
        self.recommend_tree.configure(yscrollcommand=scroll.set)
        self.recommend_tree.pack(fill="both", expand=True)

    def build_highlights_tab(self):
        if hasattr(self, "highlight_tab"):
            return
        self.highlight_tab = tk.Frame(self.notebook)
        self.notebook.add(self.highlight_tab, text="OP Duos")

        self.highlight_frame = tk.LabelFrame(self.highlight_tab, text="Top Bot Lane Duos")
        self.highlight_frame.pack(fill="both", expand=True, padx=10, pady=10)
        tk.Button(
            self.highlight_frame,
            text="Reset Highlights",
            command=self.reset_highlights_tab
        ).pack(anchor="ne", padx=5, pady=(5, 0))

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

    def _create_banpick_column(self, parent, title, side_key):
        column = tk.LabelFrame(parent, text=title)
        for idx in range(5):
            slot_frame = tk.Frame(column, bd=1, relief="groove", padx=6, pady=6)
            slot_frame.pack(fill="x", pady=4)

            tk.Label(slot_frame, text=f"Slot {idx + 1}", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
            clear_button = tk.Button(slot_frame, text="Clear", width=6)
            clear_button.grid(row=0, column=2, padx=(6, 0), sticky="e")
            active_check = tk.Checkbutton(
                slot_frame,
                text="내 차례",
                variable=self.active_slot_var,
                onvalue=f"{side_key}:{idx}",
                offvalue=""
            )
            active_check.grid(row=0, column=3, sticky="e")

            entry = tk.Entry(slot_frame, width=18)
            entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 2))

            lane_box = ttk.Combobox(slot_frame, values=LANES, state="readonly", width=12)
            lane_box.grid(row=1, column=2, padx=(6, 0), pady=(4, 2))
            if idx < len(BANPICK_DEFAULT_LANES):
                lane_box.set(BANPICK_DEFAULT_LANES[idx])
            else:
                lane_box.set("Select Lane")

            search_button = tk.Button(slot_frame, text="검색", width=6)
            search_button.grid(row=1, column=3, padx=(6, 0))

            result_var = tk.StringVar(value="검색 결과 없음")
            result_label = tk.Label(slot_frame, textvariable=result_var, anchor="w")
            result_label.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(6, 0))

            slot = {
                "side": side_key,
                "index": idx,
                "entry": entry,
                "lane": lane_box,
                "button": search_button,
                "clear_button": clear_button,
                "result_var": result_var,
                "active_check": active_check,
                "display_name": None,
                "canonical_name": None,
                "selected_lane": None,
                "synergy_dataset": None,
                "counter_dataset": None,
                "last_lane_value": None,
                "last_lane": None
            }

            search_button.configure(command=lambda s=slot: self.perform_banpick_search(s))
            entry.bind("<Return>", lambda event, s=slot: self.perform_banpick_search(s))
            lane_box.bind("<<ComboboxSelected>>", lambda _event, s=slot: self.on_banpick_lane_changed(s))
            clear_button.configure(command=lambda s=slot: self.clear_banpick_slot(s))

            slot["autocomplete"] = AutocompletePopup(
                entry,
                self.get_autocomplete_candidates,
                on_select=lambda _value, s=slot: self.perform_banpick_search(s, auto_trigger=True)
            )

            self._update_slot_lane_cache(slot)
            self.banpick_slots[side_key].append(slot)

        return column

    def _update_slot_lane_cache(self, slot, lane_value=None):
        if not slot:
            return
        lane_text = lane_value
        if lane_text is None:
            lane_widget = slot.get("lane")
            if lane_widget:
                lane_text = lane_widget.get()
        slot["last_lane_value"] = lane_text
        if isinstance(lane_text, str):
            lowered = lane_text.lower()
            slot["last_lane"] = lowered if lowered in LANES else None
        else:
            slot["last_lane"] = None

    def on_banpick_lane_changed(self, slot):
        if not slot or self._lane_swap_guard:
            return
        lane_box = slot.get("lane")
        if not lane_box:
            return
        new_value = lane_box.get()
        previous_value = slot.get("last_lane_value")
        if previous_value == new_value:
            return

        self._update_slot_lane_cache(slot, new_value)
        new_lane = slot.get("last_lane")
        if not new_lane:
            self.update_banpick_recommendations()
            return

        side_key = slot.get("side")
        if not side_key or side_key not in self.banpick_slots:
            self.update_banpick_recommendations()
            return

        swap_target = None
        for other in self.banpick_slots.get(side_key, []):
            if other is slot:
                continue
            other_box = other.get("lane")
            if not other_box:
                continue
            other_value = other_box.get()
            other_lane = other_value.lower() if isinstance(other_value, str) else ""
            if other_lane == new_lane:
                swap_target = other
                break

        if swap_target and previous_value is not None:
            swap_box = swap_target.get("lane")
            if swap_box:
                self._lane_swap_guard = True
                try:
                    swap_box.set(previous_value)
                finally:
                    self._lane_swap_guard = False
                self._update_slot_lane_cache(swap_target, previous_value)
            current_active = self.active_slot_var.get()
            slot_key = f"{side_key}:{slot.get('index')}"
            target_key = f"{side_key}:{swap_target.get('index')}"
            if current_active == target_key:
                self.active_slot_var.set(slot_key)
            elif current_active == slot_key:
                self.active_slot_var.set(target_key)

        self.update_banpick_recommendations()

    def clear_banpick_slot(self, slot, reset_lane=False, suppress_update=False):
        if not slot:
            return
        entry = slot.get("entry")
        lane_box = slot.get("lane")
        result_var = slot.get("result_var")
        if entry:
            entry.delete(0, tk.END)
        if reset_lane and lane_box:
            idx = slot.get("index", 0)
            if idx < len(BANPICK_DEFAULT_LANES):
                lane_box.set(BANPICK_DEFAULT_LANES[idx])
            else:
                lane_box.set("Select Lane")
            self._update_slot_lane_cache(slot)
        if result_var:
            result_var.set("검색 결과 없음")
        slot["display_name"] = None
        slot["canonical_name"] = None
        slot["selected_lane"] = None
        slot["synergy_dataset"] = None
        slot["counter_dataset"] = None
        if not suppress_update:
            self.update_banpick_recommendations()

    def on_counter_input_changed(self, _event=None):
        if not self.counter_auto_load_var.get():
            return
        self.schedule_counter_auto_load()

    def on_counter_lane_selected(self, _event=None):
        if self.counter_auto_load_var.get():
            self.schedule_counter_auto_load(delay=0)

    def on_counter_auto_toggle(self):
        if self.counter_auto_load_var.get():
            self.schedule_counter_auto_load(delay=0)
        elif self.counter_typing_after_id is not None:
            self.root.after_cancel(self.counter_typing_after_id)
            self.counter_typing_after_id = None

    def schedule_counter_auto_load(self, delay=400):
        if self.counter_typing_after_id is not None:
            self.root.after_cancel(self.counter_typing_after_id)
            self.counter_typing_after_id = None

        if not self.counter_auto_load_var.get():
            return

        self.counter_typing_after_id = self.root.after(delay, self._try_auto_counter_load)

    def _try_auto_counter_load(self):
        self.counter_typing_after_id = None

        if not self.counter_auto_load_var.get():
            return

        champion_name = self.name_entry.get().strip()
        if not champion_name:
            return

        selected_lane = self.lane_combobox.get().lower()
        if selected_lane not in LANES:
            return

        self.start_search(auto_trigger=True)

    def on_synergy_input_changed(self, _event=None):
        if not self.synergy_auto_load_var.get():
            return
        self.schedule_synergy_auto_load()

    def on_synergy_lane_selected(self, _event=None):
        if self.synergy_auto_load_var.get():
            self.schedule_synergy_auto_load(delay=0)

    def on_synergy_auto_toggle(self):
        if self.synergy_auto_load_var.get():
            self.schedule_synergy_auto_load(delay=0)
        elif self.synergy_typing_after_id is not None:
            self.root.after_cancel(self.synergy_typing_after_id)
            self.synergy_typing_after_id = None

    def schedule_synergy_auto_load(self, delay=400):
        if self.synergy_typing_after_id is not None:
            self.root.after_cancel(self.synergy_typing_after_id)
            self.synergy_typing_after_id = None

        if not self.synergy_auto_load_var.get():
            return

        self.synergy_typing_after_id = self.root.after(delay, self._try_auto_synergy_load)

    def _try_auto_synergy_load(self):
        self.synergy_typing_after_id = None

        if not self.synergy_auto_load_var.get():
            return

        champion_name = self.ally_name_entry.get().strip()
        if not champion_name:
            return

        selected_lane = self.ally_lane_combobox.get().lower()
        if selected_lane not in LANES:
            return

        self.start_synergy_search(auto_trigger=True)

    def get_autocomplete_candidates(self):
        return self.autocomplete_candidates

    def on_autocomplete_selection(self, context):
        if context == "counter":
            if self.counter_auto_load_var.get():
                self.schedule_counter_auto_load(delay=0)
        elif context == "synergy":
            if self.synergy_auto_load_var.get():
                self.schedule_synergy_auto_load(delay=0)

    def perform_banpick_search(self, slot, auto_trigger=False):
        if not slot:
            return
        entry_widget = slot.get("entry")
        lane_box = slot.get("lane")
        result_var = slot.get("result_var")
        if not entry_widget or not lane_box or not result_var:
            return

        champion_name = entry_widget.get().strip()
        if not champion_name:
            if not auto_trigger:
                messagebox.showerror("Error", "챔피언 이름을 입력하세요.")
            return

        lane = lane_box.get().lower()
        if lane not in LANES:
            if not auto_trigger:
                messagebox.showerror("Error", "라인을 선택하세요.")
            return

        full_name = self.resolve_champion_name(champion_name)
        if not full_name:
            autocomplete = slot.get("autocomplete")
            if autocomplete:
                unique_match = autocomplete.get_unique_match(champion_name)
                if unique_match:
                    entry_widget.delete(0, tk.END)
                    entry_widget.insert(0, unique_match)
                    entry_widget.icursor(tk.END)
                    champion_name = unique_match.strip()
                    full_name = self.resolve_champion_name(champion_name)
        if not full_name:
            if not auto_trigger:
                messagebox.showerror("Error", f"Champion name '{champion_name}' not found.")
            return

        display_name = self.display_lookup.get(full_name, full_name.title())

        synergy_dataset = None
        counter_dataset = None

        synergy_dataset, _, _ = self._load_lane_dataset(
            full_name,
            lane,
            "Synergy",
            "synergy",
            self.sanitize_synergy_entry,
            suppress_errors=True
        )
        counter_dataset, _, _ = self._load_lane_dataset(
            full_name,
            lane,
            "Counter",
            "counters",
            self.sanitize_counter_entry,
            suppress_errors=True
        )

        slot["display_name"] = display_name
        slot["canonical_name"] = full_name
        slot["selected_lane"] = lane
        slot["synergy_dataset"] = synergy_dataset
        slot["counter_dataset"] = counter_dataset
        result_var.set(f"{display_name} ({lane})")

        if not auto_trigger:
            entry_widget.delete(0, tk.END)

        self.update_banpick_recommendations()

    def update_banpick_recommendations(self):
        tree = getattr(self, "recommend_tree", None)
        if not tree:
            return
        for item in tree.get_children():
            tree.delete(item)

        active_key = self.active_slot_var.get()
        if not active_key:
            return
        try:
            side_key, idx_str = active_key.split(":")
            idx = int(idx_str)
        except ValueError:
            return

        side_slots = self.banpick_slots.get(side_key)
        if not side_slots or not (0 <= idx < len(side_slots)):
            return
        target_slot = side_slots[idx]
        target_lane = target_slot.get("lane").get().lower()
        if target_lane not in LANES:
            return

        scores = {}
        pick_rate_override = (
            self.parse_float(self.recommend_pick_rate_entry.get())
            if hasattr(self, "recommend_pick_rate_entry") else BANPICK_PICK_RATE_OVERRIDE
        )
        if pick_rate_override < 0:
            pick_rate_override = 0.0

        def ensure_score_entry(champion):
            entry = scores.get(champion)
            if entry is None:
                entry = {
                    "synergy_sum": 0.0,
                    "synergy_count": 0,
                    "counter_sum": 0.0,
                    "counter_count": 0,
                    "synergy_sources": [],
                    "counter_sources": [],
                    "has_low_sample": False,
                    "has_low_pick_gap": False
                }
                scores[champion] = entry
            return entry

        def should_use_entry(details):
            games = self.parse_int(details.get("games"))
            pick_rate_value = 0.0
            if "pick_rate" in details:
                pick_rate_value = self.parse_float(details.get("pick_rate"))
            elif "popularity" in details:
                pick_rate_value = self.parse_float(details.get("popularity"))
            meets_games_requirement = games >= min_games
            meets_pick_rate_override = pick_rate_value >= pick_rate_override
            include_entry = meets_games_requirement or meets_pick_rate_override
            low_sample = not meets_games_requirement
            penalized_pick = (not include_entry) and (not meets_pick_rate_override)
            return include_entry, low_sample, penalized_pick
        selected_lowers = set()
        for slot_list in self.banpick_slots.values():
            for s in slot_list:
                name = s.get("display_name")
                canon = s.get("canonical_name")
                if name:
                    selected_lowers.add(name.lower())
                if canon:
                    selected_lowers.add(canon.lower())

        min_games = self.parse_int(self.recommend_min_games_entry.get()) if hasattr(self, "recommend_min_games_entry") else BANPICK_MIN_GAMES_DEFAULT
        if min_games < 0:
            min_games = 0

        # Synergy contributions from same side
        for friend in self.banpick_slots.get(side_key, []):
            dataset = friend.get("synergy_dataset")
            if not dataset:
                continue
            source_lane = friend.get("selected_lane")
            lane_entries = dataset.get(target_lane, {})
            for champ_name, details in lane_entries.items():
                include_entry, low_sample, penalized_pick = should_use_entry(details)
                if penalized_pick:
                    components = ensure_score_entry(champ_name)
                    components["has_low_pick_gap"] = True
                if not include_entry:
                    continue
                value = self.parse_float(details.get("win_rate"))
                weight = self.get_lane_weight(target_lane, source_lane)
                if weight <= 0:
                    continue
                components = ensure_score_entry(champ_name)
                components["synergy_sum"] += value * weight
                components["synergy_count"] += 1
                if low_sample:
                    components["has_low_sample"] = True
                source_name = friend.get("display_name") or friend.get("canonical_name") or "Unknown"
                label = f"{source_name}({value:.2f})"
                if low_sample:
                    label = f"{WARNING_ICON} {label}"
                components["synergy_sources"].append(label)

        # Counter contributions from opposing side
        opponent_side = "enemies" if side_key == "allies" else "allies"
        for enemy in self.banpick_slots.get(opponent_side, []):
            dataset = enemy.get("counter_dataset")
            if not dataset:
                continue
            source_lane = enemy.get("selected_lane")
            lane_entries = dataset.get(target_lane, {})
            for champ_name, details in lane_entries.items():
                include_entry, low_sample, penalized_pick = should_use_entry(details)
                if penalized_pick:
                    components = ensure_score_entry(champ_name)
                    components["has_low_pick_gap"] = True
                if not include_entry:
                    continue
                win_rate_value = self.parse_float(details.get("win_rate"))
                value = 100.0 - win_rate_value
                weight = self.get_lane_weight(target_lane, source_lane)
                if weight <= 0:
                    continue
                components = ensure_score_entry(champ_name)
                components["counter_sum"] += value * weight
                components["counter_count"] += 1
                if low_sample:
                    components["has_low_sample"] = True
                source_name = enemy.get("display_name") or enemy.get("canonical_name") or "Unknown"
                label = f"{source_name}({win_rate_value:.2f})"
                if low_sample:
                    label = f"{WARNING_ICON} {label}"
                components["counter_sources"].append(label)

        recommendations = []

        for champ_name, components in scores.items():
            if champ_name.lower() in selected_lowers:
                continue
            if components["has_low_pick_gap"]:
                continue
            synergy_score = (
                components["synergy_sum"] / components["synergy_count"]
                if components["synergy_count"] > 0 else 0.0
            )
            counter_score = (
                components["counter_sum"] / components["counter_count"]
                if components["counter_count"] > 0 else 0.0
            )
            total = synergy_score + counter_score
            if total == 0:
                continue
            recommendations.append((
                champ_name,
                total,
                synergy_score,
                counter_score,
                components["synergy_sources"],
                components["counter_sources"],
                components["has_low_sample"]
            ))

        recommendations.sort(key=lambda item: item[1], reverse=True)
        for champ_name, total, synergy_score, counter_score, synergy_sources, counter_sources, has_low_sample in recommendations[:20]:
            display_name = f"{WARNING_ICON} {champ_name}" if has_low_sample else champ_name
            synergy_label = " / ".join(synergy_sources) if synergy_sources else "-"
            counter_label = " / ".join(counter_sources) if counter_sources else "-"
            tree.insert(
                "",
                "end",
                values=(
                    display_name,
                    f"{total:.2f}",
                    synergy_label,
                    counter_label
                )
            )

    def get_lane_weight(self, target_lane, source_lane):
        if not target_lane or not source_lane:
            return LANE_WEIGHT_DEFAULT
        mapping = LANE_WEIGHT_MAP.get(target_lane, {})
        return mapping.get(source_lane, LANE_WEIGHT_DEFAULT)

    def on_counter_threshold_change(self, _event=None):
        self.update_GUI()

    def on_synergy_threshold_change(self, _event=None):
        self.update_synergy_GUI()

    def start_search(self, auto_trigger=False):
        champion_name = self.name_entry.get()
        selected_lane = self.lane_combobox.get().lower()

        if selected_lane not in LANES:
            if not auto_trigger:
                messagebox.showerror("Error", "Please select a lane.")
            return False

        full_name = self.resolve_champion_name(champion_name)
        if not full_name:
            if not auto_trigger:
                messagebox.showerror("Error", f"Champion name '{champion_name}' not found.")
            return False

        display_name = self.display_lookup.get(full_name, full_name.title())
        dataset, resolved_lane, used_fallback = self._load_lane_dataset(
            full_name,
            selected_lane,
            "Counter",
            "counters",
            self.sanitize_counter_entry,
            suppress_errors=auto_trigger
        )

        if dataset is None or resolved_lane is None:
            if not auto_trigger:
                messagebox.showerror(
                    "Error",
                    f"{display_name} 챔피언의 Counter 데이터를 불러올 수 없습니다."
                )
            return False

        if used_fallback and not auto_trigger:
            messagebox.showinfo(
                "Info",
                f"{selected_lane} 라인 데이터가 없어 {resolved_lane} 라인 Counter 데이터를 불러왔습니다."
            )
        elif not used_fallback and not auto_trigger:
            self.name_entry.delete(0, tk.END)

        key = (full_name, resolved_lane)
        label = f"{display_name} ({resolved_lane})"

        self.counter_cache[key] = dataset
        if label not in self.counter_listbox_map:
            self.champion_listbox.insert(tk.END, label)
        self.counter_listbox_map[label] = key
        labels = self.champion_listbox.get(0, tk.END)
        if label in labels:
            idx = labels.index(label)
            self.champion_listbox.selection_clear(0, tk.END)
            self.champion_listbox.selection_set(idx)

        self.all_data = self.clone_dataset(dataset)
        self.apply_counter_filter()
        self.update_GUI()
        return True

    def start_synergy_search(self, auto_trigger=False):
        champion_name = self.ally_name_entry.get()
        selected_lane = self.ally_lane_combobox.get().lower()

        if selected_lane not in LANES:
            if not auto_trigger:
                messagebox.showerror("Error", "Please select a lane for synergy.")
            return False

        full_name = self.resolve_champion_name(champion_name)
        if not full_name:
            if not auto_trigger:
                messagebox.showerror("Error", f"Champion name '{champion_name}' not found.")
            return False

        display_name = self.display_lookup.get(full_name, full_name.title())
        dataset, resolved_lane, used_fallback = self._load_lane_dataset(
            full_name,
            selected_lane,
            "Synergy",
            "synergy",
            self.sanitize_synergy_entry,
            suppress_errors=auto_trigger
        )

        if dataset is None or resolved_lane is None:
            if not auto_trigger:
                messagebox.showinfo(
                    "Info",
                    f"{display_name} 챔피언의 Synergy 데이터를 불러올 수 없습니다."
                )
            return False

        if used_fallback and not auto_trigger:
            messagebox.showinfo(
                "Info",
                f"{selected_lane} 라인 데이터가 없어 {resolved_lane} 라인 Synergy 데이터를 불러왔습니다."
            )
        elif not used_fallback and not auto_trigger:
            self.ally_name_entry.delete(0, tk.END)

        label = f"{display_name} ({resolved_lane})"

        key = (full_name, resolved_lane)
        self.synergy_cache[key] = dataset
        if label not in self.synergy_listbox_map:
            self.synergy_listbox.insert(tk.END, label)
        self.synergy_listbox_map[label] = key
        labels = self.synergy_listbox.get(0, tk.END)
        if label in labels:
            idx = labels.index(label)
            self.synergy_listbox.selection_clear(0, tk.END)
            self.synergy_listbox.selection_set(idx)

        self.synergy_data = self.clone_dataset(dataset)
        self.apply_synergy_filter()
        self.update_synergy_GUI()
        return True

    def get_counter_min_games_threshold(self):
        return self._parse_threshold_value(
            getattr(self, "counter_min_games_entry", None),
            COUNTER_LOW_GAMES_DEFAULT
        )

    def get_synergy_min_games_threshold(self):
        return self._parse_threshold_value(
            getattr(self, "synergy_min_games_entry", None),
            SYNERGY_LOW_GAMES_DEFAULT
        )

    @staticmethod
    def _parse_threshold_value(entry_widget, default_value):
        if not entry_widget:
            return default_value
        value = entry_widget.get().strip()
        if not value:
            return default_value
        try:
            parsed = int(value)
        except ValueError:
            return default_value
        return parsed if parsed >= 0 else default_value

    def _load_lane_dataset(self, full_name, preferred_lane, data_label, data_key, sanitize_entry, suppress_errors=False):
        lanes_to_try = [preferred_lane] + [lane for lane in LANES if lane != preferred_lane]
        best_candidate = None

        for lane_candidate in lanes_to_try:
            data_filename = f"{full_name}_{lane_candidate}.json".replace(" ", "_")
            filename = resolve_resource_path("data", data_filename)
            try:
                with open(filename, "r", encoding="utf-8") as file:
                    raw_data = json.load(file)
            except FileNotFoundError:
                continue
            except json.JSONDecodeError as e:
                if not suppress_errors:
                    messagebox.showerror(
                        "Error",
                        f"{data_label} 데이터 파일 '{data_filename}'을 읽을 수 없습니다.\n에러: {e}"
                    )
                return None, None, False
            except OSError as e:
                if not suppress_errors:
                    messagebox.showerror(
                        "Error",
                        f"{data_label} 데이터 파일 '{data_filename}'을 여는 중 오류가 발생했습니다.\n경로: {filename}\n에러: {e}"
                    )
                return None, None, False

            payload = raw_data.get(data_key)
            if payload is None and data_key == "counters":
                payload = raw_data
            if not isinstance(payload, dict):
                continue

            sanitized_dataset = {ln: {} for ln in LANES}
            for lane_name in LANES:
                lane_payload = payload.get(lane_name, {})
                if not isinstance(lane_payload, dict):
                    continue
                for name, entry in lane_payload.items():
                    if not isinstance(entry, dict):
                        continue
                    sanitized_dataset[lane_name][name] = sanitize_entry(entry)

            has_entries = any(sanitized_dataset[lane] for lane in LANES)
            if not has_entries:
                continue

            if lane_candidate == preferred_lane:
                return sanitized_dataset, lane_candidate, False

            total_games = sum(
                self.parse_int(details.get("games"))
                for lane_data in sanitized_dataset.values()
                for details in lane_data.values()
            )
            if best_candidate is None or total_games > best_candidate["games"]:
                best_candidate = {
                    "dataset": sanitized_dataset,
                    "lane": lane_candidate,
                    "games": total_games
                }

        if best_candidate:
            return best_candidate["dataset"], best_candidate["lane"], best_candidate["lane"] != preferred_lane

        return None, None, False

    def reset_data(self):
        self.all_data = {lane: {} for lane in LANES}
        self.synergy_data = {lane: {} for lane in LANES}
        self.counter_cache.clear()
        self.synergy_cache.clear()
        self.counter_listbox_map.clear()
        self.synergy_listbox_map.clear()
        self.champion_listbox.delete(0, tk.END)
        self.synergy_listbox.delete(0, tk.END)

        for tree in self.treeviews.values():
            for item in tree.get_children():
                tree.delete(item)

        for tree in self.synergy_treeviews.values():
            for item in tree.get_children():
                tree.delete(item)

        for var in self.lane_vars.values():
            var.set(True)
        for var in self.synergy_lane_vars.values():
            var.set(True)

        self.update_GUI()
        self.update_synergy_GUI()
        self.update_lane_visibility()
        self.update_synergy_visibility()
        self.reset_banpick_slots()
        self.reset_highlight_tree()

    def update_GUI(self):
        threshold = self.get_counter_min_games_threshold()
        for lane, data_dict in self.all_data.items():
            tree = self.treeviews[lane]
            for item in tree.get_children():
                tree.delete(item)
            
            for name, details in sorted(data_dict.items(), key=lambda item: float(item[1].get('win_rate_diff', 0.0)), reverse=False):
                games = self.parse_int(details.get("games"))
                is_low = games < threshold
                display_name = f"{WARNING_ICON} {name}" if is_low else name
                tag = "low_games" if is_low else "normal_games"
                tree.insert("", "end", values=(
                    display_name,
                    details["popularity"],
                    details.get("win_rate", "0.00")
                ), tags=(tag,))

    def update_synergy_GUI(self):
        threshold = self.get_synergy_min_games_threshold()
        for lane, data_dict in self.synergy_data.items():
            tree = self.synergy_treeviews[lane]
            for item in tree.get_children():
                tree.delete(item)

            sorted_entries = sorted(
                data_dict.items(),
                key=lambda item: self.parse_float(item[1].get("win_rate")),
                reverse=True
            )

            for name, details in sorted_entries:
                games = self.parse_int(details.get("games"))
                is_low = games < threshold
                display_name = f"{WARNING_ICON} {name}" if is_low else name
                tag = "low_games" if is_low else "normal_games"
                tree.insert("", "end", values=(
                    display_name,
                    details.get("pick_rate", "0.00"),
                    details.get("win_rate", "0.00")
                ), tags=(tag,))

    def update_lane_visibility(self):
        visible_lanes = [lane for lane in LANES if self.lane_vars.get(lane).get()]
        for index, lane in enumerate(visible_lanes):
            frame = self.lane_frames[lane]
            frame.grid(row=index + 1, column=4, sticky="nsew", padx=(5, 0), pady=(0, 10))

        for lane in LANES:
            if lane not in visible_lanes:
                self.lane_frames[lane].grid_remove()

        self.update_GUI()

    def update_synergy_visibility(self):
        visible_lanes = [lane for lane in LANES if self.synergy_lane_vars.get(lane).get()]
        for index, lane in enumerate(visible_lanes):
            frame = self.synergy_frames[lane]
            frame.grid(row=index + 1, column=5, sticky="nsew", padx=(5, 0), pady=(0, 10))

        for lane in LANES:
            if lane not in visible_lanes:
                self.synergy_frames[lane].grid_remove()

        self.update_synergy_GUI()

    def resolve_champion_name(self, query: str):
        allow_initials = not contains_hangul_syllable(query or "")
        variants = alias_variants(query, include_initials=allow_initials)
        variants.add(query.lower().strip())

        for variant in variants:
            if variant in self.alias_lookup:
                return self.alias_lookup[variant]

        lowered_query = query.lower().strip()
        for normalized, canonical in self.canonical_lookup.items():
            if lowered_query and lowered_query in normalized:
                return canonical
        return None
    def apply_counter_filter(self):
        try:
            min_popularity = float(self.popularity_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for popularity.")
            return

        filtered_data = {lane: {} for lane in LANES}
        for lane, champions in self.all_data.items():
            for name, details in champions.items():
                if self.parse_float(details.get("popularity")) >= min_popularity:
                    filtered_data[lane][name] = details

        self.all_data = filtered_data
    
    def filter_by_popularity(self):
        self.apply_counter_filter()
        self.update_GUI()

    def apply_synergy_filter(self):
        try:
            min_pick_rate = float(self.synergy_pick_rate_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for synergy pick rate.")
            return

        filtered_data = {lane: {} for lane in LANES}
        for lane, champions in self.synergy_data.items():
            for name, details in champions.items():
                if self.parse_float(details.get("pick_rate")) >= min_pick_rate:
                    filtered_data[lane][name] = details

        self.synergy_data = filtered_data
    
    def filter_synergy(self):
        self.apply_synergy_filter()
        self.update_synergy_GUI()

    @staticmethod
    def clone_dataset(dataset):
        if not dataset:
            return {lane: {} for lane in LANES}
        return {
            lane: {name: details.copy() for name, details in lane_data.items()}
            for lane, lane_data in dataset.items()
        }

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
        if not DATA_DIR.exists():
            return highlights

        for path in DATA_DIR.glob("*_bottom.json"):
            try:
                with path.open("r", encoding="utf-8") as file:
                    payload = json.load(file)
            except (IOError, json.JSONDecodeError):
                continue

            stem = path.stem
            if stem.endswith("_bottom"):
                stem = stem[:-7]
            adc_name = self.format_display_name(stem)

            support_entries = payload.get("synergy", {}).get("support", {})
            for entry in support_entries.values():
                support_name = entry.get("Name") or entry.get("name")
                if not support_name:
                    continue
                win_rate = self.parse_float(str(entry.get("win_rate", "")).replace("%", ""))
                pick_rate = self.parse_float(str(entry.get("pick_rate", "")).replace("%", ""))
                games = self.parse_int(entry.get("games"))

                if win_rate < HIGHLIGHT_WIN_RATE or pick_rate < pick_threshold or games < games_threshold:
                    continue

                highlights.append({
                    "duo": f"{adc_name} + {support_name}",
                    "win": win_rate,
                    "pick": pick_rate,
                    "games": games
                })

        highlights.sort(key=lambda item: (item["win"], item["pick"]), reverse=True)
        return highlights[:HIGHLIGHT_LIMIT]

    def reset_banpick_slots(self):
        if not hasattr(self, "banpick_slots"):
            return
        for _side_key, slots in self.banpick_slots.items():
            for slot in slots:
                self.clear_banpick_slot(slot, reset_lane=True, suppress_update=True)
        self.active_slot_var.set("")
        self.update_banpick_recommendations()

    def reset_main_tab(self):
        self.reset_data()

    def reset_dashboard_tab(self):
        self.reset_banpick_slots()
        self.recommend_min_games_entry.delete(0, tk.END)
        self.recommend_min_games_entry.insert(0, str(BANPICK_MIN_GAMES_DEFAULT))
        self.update_banpick_recommendations()

    def reset_highlights_tab(self):
        self.highlight_pick_entry.delete(0, tk.END)
        self.highlight_pick_entry.insert(0, str(HIGHLIGHT_PICK_RATE))
        self.highlight_games_entry.delete(0, tk.END)
        self.highlight_games_entry.insert(0, str(HIGHLIGHT_MIN_GAMES))
        self.populate_synergy_highlights()

    def reset_highlight_tree(self):
        if hasattr(self, "highlight_tree"):
            for item in self.highlight_tree.get_children():
                self.highlight_tree.delete(item)

    def format_display_name(self, slug: str) -> str:
        key = slug.lower().replace("_", "")
        display = self.display_lookup.get(key)
        if display:
            return display
        return slug.replace("_", " ").title()

    def on_counter_select(self, event):
        selection = event.widget.curselection()
        if not selection:
            return
        label = event.widget.get(selection[0])
        key = self.counter_listbox_map.get(label)
        cached = self.counter_cache.get(key) if key else None
        if not cached:
            return
        self.all_data = self.clone_dataset(cached)
        self.apply_counter_filter()
        self.update_GUI()

    def on_synergy_select(self, event):
        selection = event.widget.curselection()
        if not selection:
            return
        label = event.widget.get(selection[0])
        key = self.synergy_listbox_map.get(label)
        cached = self.synergy_cache.get(key) if key else None
        if not cached:
            return
        self.synergy_data = self.clone_dataset(cached)
        self.apply_synergy_filter()
        self.update_synergy_GUI()


    def integrate_data(self, existing_data, new_data):
        existing_games = self.parse_int(existing_data.get("games"))
        new_games = self.parse_int(new_data.get("games"))
        total_games = existing_games + new_games

        existing_win_rate = self.parse_float(existing_data.get("win_rate"))
        new_win_rate = self.parse_float(new_data.get("win_rate"))

        weighted_win_rate = (
            ((existing_win_rate * existing_games) + (new_win_rate * new_games)) 
            / total_games if total_games > 0 else 0
        )
        
        win_rate_diff = weighted_win_rate - 50
        
        total_popularity = self.parse_float(existing_data.get("popularity")) + \
                        self.parse_float(new_data.get("popularity"))

        existing_data.update({
            "games": f"{total_games}",
            "win_rate_diff": f"{win_rate_diff:.2f}",
            "popularity": f"{total_popularity:.2f}",
            "win_rate": f"{weighted_win_rate:.2f}"
        })

        return existing_data

    def integrate_synergy_data(self, existing_data, new_data):
        existing_games = self.parse_int(existing_data.get("games"))
        new_games = self.parse_int(new_data.get("games"))
        total_games = existing_games + new_games

        existing_win_rate = self.parse_float(existing_data.get("win_rate"))
        new_win_rate = self.parse_float(new_data.get("win_rate"))

        existing_pick_rate = self.parse_float(existing_data.get("pick_rate"))
        new_pick_rate = self.parse_float(new_data.get("pick_rate"))

        weighted_win_rate = (
            ((existing_win_rate * existing_games) + (new_win_rate * new_games))
            / total_games if total_games > 0 else 0
        )

        weighted_pick_rate = (
            ((existing_pick_rate * existing_games) + (new_pick_rate * new_games))
            / total_games if total_games > 0 else 0
        )

        existing_data.update({
            "games": f"{total_games}",
            "win_rate": f"{weighted_win_rate:.2f}",
            "pick_rate": f"{weighted_pick_rate:.2f}"
        })

        return existing_data

    def sanitize_counter_entry(self, entry):
        sanitized = entry.copy()
        sanitized["games"] = f"{self.parse_int(entry.get('games'))}"
        sanitized["popularity"] = f"{self.parse_float(entry.get('popularity')):.2f}"
        sanitized["win_rate"] = f"{self.parse_float(entry.get('win_rate')):.2f}"
        sanitized["win_rate_diff"] = f"{self.parse_float(entry.get('win_rate_diff')):.2f}"
        return sanitized

    def sanitize_synergy_entry(self, entry):
        sanitized = entry.copy()
        sanitized["games"] = f"{self.parse_int(entry.get('games'))}"
        sanitized["pick_rate"] = f"{self.parse_float(entry.get('pick_rate')):.2f}"
        sanitized["win_rate"] = f"{self.parse_float(entry.get('win_rate')):.2f}"
        return sanitized

    @staticmethod
    def parse_int(value):
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            value = value.replace(",", "").strip()
            if not value:
                return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def parse_float(value):
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            value = value.replace(",", "").strip()
            if not value:
                return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0


if __name__ == "__main__":
    root = tk.Tk()
    app = ChampionScraperApp(root)
    root.mainloop()
