"""
Regression test for duplicate lane bug.
This test reproduces the issue where multiple champions end up in the same lane.
"""

import pytest
import json
from unittest.mock import patch, MagicMock

try:
    import tkinter as tk
    TKINTER_AVAILABLE = True
except:
    TKINTER_AVAILABLE = False

from lobby_manager import ChampionScraperApp


@pytest.mark.skipif(not TKINTER_AVAILABLE, reason="Tkinter not available")
class TestDuplicateLaneBugFix:
    """Test for the duplicate lane bug found in snapshot replay."""
    
    def test_no_duplicate_lanes_after_sorting(self):
        """Test that lane sorting doesn't create duplicates."""
        root = tk.Tk()
        root.withdraw()
        app = ChampionScraperApp(root)
        
        try:
            # Simulate snapshot with multiple champions
            snapshot = {
                "phase": "BAN_PICK",
                "allies": [
                    {"name": "트리스타나", "championId": 18, "assignedPosition": "bottom", "isLocalPlayer": True},
                    {"name": "리 신", "championId": 64, "assignedPosition": "jungle", "isLocalPlayer": False},
                    {"name": "쉔", "championId": 98, "assignedPosition": "top", "isLocalPlayer": False}
                ],
                "enemies": []
            }
            
            # Apply snapshot
            with patch.object(app, 'perform_banpick_search', return_value=True):
                app._apply_client_snapshot(snapshot)
            
            # Check for duplicate lanes
            lanes_seen = {}
            duplicates = []
            
            for i, slot in enumerate(app.banpick_slots["allies"]):
                lane = slot["lane"].get()
                if lane and lane != "라인 선택":
                    if lane in lanes_seen:
                        duplicates.append({
                            "lane": lane,
                            "slot1": lanes_seen[lane],
                            "slot2": i
                        })
                    lanes_seen[lane] = i
            
            # Assert no duplicates
            assert len(duplicates) == 0, f"Found duplicate lanes: {duplicates}"
            
        finally:
            root.destroy()
    
    def test_sequential_snapshots_no_duplicates(self):
        """Test that applying sequential snapshots doesn't create duplicates."""
        root = tk.Tk()
        root.withdraw()
        app = ChampionScraperApp(root)
        
        try:
            # First snapshot: 1 champion
            snapshot1 = {
                "allies": [
                    {"name": "쉔", "championId": 98, "assignedPosition": "top", "isLocalPlayer": False}
                ],
                "enemies": []
            }
            
            # Second snapshot: 2 champions (one new)
            snapshot2 = {
                "allies": [
                    {"name": "리 신", "championId": 64, "assignedPosition": "jungle", "isLocalPlayer": False},
                    {"name": "쉔", "championId": 98, "assignedPosition": "top", "isLocalPlayer": False}
                ],
                "enemies": []
            }
            
            # Third snapshot: 3 champions (one more new)
            snapshot3 = {
                "allies": [
                    {"name": "트리스타나", "championId": 18, "assignedPosition": "bottom", "isLocalPlayer": True},
                    {"name": "리 신", "championId": 64, "assignedPosition": "jungle", "isLocalPlayer": False},
                    {"name": "쉔", "championId": 98, "assignedPosition": "top", "isLocalPlayer": False}
                ],
                "enemies": []
            }
            
            # Apply snapshots sequentially
            with patch.object(app, 'perform_banpick_search', return_value=True):
                for snapshot in [snapshot1, snapshot2, snapshot3]:
                    app._apply_client_snapshot(snapshot)
                    
                    # Check for duplicates after each snapshot
                    lanes_seen = {}
                    duplicates = []
                    
                    for i, slot in enumerate(app.banpick_slots["allies"]):
                        lane = slot["lane"].get()
                        name = slot["entry"].get()
                        
                        if lane and lane != "라인 선택":
                            if lane in lanes_seen:
                                duplicates.append({
                                    "lane": lane,
                                    "slot1": lanes_seen[lane],
                                    "slot2": i,
                                    "name": name
                                })
                            lanes_seen[lane] = i
                    
                    # Assert no duplicates after each snapshot
                    assert len(duplicates) == 0, f"Found duplicate lanes after applying snapshot: {duplicates}"
            
        finally:
            root.destroy()
    
    def test_lane_sorting_preserves_uniqueness(self):
        """Test that the lane sorting algorithm maintains unique lanes per slot."""
        root = tk.Tk()
        root.withdraw()
        app = ChampionScraperApp(root)
        
        try:
            # Create entries that will be sorted
            entries = [
                {"display": "Thresh", "canonical": "Thresh", "normalized": "thresh",
                 "isLocalPlayer": False, "assignedPosition": "UTILITY"},
                {"display": "Jinx", "canonical": "Jinx", "normalized": "jinx",
                 "isLocalPlayer": False, "assignedPosition": "BOTTOM"},
                {"display": "Ahri", "canonical": "Ahri", "normalized": "ahri",
                 "isLocalPlayer": False, "assignedPosition": "MIDDLE"},
                {"display": "Lee Sin", "canonical": "Lee Sin", "normalized": "leesin",
                 "isLocalPlayer": False, "assignedPosition": "JUNGLE"},
                {"display": "Garen", "canonical": "Garen", "normalized": "garen",
                 "isLocalPlayer": False, "assignedPosition": "TOP"}
            ]
            
            # Apply entries
            with patch.object(app, 'perform_banpick_search', return_value=True):
                app._populate_side_from_client("allies", entries)
            
            # Collect all lanes
            lanes = []
            for slot in app.banpick_slots["allies"]:
                lane = slot["lane"].get()
                if lane and lane != "라인 선택":
                    lanes.append(lane)
            
            # Check for duplicates
            assert len(lanes) == len(set(lanes)), f"Duplicate lanes found: {lanes}"
            
        finally:
            root.destroy()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
