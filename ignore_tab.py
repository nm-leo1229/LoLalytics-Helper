import tkinter as tk
from tkinter import messagebox
from common import AutocompletePopup, WARNING_ICON

class IgnoreTab:
    def __init__(self, notebook, app_context):
        self.notebook = notebook
        self.app = app_context
        self.tab = tk.Frame(self.notebook)
        self.notebook.add(self.tab, text="Ignore List")
        
        self.ignore_listbox_map = {}
        self._build_ui()

    def _build_ui(self):
        self.tab.grid_rowconfigure(0, weight=1)
        self.tab.grid_columnconfigure(0, weight=1)

        self.ignore_section = tk.LabelFrame(self.tab, text="Ignore List")
        self.ignore_section.pack(fill="both", expand=True, padx=10, pady=10)
        self.ignore_section.grid_columnconfigure(0, weight=1)
        self.ignore_section.grid_rowconfigure(1, weight=1)

        self.ignore_entry = tk.Entry(self.ignore_section, width=25)
        self.ignore_entry.grid(row=0, column=0, sticky="ew", padx=(5, 5), pady=(5, 2))
        self.ignore_entry.bind("<Return>", lambda _event: self.add_ignore_champion())

        self.ignore_add_button = tk.Button(self.ignore_section, text="추가", command=self.add_ignore_champion)
        self.ignore_add_button.grid(row=0, column=1, sticky="ew", padx=(0, 5), pady=(5, 2))

        self.ignore_remove_button = tk.Button(self.ignore_section, text="선택 제거", command=self.remove_selected_ignore)
        self.ignore_remove_button.grid(row=0, column=2, sticky="ew", padx=(0, 5), pady=(5, 2))

        self.ignore_listbox = tk.Listbox(self.ignore_section, height=5)
        self.ignore_listbox.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=(5, 0), pady=(0, 5))
        self.ignore_listbox.bind("<Delete>", lambda _event: self.remove_selected_ignore())

        ignore_scrollbar = tk.Scrollbar(self.ignore_section, orient="vertical", command=self.ignore_listbox.yview)
        ignore_scrollbar.grid(row=1, column=2, sticky="ns", padx=(0, 5), pady=(0, 5))
        self.ignore_listbox.configure(yscrollcommand=ignore_scrollbar.set)

        tk.Label(
            self.ignore_section,
            text="리스트에 있는 챔피언은 추천/표시에서 제외됩니다.",
            anchor="w"
        ).grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=(0, 5))

        self.ignore_autocomplete = AutocompletePopup(
            self.ignore_entry,
            self.app.get_autocomplete_candidates,
            on_select=lambda _value: None
        )
        self.refresh_ignore_listbox()

    def refresh_ignore_listbox(self):
        if not hasattr(self, "ignore_listbox"):
            return
        self.ignore_listbox.delete(0, tk.END)
        self.ignore_listbox_map.clear()
        if not self.app.ignored_champions:
            return
        sorted_names = sorted(self.app.ignored_champions)
        for idx, normalized in enumerate(sorted_names):
            canonical = self.app.canonical_lookup.get(normalized, normalized)
            display = self.app.display_lookup.get(canonical, canonical.title())
            self.ignore_listbox.insert(tk.END, display)
            self.ignore_listbox_map[idx] = normalized

    def _register_ignore(self, champion_query: str, apply_updates: bool = True):
        canonical_name = self.app.resolve_champion_name(champion_query)
        if not canonical_name:
            return False, "not_found", champion_query
        normalized = canonical_name.lower()
        if normalized in self.app.ignored_champions:
            return False, "duplicate", canonical_name
        self.app.ignored_champions.add(normalized)
        if apply_updates:
            self.app.persist_ignored_champions()
            self.refresh_ignore_listbox()
            self.app.on_ignore_list_updated()
        return True, None, canonical_name

    def add_ignore_champion(self):
        champion_query = self.ignore_entry.get().strip()
        if not champion_query:
            messagebox.showerror("Error", "챔피언 이름을 입력하세요.")
            return
        success, reason, canonical = self._register_ignore(champion_query)
        if success:
            self.ignore_entry.delete(0, tk.END)
            return
        if reason == "duplicate":
            display = self.app.display_lookup.get(canonical, canonical.title())
            messagebox.showinfo("Info", f"{display} 는 이미 제외 리스트에 있습니다.")
            self.ignore_entry.delete(0, tk.END)
        elif reason == "not_found":
            messagebox.showerror("Error", f"'{champion_query}' 챔피언을 찾을 수 없습니다.")

    def remove_selected_ignore(self):
        selection = self.ignore_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        normalized = self.ignore_listbox_map.get(idx)
        if not normalized:
            return
        self.app.ignored_champions.discard(normalized)
        self.app.persist_ignored_champions()
        self.refresh_ignore_listbox()
        self.app.on_ignore_list_updated()

    def ignore_selected_recommendations(self, selection):
        if not selection:
            messagebox.showinfo("Ignore List", "추천 리스트에서 제외할 챔피언을 선택하세요.")
            return
        added = []
        duplicates = []
        missing = []
        for item_id in selection:
            values = self.app.recommend_tree.item(item_id, "values")
            if not values:
                continue
            champ_name = str(values[0]).strip()
            warning_prefix = f"{WARNING_ICON} "
            if champ_name.startswith(warning_prefix):
                champ_name = champ_name[len(warning_prefix):].strip()
            success, reason, canonical = self._register_ignore(champ_name, apply_updates=False)
            if success:
                display = self.app.display_lookup.get(canonical, canonical.title())
                added.append(display)
            elif reason == "duplicate":
                display = self.app.display_lookup.get(canonical, canonical.title())
                duplicates.append(display)
            elif reason == "not_found":
                missing.append(champ_name)
        if added:
            self.app.persist_ignored_champions()
            self.refresh_ignore_listbox()
            self.app.on_ignore_list_updated()
            messagebox.showinfo("Ignore List", f"{', '.join(added)} 제외 리스트에 추가했습니다.")
        if duplicates:
            messagebox.showinfo("Ignore List", f"{', '.join(duplicates)} 는 이미 제외 리스트에 있습니다.")
        if missing:
            messagebox.showerror("Ignore List", f"{', '.join(missing)} 챔피언을 찾을 수 없습니다.")

