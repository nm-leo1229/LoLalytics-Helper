import json
import os
import sys
import tkinter as tk
from unittest.mock import MagicMock

# Import the app class
from lobby_manager import ChampionScraperApp

class MockApp(ChampionScraperApp):
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("LCU Replay Test")
        # Ensure window is visible
        self.root.deiconify()
        super().__init__(self.root)
        self.snapshots = []
        self.current_index = 0
        
    def load_snapshots(self, directory="debug_data"):
        if not os.path.exists(directory):
            print(f"Directory {directory} not found.")
            return
            
        files = [f for f in os.listdir(directory) if f.startswith("snapshot_") and f.endswith(".json")]
        files.sort() # Sort by timestamp (filename)
        
        for f in files:
            path = os.path.join(directory, f)
            try:
                with open(path, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    self.snapshots.append((f, data))
            except Exception as e:
                print(f"Failed to load {f}: {e}")
                
        print(f"Loaded {len(self.snapshots)} snapshots.")

    def start_replay(self, interval_ms=1500, initial_delay_ms=2000):
        if not self.snapshots:
            print("No snapshots to replay.")
            return
        
        print(f"\nStarting replay in {initial_delay_ms/1000:.1f} seconds...")
        print(f"Will replay {len(self.snapshots)} snapshots with {interval_ms/1000:.1f}s interval.\n")
        
        # Schedule first snapshot after initial delay
        self.root.after(initial_delay_ms, lambda: self.replay_step(interval_ms))
        self.root.mainloop()

    def replay_step(self, interval_ms):
        if self.current_index >= len(self.snapshots):
            print("Replay finished.")
            self.root.quit()
            return

        filename, snapshot = self.snapshots[self.current_index]
        self.root.title(f"Replaying: {filename} ({self.current_index + 1}/{len(self.snapshots)})")
        print(f"Applying {filename}...")
        
        # Debug: Print raw assigned positions
        allies = snapshot.get("allies", [])
        print("Raw Allies Data:")
        for a in allies:
            print(f"  {a.get('name')}: {a.get('assignedPosition')}")

        self._apply_client_snapshot(snapshot)
        
        # Verify results
        print("Resulting Slots:")
        lanes_seen = {}
        duplicates_found = False
        for i, slot in enumerate(self.banpick_slots["allies"]):
            name = slot["entry"].get()
            lane = slot["lane"].get()
            print(f"  Slot {i}: {name} - {lane}")
            
            if lane and lane != "라인 선택":
                if lane in lanes_seen:
                    print(f"  [ERROR] Duplicate Lane Detected! {lane} is in Slot {lanes_seen[lane]} and Slot {i}")
                    duplicates_found = True
                lanes_seen[lane] = i
        
        if duplicates_found:
            print("  -> TEST FAILED: Duplicate lanes found in ALLIES team.")
        else:
            print("  -> TEST PASSED: No duplicate lanes in ALLIES team.")

        print("Resulting Slots (Enemies):")
        lanes_seen = {}
        duplicates_found = False
        for i, slot in enumerate(self.banpick_slots["enemies"]):
            name = slot["entry"].get()
            lane = slot["lane"].get()
            print(f"  Slot {i}: {name} - {lane}")
            
            if lane and lane != "라인 선택":
                if lane in lanes_seen:
                    print(f"  [ERROR] Duplicate Lane Detected! {lane} is in Slot {lanes_seen[lane]} and Slot {i}")
                    duplicates_found = True
                lanes_seen[lane] = i
        
        if duplicates_found:
            print("  -> TEST FAILED: Duplicate lanes found in ENEMIES team.")
        else:
            print("  -> TEST PASSED: No duplicate lanes in ENEMIES team.")
        
        self.current_index += 1
        self.root.after(interval_ms, lambda: self.replay_step(interval_ms))

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Replay LCU snapshots for testing")
    parser.add_argument("--interval", type=int, default=1500, 
                       help="Interval between snapshots in milliseconds (default: 1500)")
    parser.add_argument("--initial-delay", type=int, default=2000,
                       help="Initial delay before first snapshot in milliseconds (default: 2000)")
    parser.add_argument("--directory", type=str, default="debug_data",
                       help="Directory containing snapshot files (default: debug_data)")
    
    args = parser.parse_args()
    
    app = MockApp()
    app.load_snapshots(args.directory)
    app.start_replay(interval_ms=args.interval, initial_delay_ms=args.initial_delay)

