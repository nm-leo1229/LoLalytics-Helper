import tkinter as tk
import re
import os
import sys

LANES = ['top', 'jungle', 'middle', 'bottom', 'support']
COUNTER_LOW_GAMES_DEFAULT = 1500
SYNERGY_LOW_GAMES_DEFAULT = 1500
LOW_SAMPLE_COLOR = "#888888"
NORMAL_SAMPLE_COLOR = "#111111"
WARNING_ICON = "⚠"

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

            if len(prefix_matches) + len(word_matches) >= self.max_results:
                break

        combined = prefix_matches + word_matches
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


class ScoreTooltip:
    """마우스 호버 시 점수 계산 상세 정보를 표시하는 툴팁"""
    
    def __init__(self, widget, text_provider):
        """
        widget: 툴팁을 표시할 위젯
        text_provider: 툴팁 텍스트를 반환하는 콜백 함수 (동적으로 텍스트 생성)
        """
        self.widget = widget
        self.text_provider = text_provider
        self.tooltip_window = None
        self.show_delay = 500  # ms
        self.show_job = None
        
        self.widget.bind("<Enter>", self._on_enter, add="+")
        self.widget.bind("<Leave>", self._on_leave, add="+")
        self.widget.bind("<ButtonPress>", self._on_leave, add="+")
    
    def _on_enter(self, event):
        self._cancel_show()
        self.show_job = self.widget.after(self.show_delay, self._show_tooltip)
    
    def _on_leave(self, event):
        self._cancel_show()
        self._hide_tooltip()
    
    def _cancel_show(self):
        if self.show_job:
            self.widget.after_cancel(self.show_job)
            self.show_job = None
    
    def _show_tooltip(self):
        if self.tooltip_window:
            return
        
        text = self.text_provider()
        if not text:
            return
        
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.attributes("-topmost", True)
        
        # 스타일링
        frame = tk.Frame(
            self.tooltip_window,
            background="#FFFDE7",  # 밝은 노란색 배경
            borderwidth=1,
            relief="solid"
        )
        frame.pack(fill="both", expand=True)
        
        label = tk.Label(
            frame,
            text=text,
            justify="left",
            background="#FFFDE7",
            foreground="#5D4037",
            font=("Consolas", 9),
            padx=8,
            pady=6
        )
        label.pack()
        
        # 위치 조정 (화면 밖으로 나가지 않도록)
        self.tooltip_window.update_idletasks()
        screen_width = self.widget.winfo_screenwidth()
        screen_height = self.widget.winfo_screenheight()
        tooltip_width = self.tooltip_window.winfo_reqwidth()
        tooltip_height = self.tooltip_window.winfo_reqheight()
        
        if x + tooltip_width > screen_width:
            x = screen_width - tooltip_width - 10
        if y + tooltip_height > screen_height:
            y = self.widget.winfo_rooty() - tooltip_height - 5
        
        self.tooltip_window.geometry(f"+{x}+{y}")
    
    def _hide_tooltip(self):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
    
    def update_text_provider(self, text_provider):
        """텍스트 제공자 업데이트"""
        self.text_provider = text_provider

