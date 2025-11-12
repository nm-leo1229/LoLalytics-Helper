import tkinter as tk
from tkinter import messagebox, ttk
import json
import os
CHAMPION_NAMES = [
    "jinx"
]

LANES = ['top', 'jungle', 'middle', 'bottom', 'support']

class ChampionScraperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Champion Scraper")
        self.all_data = {lane: {} for lane in LANES}

        # Create and place widgets
        # name input
        self.name_entry = tk.Entry(root, width=20)
        self.name_entry.grid(row=0, column=0, sticky="ew")

        # lane input
        self.lane_combobox = ttk.Combobox(root, values=LANES, state="readonly", width=10)
        self.lane_combobox.grid(row=0, column=1, sticky="ew")
        self.lane_combobox.set("Select Lane")

        self.search_button = tk.Button(root, text="Start Search", command=self.start_search)
        self.search_button.grid(row=0, column=2, sticky="ew")
        self.root.bind('<Return>', lambda _: self.start_search()) # Bind Enter key to also search

        self.reset_button = tk.Button(root, text="Reset", command=self.reset_data)
        self.reset_button.grid(row=0, column=3, sticky="ew")

        # Listbox for loaded champions
        tk.Label(root, text="Loaded Champions:").grid(row=1, column=0, columnspan=2, sticky="wn")
        self.champion_listbox = tk.Listbox(root, height=7)
        self.champion_listbox.grid(row=1, column=0, columnspan=2, sticky="wn", pady=25)

        # Filter by game count
        tk.Label(root, text="Filter Data by Popularity:").grid(row=1, column=1, columnspan=2, sticky="wn")
        self.popularity_entry = tk.Entry(root, width=17)
        self.popularity_entry.grid(row=1, column=1, columnspan=2, sticky="wn", pady=26)
        self.popularity_entry.insert(0, "1")
        self.filter_button = tk.Button(root, text="Filter", command=self.filter_by_popularity)
        self.filter_button.grid(row=1, column=1, columnspan=2, sticky="ne", pady=25)

        style = ttk.Style()
        style.configure('Treeview', rowheight=15)

        # Create Treeview for each lane
        self.treeviews = {}
        for i, lane in enumerate(LANES):
            frame = tk.Frame(root)
            frame.grid(row=i + 1, column=4, sticky="nsew")
            tk.Label(frame, text=f"{lane.capitalize()} Lane:").pack(anchor="w")
            tree = ttk.Treeview(frame, columns=("Name", "Popularity", "Win Rate"), show='headings')
            tree.pack(expand=True, fill='both')
            tree.heading("Name", text="Name")
            tree.heading("Popularity", text="Popularity")
            tree.heading("Win Rate", text="Win Rate")
            self.treeviews[lane] = tree

    def start_search(self):
        champion_name = self.name_entry.get()
        lane = self.lane_combobox.get().lower()

        # Find the full champion name
        full_name = next((name for name in CHAMPION_NAMES if champion_name.lower() in name.lower()), None)

        # Show error if the champion is not found
        if not full_name:
            messagebox.showerror("Error", f"Champion name '{champion_name}' not found.")
            return
        
        # Clean input fields
        self.name_entry.delete(0, tk.END)

        # Extract data from json file
        filename = f"data/{full_name}_{lane}.json".replace(" ", "_")
        try:
            with open(filename, 'r') as file:
                data = json.load(file)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading data from {filename} {e}")
            return

        counters_data = data.get("counters")
        if counters_data is None:
            counters_data = data

        # Add the champion to the loaded list
        self.champion_listbox.insert(tk.END, f"{full_name}_{lane}")

        for lane in self.all_data:
            lane_data = counters_data.get(lane, {})
            for name, new_data in lane_data.items():
                sanitized_new_data = self.sanitize_counter_entry(new_data)
                if name in self.all_data[lane]:
                    existing_data = self.all_data[lane][name]
                    self.all_data[lane][name] = self.integrate_data(existing_data, sanitized_new_data)
                else:
                    self.all_data[lane][name] = sanitized_new_data

        self.apply_current_filter()
        self.update_GUI()

    def reset_data(self):
        self.all_data = {lane: {} for lane in LANES}
        self.champion_listbox.delete(0, tk.END)

        for tree in self.treeviews.values():
            for item in tree.get_children():
                tree.delete(item)

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
    def apply_current_filter(self):
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
        self.apply_current_filter()
        self.update_GUI()


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

    def sanitize_counter_entry(self, entry):
        sanitized = entry.copy()
        sanitized["games"] = f"{self.parse_int(entry.get('games'))}"
        sanitized["popularity"] = f"{self.parse_float(entry.get('popularity')):.2f}"
        sanitized["win_rate"] = f"{self.parse_float(entry.get('win_rate')):.2f}"
        sanitized["win_rate_diff"] = f"{self.parse_float(entry.get('win_rate_diff')):.2f}"
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
