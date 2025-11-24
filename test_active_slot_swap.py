"""
Test for the ACTUAL bug: when lanes are swapped between current slot and empty conflicting slot,
the active slot checkbox should also swap if the conflicting slot had the active checkbox.
"""

import pytest
from unittest.mock import patch

try:
    import tkinter as tk
    TKINTER_AVAILABLE = True
except:
    TKINTER_AVAILABLE = False

from lobby_manager import ChampionScraperApp


@pytest.mark.skipif(not TKINTER_AVAILABLE, reason="Tkinter not available")
class TestActiveSlotSwapWithEmptySlot:
    """Test the REAL bug: active slot not swapping when lanes swap with empty slot."""
    
    def test_active_slot_swaps_when_lanes_swap_with_empty_conflicting_slot(self):
        """
        REAL Bug Scenario:
        1. User manually sets "내 차례" on slot 3 (middle lane, empty)
        2. Tristana (isLocalPlayer=true, bottom) gets assigned to slot 0
        3. Slot 0 wants "bottom" but slot 1 has it (default)
        4. Slot 0 and slot 1 swap lanes (bottom <-> jungle)
        5. Now if slot 1 wants "middle" and slot 3 has it (and is empty)
        6. Slot 1 and slot 3 should swap lanes AND active checkbox
        7. BUG: Active checkbox stays at slot 3 instead of moving to slot 1
        """
        root = tk.Tk()
        root.withdraw()
        app = ChampionScraperApp(root)
        
        try:
            slot0 = app.banpick_slots["allies"][0]
            slot1 = app.banpick_slots["allies"][1]
            slot3 = app.banpick_slots["allies"][3]
            
            # Step 1: Manually set active slot to slot 3 (simulating user clicking "내 차례")
            app.active_slot_var.set("allies:3")
            print(f"\n=== Initial State ===")
            print(f"Slot 0: {slot0['entry'].get()} - {slot0['lane'].get()}")
            print(f"Slot 1: {slot1['entry'].get()} - {slot1['lane'].get()}")
            print(f"Slot 3: {slot3['entry'].get()} - {slot3['lane'].get()}")
            print(f"Active slot: {app.active_slot_var.get()}")
            
            # Step 2: Assign champion to slot 1 with "middle" lane
            # This should trigger swap with slot 3 (which has "middle" and is empty)
            entry_maokai = {
                "display": "Maokai",
                "canonical": "Maokai",
                "normalized": "maokai",
                "isLocalPlayer": False,
                "assignedPosition": "MIDDLE"
            }
            
            with patch.object(app, 'perform_banpick_search', return_value=True):
                app._populate_slot_from_client(slot1, entry_maokai)
            
            print(f"\n=== After Maokai Assignment ===")
            print(f"Slot 1: {slot1['entry'].get()} - {slot1['lane'].get()}")
            print(f"Slot 3: {slot3['entry'].get()} - {slot3['lane'].get()}")
            print(f"Active slot: {app.active_slot_var.get()}")
            
            # Verify Maokai is in slot 1 with middle lane
            assert slot1["entry"].get() == "Maokai"
            assert slot1["lane"].get() == "middle"
            
            # Verify slot 3 no longer has middle (swapped away)
            assert slot3["lane"].get() != "middle"
            
            # CRITICAL BUG: Active slot should have moved from slot 3 to slot 1
            # Because the lanes were swapped
            active_slot = app.active_slot_var.get()
            # This is the bug - active slot stays at slot 3 instead of moving to slot 1
            print(f"\nExpected: allies:1 (should follow the swap)")
            print(f"Actual: {active_slot}")
            
            # This assertion will FAIL, demonstrating the bug
            assert active_slot == "allies:1", \
                f"BUG! Active slot should swap to 'allies:1' but stayed at '{active_slot}'"
            
        finally:
            root.destroy()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
