import tkinter as tk
from tkinter import messagebox, ttk
from common import AutocompletePopup, LANES, COUNTER_LOW_GAMES_DEFAULT, SYNERGY_LOW_GAMES_DEFAULT, LOW_SAMPLE_COLOR, NORMAL_SAMPLE_COLOR, WARNING_ICON

class CounterSynergyTab:
    def __init__(self, notebook, app_context):
        self.notebook = notebook
        self.app = app_context
        
        self.tab = tk.Frame(self.notebook)
        self.tab.grid_rowconfigure(6, weight=1)
        self.tab.grid_columnconfigure(5, weight=1)
        
        tk.Button(
            self.tab,
            text="Reset Main",
            command=self.reset_main_tab
        ).grid(row=0, column=3, sticky="e", padx=5, pady=5)
        
        self.notebook.add(self.tab, text="카운터 & 시너지")

        self.all_data = {lane: {} for lane in LANES}
        self.synergy_data = {lane: {} for lane in LANES}
        self.counter_cache = {}
        self.synergy_cache = {}
        self.counter_listbox_map = {}
        self.synergy_listbox_map = {}
        
        self.counter_typing_after_id = None
        self.synergy_typing_after_id = None

        self._build_ui()

    def _build_ui(self):
        # Counter controls
        self.counter_section = tk.LabelFrame(self.tab, text="Counter")
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
        # Ensure root binding is handled in main app or handled here specifically for this frame
        # But root.bind might be global. We can bind to entry or handle global keypress if focused.
        # For now, let's leave root binding in main app if it was global, or re-bind if needed.
        self.name_entry.bind('<Return>', lambda _: self.start_search())

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
            self.app.get_autocomplete_candidates,
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

        self.treeviews = {}
        self.lane_frames = {}
        for lane in LANES:
            frame = tk.Frame(self.tab)
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
        self.synergy_section = tk.LabelFrame(self.tab, text="Ally Synergy")
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
            self.app.get_autocomplete_candidates,
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
            frame = tk.Frame(self.tab)
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
            self.tab.after_cancel(self.counter_typing_after_id)
            self.counter_typing_after_id = None

    def schedule_counter_auto_load(self, delay=400):
        if self.counter_typing_after_id is not None:
            self.tab.after_cancel(self.counter_typing_after_id)
            self.counter_typing_after_id = None

        if not self.counter_auto_load_var.get():
            return

        self.counter_typing_after_id = self.tab.after(delay, self._try_auto_counter_load)

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
            self.tab.after_cancel(self.synergy_typing_after_id)
            self.synergy_typing_after_id = None

    def schedule_synergy_auto_load(self, delay=400):
        if self.synergy_typing_after_id is not None:
            self.tab.after_cancel(self.synergy_typing_after_id)
            self.synergy_typing_after_id = None

        if not self.synergy_auto_load_var.get():
            return

        self.synergy_typing_after_id = self.tab.after(delay, self._try_auto_synergy_load)

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

    def on_autocomplete_selection(self, context):
        if context == "counter":
            if self.counter_auto_load_var.get():
                self.schedule_counter_auto_load(delay=0)
        elif context == "synergy":
            if self.synergy_auto_load_var.get():
                self.schedule_synergy_auto_load(delay=0)

    def on_counter_threshold_change(self, _event=None):
        self.update_GUI()

    def on_synergy_threshold_change(self, _event=None):
        self.update_synergy_GUI()

    def get_counter_min_games_threshold(self):
        return self.app._parse_threshold_value(
            getattr(self, "counter_min_games_entry", None),
            COUNTER_LOW_GAMES_DEFAULT
        )

    def get_synergy_min_games_threshold(self):
        return self.app._parse_threshold_value(
            getattr(self, "synergy_min_games_entry", None),
            SYNERGY_LOW_GAMES_DEFAULT
        )

    def start_search(self, auto_trigger=False):
        champion_name = self.name_entry.get()
        selected_lane = self.lane_combobox.get().lower()

        if selected_lane not in LANES:
            if not auto_trigger:
                messagebox.showerror("Error", "Please select a lane.")
            return False

        full_name = self.app.resolve_champion_name(champion_name)
        if not full_name:
            if not auto_trigger:
                messagebox.showerror("Error", f"Champion name '{champion_name}' not found.")
            return False

        display_name = self.app.display_lookup.get(full_name, full_name.title())
        dataset, resolved_lane, used_fallback = self.app._load_lane_dataset(
            full_name,
            selected_lane,
            "Counter",
            "counters",
            self.app.sanitize_counter_entry,
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

        full_name = self.app.resolve_champion_name(champion_name)
        if not full_name:
            if not auto_trigger:
                messagebox.showerror("Error", f"Champion name '{champion_name}' not found.")
            return False

        display_name = self.app.display_lookup.get(full_name, full_name.title())
        dataset, resolved_lane, used_fallback = self.app._load_lane_dataset(
            full_name,
            selected_lane,
            "Synergy",
            "synergy",
            self.app.sanitize_synergy_entry,
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

    def apply_counter_filter(self):
        try:
            min_popularity = float(self.popularity_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for popularity.")
            return

        filtered_data = {lane: {} for lane in LANES}
        for lane, champions in self.all_data.items():
            for name, details in champions.items():
                if self.app.is_champion_ignored(name):
                    continue
                if self.app.parse_float(details.get("popularity")) >= min_popularity:
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
                if self.app.is_champion_ignored(name):
                    continue
                if self.app.parse_float(details.get("pick_rate")) >= min_pick_rate:
                    filtered_data[lane][name] = details

        self.synergy_data = filtered_data
    
    def filter_synergy(self):
        self.apply_synergy_filter()
        self.update_synergy_GUI()

    def update_GUI(self):
        threshold = self.get_counter_min_games_threshold()
        for lane, data_dict in self.all_data.items():
            tree = self.treeviews[lane]
            for item in tree.get_children():
                tree.delete(item)
            
            for name, details in sorted(data_dict.items(), key=lambda item: float(item[1].get('win_rate_diff', 0.0)), reverse=False):
                games = self.app.parse_int(details.get("games"))
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
                key=lambda item: self.app.parse_float(item[1].get("win_rate")),
                reverse=True
            )

            for name, details in sorted_entries:
                games = self.app.parse_int(details.get("games"))
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

    def reset_main_tab(self):
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

    @staticmethod
    def clone_dataset(dataset):
        if not dataset:
            return {lane: {} for lane in LANES}
        return {
            lane: {name: details.copy() for name, details in lane_data.items()}
            for lane, lane_data in dataset.items()
        }

    def update_tree_colors(self, low_sample_color, normal_sample_color):
        """테마 변경 시 Treeview 태그 색상을 갱신합니다."""
        # Counter Treeviews
        for tree in self.treeviews.values():
            tree.tag_configure("low_games", foreground=low_sample_color)
            tree.tag_configure("normal_games", foreground=normal_sample_color)
        
        # Synergy Treeviews
        for tree in self.synergy_treeviews.values():
            tree.tag_configure("low_games", foreground=low_sample_color)
            tree.tag_configure("normal_games", foreground=normal_sample_color)

