import tkinter as tk
from tkinter import messagebox, simpledialog
import json
import os
from common import resolve_resource_path

CREDITS_FILE = "credits.json"

class CreditsTab(tk.Frame):
    def __init__(self, notebook, parent):
        super().__init__(notebook)
        self.parent = parent
        self.credits_file_path = resolve_resource_path(CREDITS_FILE)
        self.contributors = self.load_credits()
        
        self.build_ui()

    def build_ui(self):
        # Title
        tk.Label(self, text="고마운 분들 (Contributors)", font=("Segoe UI", 14, "bold")).pack(pady=(15, 10))
        
        # Listbox frame
        list_frame = tk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=20, pady=5)
        
        self.listbox = tk.Listbox(list_frame, font=("Segoe UI", 10))
        self.listbox.pack(side="left", fill="both", expand=True)
        
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)
        
        # Buttons frame
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=20, pady=10)
        
        tk.Button(btn_frame, text="추가 (Add)", command=self.add_contributor, width=12).pack(side="left", padx=(0, 5))
        tk.Button(btn_frame, text="삭제 (Remove)", command=self.remove_contributor, width=12).pack(side="left")
        
        self.refresh_list()

    def load_credits(self):
        # Try to load from local file first (for persistence), then resource path
        local_path = CREDITS_FILE
        if os.path.exists(local_path):
            try:
                with open(local_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return []
        
        # If local file doesn't exist, try resource path (bundled default)
        if os.path.exists(self.credits_file_path):
             try:
                with open(self.credits_file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
             except (json.JSONDecodeError, OSError):
                return []
        return []

    def save_credits(self):
        # Always save to local file for persistence
        try:
            with open(CREDITS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.contributors, f, ensure_ascii=False, indent=2)
        except OSError as e:
            messagebox.showerror("Error", f"저장 실패: {e}")

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        for name in sorted(self.contributors):
            self.listbox.insert(tk.END, name)

    def add_contributor(self):
        name = simpledialog.askstring("추가", "이름을 입력하세요:")
        if name:
            name = name.strip()
            if name and name not in self.contributors:
                self.contributors.append(name)
                self.save_credits()
                self.refresh_list()

    def remove_contributor(self):
        selection = self.listbox.curselection()
        if not selection:
            return
        index = selection[0]
        name = self.listbox.get(index)
        if messagebox.askyesno("삭제", f"'{name}' 님을 목록에서 삭제하시겠습니까?"):
            if name in self.contributors:
                self.contributors.remove(name)
                self.save_credits()
                self.refresh_list()
