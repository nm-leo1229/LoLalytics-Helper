import tkinter as tk
from tkinter import messagebox, ttk
import json
import os
import re
import sys

CHAMPION_NAMES = [
    "jinx"
]

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


def alias_variants(alias: str) -> set[str]:
    variants = set()
    candidate = alias.strip()
    if not candidate:
        return variants

    lower_candidate = candidate.lower()
    variants.add(lower_candidate)

    alnum_only = re.sub(r"[^0-9a-z가-힣]", "", lower_candidate)
    if alnum_only:
        variants.add(alnum_only)

    initials = extract_choseong(candidate)
    if initials:
        variants.add(initials.lower())

    return variants


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

    for canonical_name, aliases in alias_data.items():
        normalized = canonical_name.lower()
        canonical_lookup[normalized] = canonical_name

        display_value = canonical_name.title()
        if isinstance(aliases, list) and aliases:
            display_value = next((alias for alias in aliases if alias and alias[0].isascii()), display_value)
            for alias in aliases:
                for variant in alias_variants(alias):
                    alias_lookup.setdefault(variant, canonical_name)

        for variant in alias_variants(canonical_name):
            alias_lookup.setdefault(variant, canonical_name)
        alias_lookup.setdefault(normalized, canonical_name)
        display_lookup[canonical_name] = display_value

    for name in CHAMPION_NAMES:
        normalized = name.lower()
        canonical_lookup.setdefault(normalized, name)
        alias_lookup.setdefault(normalized, name)
        display_lookup.setdefault(name, name.title())

    return canonical_lookup, alias_lookup, display_lookup


class ChampionScraperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Champion Ban/Pick Helper")
        self.all_data = {lane: {} for lane in LANES}
        self.synergy_data = {lane: {} for lane in LANES}
        self.canonical_lookup, self.alias_lookup, self.display_lookup = load_alias_tables()
        self.counter_cache = {}
        self.synergy_cache = {}
        self.counter_listbox_map = {}
        self.synergy_listbox_map = {}

        # Counter controls
        self.counter_section = tk.LabelFrame(root, text="Counter")
        self.counter_section.grid(row=1, column=0, columnspan=4, sticky="ew", padx=5, pady=(10, 0))
        self.counter_section.grid_columnconfigure(0, weight=1)
        self.counter_section.grid_columnconfigure(1, weight=1)

        self.name_entry = tk.Entry(self.counter_section, width=20)
        self.name_entry.grid(row=0, column=0, sticky="ew")

        self.lane_combobox = ttk.Combobox(self.counter_section, values=LANES, state="readonly", width=10)
        self.lane_combobox.grid(row=0, column=1, sticky="ew")
        self.lane_combobox.set("Select Lane")

        self.search_button = tk.Button(self.counter_section, text="Load Counter", command=self.start_search)
        self.search_button.grid(row=0, column=2, sticky="ew")
        self.root.bind('<Return>', lambda _: self.start_search())

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

        self.lane_filter_frame = tk.LabelFrame(self.counter_section, text="Lane Filters")
        self.lane_filter_frame.grid(row=2, column=0, columnspan=4, sticky="ew", padx=5, pady=(0, 10))

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
            frame = tk.Frame(root)
            tk.Label(frame, text=f"{lane.capitalize()} Counter:").pack(anchor="w")
            tree = ttk.Treeview(frame, columns=("Name", "Popularity", "Win Rate"), show='headings')
            tree.pack(expand=True, fill='both')
            tree.heading("Name", text="Name")
            tree.heading("Popularity", text="Popularity")
            tree.heading("Win Rate", text="Win Rate")
            self.treeviews[lane] = tree
            self.lane_frames[lane] = frame

        self.update_lane_visibility()

        # Synergy controls
        self.synergy_section = tk.LabelFrame(root, text="Ally Synergy")
        self.synergy_section.grid(row=3, column=0, columnspan=4, sticky="ew", padx=5, pady=(10, 0))
        self.synergy_section.grid_columnconfigure(0, weight=1)
        self.synergy_section.grid_columnconfigure(1, weight=1)

        self.ally_name_entry = tk.Entry(self.synergy_section, width=20)
        self.ally_name_entry.grid(row=0, column=0, sticky="ew")

        self.ally_lane_combobox = ttk.Combobox(self.synergy_section, values=LANES, state="readonly", width=10)
        self.ally_lane_combobox.grid(row=0, column=1, sticky="ew")
        self.ally_lane_combobox.set("Select Lane")

        self.ally_search_button = tk.Button(self.synergy_section, text="Load Synergy", command=self.start_synergy_search)
        self.ally_search_button.grid(row=0, column=2, sticky="ew", padx=(5, 0))

        tk.Label(self.synergy_section, text="Loaded Synergy:").grid(row=1, column=0, columnspan=2, sticky="wn", pady=5)
        self.synergy_listbox = tk.Listbox(self.synergy_section, height=7)
        self.synergy_listbox.grid(row=1, column=0, columnspan=2, sticky="wn", pady=25)
        self.synergy_listbox.bind("<<ListboxSelect>>", self.on_synergy_select)

        tk.Label(self.synergy_section, text="Filter Synergy by Pick Rate:").grid(row=1, column=1, columnspan=2, sticky="wn")
        self.synergy_pick_rate_entry = tk.Entry(self.synergy_section, width=17)
        self.synergy_pick_rate_entry.grid(row=1, column=1, columnspan=2, sticky="wn", pady=26)
        self.synergy_pick_rate_entry.insert(0, "2")

        self.synergy_filter_button = tk.Button(self.synergy_section, text="Filter", command=self.filter_synergy)
        self.synergy_filter_button.grid(row=1, column=1, columnspan=2, sticky="ne", pady=(0, 25))

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
            frame = tk.Frame(root)
            tk.Label(frame, text=f"{lane.capitalize()} Synergy:").pack(anchor="w")
            tree = ttk.Treeview(frame, columns=("Name", "Pick Rate", "Win Rate"), show='headings')
            tree.pack(expand=True, fill='both')
            tree.heading("Name", text="Name")
            tree.heading("Pick Rate", text="Pick Rate")
            tree.heading("Win Rate", text="Win Rate")
            self.synergy_treeviews[lane] = tree
            self.synergy_frames[lane] = frame

        self.update_synergy_visibility()

    def start_search(self):
        champion_name = self.name_entry.get()
        lane = self.lane_combobox.get().lower()

        if lane not in LANES:
            messagebox.showerror("Error", "Please select a lane.")
            return

        full_name = self.resolve_champion_name(champion_name)
        if not full_name:
            messagebox.showerror("Error", f"Champion name '{champion_name}' not found.")
            return

        # Clean input fields
        self.name_entry.delete(0, tk.END)

        # Extract data from json file
        data_filename = f"{full_name}_{lane}.json".replace(" ", "_")
        filename = resolve_resource_path("data", data_filename)
        try:
            with open(filename, 'r', encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            messagebox.showerror("Error", f"Counter data file '{data_filename}' not found.\n경로: {filename}")
            return
        except json.JSONDecodeError as e:
            messagebox.showerror("Error", f"Counter 데이터 파일을 읽을 수 없습니다: {data_filename}\n에러: {e}")
            return
        except OSError as e:
            messagebox.showerror("Error", f"Counter 데이터 파일을 여는 중 오류가 발생했습니다: {filename}\n에러: {e}")
            return

        counters_data = data.get("counters")
        if counters_data is None:
            counters_data = data

        key = (full_name, lane)
        display_name = self.display_lookup.get(full_name, full_name.title())
        label = f"{display_name} ({lane})"

        sanitized_dataset = {ln: {} for ln in LANES}
        for lane_name in sanitized_dataset:
            lane_data = counters_data.get(lane_name, {})
            for name, new_data in lane_data.items():
                sanitized_dataset[lane_name][name] = self.sanitize_counter_entry(new_data)

        self.counter_cache[key] = sanitized_dataset
        if label not in self.counter_listbox_map:
            self.champion_listbox.insert(tk.END, label)
        self.counter_listbox_map[label] = key
        labels = self.champion_listbox.get(0, tk.END)
        if label in labels:
            idx = labels.index(label)
            self.champion_listbox.selection_clear(0, tk.END)
            self.champion_listbox.selection_set(idx)

        self.all_data = self.clone_dataset(sanitized_dataset)
        self.apply_counter_filter()
        self.update_GUI()

    def start_synergy_search(self):
        champion_name = self.ally_name_entry.get()
        lane = self.ally_lane_combobox.get().lower()

        if lane not in LANES:
            messagebox.showerror("Error", "Please select a lane for synergy.")
            return

        full_name = self.resolve_champion_name(champion_name)
        if not full_name:
            messagebox.showerror("Error", f"Champion name '{champion_name}' not found.")
            return

        self.ally_name_entry.delete(0, tk.END)

        data_filename = f"{full_name}_{lane}.json".replace(" ", "_")
        filename = resolve_resource_path("data", data_filename)
        try:
            with open(filename, 'r', encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            messagebox.showerror("Error", f"Synergy 데이터 파일 '{data_filename}'을 찾을 수 없습니다.\n경로: {filename}")
            return
        except json.JSONDecodeError as e:
            messagebox.showerror("Error", f"Synergy 데이터 파일을 읽을 수 없습니다: {data_filename}\n에러: {e}")
            return
        except OSError as e:
            messagebox.showerror("Error", f"Synergy 데이터 파일을 여는 중 오류가 발생했습니다: {filename}\n에러: {e}")
            return

        synergy_payload = data.get("synergy")
        if not isinstance(synergy_payload, dict):
            messagebox.showinfo("Info", f"No synergy data available for {full_name}_{lane}.")
            return

        display_name = self.display_lookup.get(full_name, full_name.title())
        label = f"{display_name} ({lane})"
        sanitized_dataset = {ln: {} for ln in LANES}
        for lane_name in sanitized_dataset:
            lane_synergy = synergy_payload.get(lane_name, {})
            for name, new_data in lane_synergy.items():
                sanitized_dataset[lane_name][name] = self.sanitize_synergy_entry(new_data)

        key = (full_name, lane)
        self.synergy_cache[key] = sanitized_dataset
        if label not in self.synergy_listbox_map:
            self.synergy_listbox.insert(tk.END, label)
        self.synergy_listbox_map[label] = key
        labels = self.synergy_listbox.get(0, tk.END)
        if label in labels:
            idx = labels.index(label)
            self.synergy_listbox.selection_clear(0, tk.END)
            self.synergy_listbox.selection_set(idx)

        self.synergy_data = self.clone_dataset(sanitized_dataset)
        self.apply_synergy_filter()
        self.update_synergy_GUI()

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

    def update_GUI(self):
        for lane, data_dict in self.all_data.items():
            tree = self.treeviews[lane]
            for item in tree.get_children():
                tree.delete(item)
            
            for name, details in sorted(data_dict.items(), key=lambda item: float(item[1].get('win_rate_diff', 0.0)), reverse=False):
                tree.insert("", "end", values=(
                    name,
                    details["popularity"],
                    details.get("win_rate", "0.00")
                ))

    def update_synergy_GUI(self):
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
                tree.insert("", "end", values=(
                    name,
                    details.get("pick_rate", "0.00"),
                    details.get("win_rate", "0.00")
                ))

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
        variants = alias_variants(query)
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
