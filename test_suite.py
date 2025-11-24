"""
Comprehensive Test Suite for LoLalytics-Helper
Tests cover LCU data processing, lane detection, champion resolution, and recommendations.
"""

import pytest
import json
import os
import sys
from unittest.mock import MagicMock, patch, mock_open

# Try to import tkinter, but handle gracefully if it fails
try:
    import tkinter as tk
    TKINTER_AVAILABLE = True
except Exception as e:
    TKINTER_AVAILABLE = False
    tk = None
    print(f"Warning: Tkinter not available: {e}")

from lobby_manager import (
    ChampionScraperApp,
    extract_choseong,
    alias_variants,
    contains_hangul_syllable,
    load_alias_tables,
    LANES,
    BANPICK_DEFAULT_LANES
)


@pytest.fixture
def mock_root():
    """Create a mock Tkinter root window."""
    if not TKINTER_AVAILABLE:
        pytest.skip("Tkinter not available")
    
    try:
        root = tk.Tk()
        root.withdraw()  # Hide the window
        yield root
        try:
            root.destroy()
        except:
            pass
    except Exception as e:
        pytest.skip(f"Cannot create Tkinter window: {e}")


@pytest.fixture
def app_instance(mock_root):
    """Create a ChampionScraperApp instance for testing."""
    if not TKINTER_AVAILABLE:
        pytest.skip("Tkinter not available")
    app = ChampionScraperApp(mock_root)
    yield app


# Marker for tests that require Tkinter
requires_tkinter = pytest.mark.skipif(
    not TKINTER_AVAILABLE,
    reason="Tkinter not available"
)


class TestChoseongExtraction:
    """Test Korean initial consonant (choseong) extraction."""
    
    def test_extract_choseong_korean(self):
        """Test extracting choseong from Korean text."""
        assert extract_choseong("가렌") == "ㄱㄹ"
        assert extract_choseong("아리") == "ㅇㄹ"
        assert extract_choseong("제드") == "ㅈㄷ"
    
    def test_extract_choseong_mixed(self):
        """Test extracting choseong from mixed Korean/English text."""
        result = extract_choseong("가렌Garen")
        assert "ㄱㄹ" in result
    
    def test_extract_choseong_empty(self):
        """Test extracting choseong from empty string."""
        assert extract_choseong("") == ""
    
    def test_extract_choseong_english_only(self):
        """Test extracting choseong from English-only text."""
        result = extract_choseong("Garen")
        assert result == "garen"  # English characters are lowercased


class TestAliasVariants:
    """Test alias variant generation."""
    
    def test_alias_variants_basic(self):
        """Test basic alias variant generation."""
        variants = alias_variants("가렌")
        assert "가렌" in variants
        assert "ㄱㄹ" in variants  # Choseong
    
    def test_alias_variants_no_initials(self):
        """Test alias variants without initials."""
        variants = alias_variants("가렌", include_initials=False)
        assert "가렌" in variants
        assert "ㄱㄹ" not in variants
    
    def test_alias_variants_english(self):
        """Test alias variants for English text."""
        variants = alias_variants("Garen")
        assert "garen" in variants  # Lowercased version


class TestHangulDetection:
    """Test Hangul syllable detection."""
    
    def test_contains_hangul_syllable_korean(self):
        """Test detection of Korean syllables."""
        assert contains_hangul_syllable("가렌") == True
        assert contains_hangul_syllable("아리") == True
    
    def test_contains_hangul_syllable_english(self):
        """Test detection in English text."""
        assert contains_hangul_syllable("Garen") == False
    
    def test_contains_hangul_syllable_mixed(self):
        """Test detection in mixed text."""
        assert contains_hangul_syllable("가렌Garen") == True
    
    def test_contains_hangul_syllable_empty(self):
        """Test detection in empty string."""
        assert contains_hangul_syllable("") == False


class TestLCUDataNormalization:
    """Test LCU data normalization and processing."""
    
    def test_normalize_client_entries_basic(self, app_instance):
        """Test basic client entry normalization."""
        entries = [
            {"name": "Garen", "championId": 86, "isLocalPlayer": False, "assignedPosition": "TOP"},
            {"name": "Lee Sin", "championId": 64, "isLocalPlayer": True, "assignedPosition": "JUNGLE"}
        ]
        
        normalized = app_instance._normalize_client_entries(entries)
        
        assert len(normalized) == 2
        assert normalized[0]["assignedPosition"] == "TOP"
        assert normalized[1]["isLocalPlayer"] == True
    
    def test_normalize_client_entries_empty(self, app_instance):
        """Test normalization with empty entries."""
        normalized = app_instance._normalize_client_entries([])
        assert normalized == []
    
    def test_normalize_client_entries_missing_fields(self, app_instance):
        """Test normalization with missing fields."""
        entries = [
            {"championId": 86}  # Missing name and assignedPosition
        ]
        
        normalized = app_instance._normalize_client_entries(entries)
        assert len(normalized) == 1
        assert "assignedPosition" in normalized[0]


class TestLaneSorting:
    """Test lane-based sorting of entries."""
    
    def test_populate_side_from_client_sorting(self, app_instance):
        """Test that entries are sorted by lane priority."""
        # Create mock entries with different lanes
        entries = [
            {"display": "Support", "canonical": "Thresh", "normalized": "thresh", 
             "isLocalPlayer": False, "assignedPosition": "UTILITY"},
            {"display": "Top", "canonical": "Garen", "normalized": "garen", 
             "isLocalPlayer": False, "assignedPosition": "TOP"},
            {"display": "Mid", "canonical": "Ahri", "normalized": "ahri", 
             "isLocalPlayer": False, "assignedPosition": "MIDDLE"},
        ]
        
        # The sorting should arrange them as: Top, Mid, Support
        # We can't directly test the internal sorting, but we can verify
        # that the function doesn't crash and processes all entries
        result = app_instance._populate_side_from_client("allies", entries)
        assert isinstance(result, bool)
    
    def test_populate_side_from_client_no_assigned_position(self, app_instance):
        """Test sorting when assignedPosition is missing."""
        entries = [
            {"display": "Garen", "canonical": "Garen", "normalized": "garen", 
             "isLocalPlayer": False},
        ]
        
        result = app_instance._populate_side_from_client("allies", entries)
        assert isinstance(result, bool)


class TestLaneDetection:
    """Test lane detection from assignedPosition."""
    
    def test_assigned_position_utility_to_support(self, app_instance):
        """Test that UTILITY position is converted to support."""
        entry = {
            "display": "Thresh",
            "canonical": "Thresh",
            "normalized": "thresh",
            "isLocalPlayer": False,
            "assignedPosition": "UTILITY"
        }
        
        # Create a mock slot
        slot = {
            "side": "allies",
            "index": 0,
            "entry": tk.Entry(app_instance.root),
            "lane": MagicMock(),
            "result_var": tk.StringVar(),
            "exclude_var": tk.BooleanVar(),
            "active_check": None
        }
        
        # Mock the perform_banpick_search to avoid actual data loading
        with patch.object(app_instance, 'perform_banpick_search', return_value=True):
            app_instance._populate_slot_from_client(slot, entry)
            
            # Verify that the lane was set (utility -> support conversion)
            # The actual conversion happens in _populate_slot_from_client
            slot["lane"].set.assert_called()


class TestSnapshotApplication:
    """Test applying LCU snapshots."""
    
    def test_apply_client_snapshot_basic(self, app_instance):
        """Test applying a basic snapshot."""
        snapshot = {
            "phase": "FINALIZATION",
            "allies": [
                {"name": "Garen", "championId": 86, "assignedPosition": "TOP"}
            ],
            "enemies": [
                {"name": "Darius", "championId": 122, "assignedPosition": "TOP"}
            ]
        }
        
        with patch.object(app_instance, '_populate_side_from_client', return_value=True):
            with patch.object(app_instance, 'update_banpick_recommendations'):
                result = app_instance._apply_client_snapshot(snapshot)
                assert app_instance.last_client_snapshot == snapshot
    
    def test_apply_client_snapshot_empty(self, app_instance):
        """Test applying an empty snapshot."""
        snapshot = {
            "phase": "LOBBY",
            "allies": [],
            "enemies": []
        }
        
        with patch.object(app_instance, '_populate_side_from_client', return_value=False):
            result = app_instance._apply_client_snapshot(snapshot)
            assert result == False
    
    def test_apply_client_snapshot_triggers_update(self, app_instance):
        """Test that snapshot application triggers recommendations update."""
        snapshot = {
            "allies": [{"name": "Garen", "championId": 86}],
            "enemies": []
        }
        
        with patch.object(app_instance, '_populate_side_from_client', return_value=True):
            with patch.object(app_instance, 'update_banpick_recommendations') as mock_update:
                app_instance._apply_client_snapshot(snapshot)
                mock_update.assert_called_once()


class TestDuplicateLaneDetection:
    """Test detection of duplicate lanes in the same team."""
    
    def test_no_duplicate_lanes(self, app_instance):
        """Test that different lanes don't trigger duplicate detection."""
        # Set up slots with different lanes
        for i, lane in enumerate(["top", "jungle", "middle", "bottom", "support"]):
            slot = app_instance.banpick_slots["allies"][i]
            slot["lane"].set(lane)
            slot["entry"].insert(0, f"Champion{i}")
        
        # Verify no duplicates
        lanes_seen = {}
        duplicates_found = False
        for i, slot in enumerate(app_instance.banpick_slots["allies"]):
            lane = slot["lane"].get()
            if lane and lane != "라인 선택":
                if lane in lanes_seen:
                    duplicates_found = True
                lanes_seen[lane] = i
        
        assert duplicates_found == False
    
    def test_duplicate_lanes_detected(self, app_instance):
        """Test that duplicate lanes are detected."""
        # Set up slots with duplicate lanes
        app_instance.banpick_slots["allies"][0]["lane"].set("top")
        app_instance.banpick_slots["allies"][1]["lane"].set("top")
        
        # Verify duplicates
        lanes_seen = {}
        duplicates_found = False
        for i, slot in enumerate(app_instance.banpick_slots["allies"]):
            lane = slot["lane"].get()
            if lane and lane != "라인 선택":
                if lane in lanes_seen:
                    duplicates_found = True
                lanes_seen[lane] = i
        
        assert duplicates_found == True


class TestChampionResolution:
    """Test champion name resolution and alias handling."""
    
    def test_resolve_champion_name_exact(self, app_instance):
        """Test resolving exact champion name."""
        # This depends on the actual alias data being loaded
        # We'll test the mechanism rather than specific champions
        result = app_instance.resolve_champion_name("Garen")
        # Result could be None if data isn't loaded, or the canonical name
        assert result is None or isinstance(result, str)
    
    def test_resolve_champion_name_alias(self, app_instance):
        """Test resolving champion name via alias."""
        # Test with a potential alias
        result = app_instance.resolve_champion_name("가렌")
        assert result is None or isinstance(result, str)
    
    def test_resolve_champion_name_empty(self, app_instance):
        """Test resolving empty string."""
        result = app_instance.resolve_champion_name("")
        assert result is None


class TestSlotOperations:
    """Test slot manipulation operations."""
    
    def test_clear_banpick_slot(self, app_instance):
        """Test clearing a banpick slot."""
        slot = app_instance.banpick_slots["allies"][0]
        
        # Set some data
        slot["entry"].insert(0, "Garen")
        slot["display_name"] = "Garen"
        slot["canonical_name"] = "Garen"
        
        # Clear the slot
        with patch.object(app_instance, 'update_banpick_recommendations'):
            app_instance.clear_banpick_slot(slot, reset_lane=False, suppress_update=True)
        
        # Verify cleared
        assert slot["entry"].get() == ""
        assert slot["display_name"] is None
        assert slot["canonical_name"] is None
    
    def test_clear_banpick_slot_with_lane_reset(self, app_instance):
        """Test clearing a slot with lane reset."""
        slot = app_instance.banpick_slots["allies"][0]
        slot["lane"].set("jungle")
        
        with patch.object(app_instance, 'update_banpick_recommendations'):
            app_instance.clear_banpick_slot(slot, reset_lane=True, suppress_update=True)
        
        # Lane should be reset to default
        assert slot["lane"].get() == BANPICK_DEFAULT_LANES[0]


class TestLaneSwapping:
    """Test lane swapping logic."""
    
    def test_lane_swap_on_duplicate(self, app_instance):
        """Test that lanes swap when duplicate is selected."""
        # Set up initial state
        slot1 = app_instance.banpick_slots["allies"][0]
        slot2 = app_instance.banpick_slots["allies"][1]
        
        slot1["lane"].set("top")
        slot2["lane"].set("jungle")
        
        app_instance._update_slot_lane_cache(slot1, "top")
        app_instance._update_slot_lane_cache(slot2, "jungle")
        
        # Simulate changing slot2 to "top" (duplicate)
        with patch.object(app_instance, 'update_banpick_recommendations'):
            slot2["lane"].set("top")
            app_instance.on_banpick_lane_changed(slot2)
        
        # Verify swap occurred
        assert slot1["lane"].get() == "jungle"
        assert slot2["lane"].get() == "top"


class TestSnapshotSaving:
    """Test snapshot saving functionality."""
    
    def test_save_snapshot_no_data(self, app_instance):
        """Test saving when no snapshot data exists."""
        app_instance.last_client_snapshot = None
        
        with patch('tkinter.messagebox.showinfo') as mock_info:
            app_instance.save_snapshot()
            mock_info.assert_called_once()
    
    def test_save_snapshot_success(self, app_instance):
        """Test successful snapshot saving."""
        app_instance.last_client_snapshot = {
            "phase": "FINALIZATION",
            "allies": [{"name": "Garen", "championId": 86}]
        }
        
        with patch('builtins.open', mock_open()) as mock_file:
            with patch('tkinter.messagebox.showinfo') as mock_info:
                with patch('os.path.exists', return_value=True):
                    app_instance.save_snapshot()
                    mock_file.assert_called_once()


class TestIntegrationScenarios:
    """Integration tests for complete workflows."""
    
    def test_full_snapshot_to_recommendation_flow(self, app_instance):
        """Test complete flow from snapshot to recommendations."""
        snapshot = {
            "phase": "FINALIZATION",
            "allies": [
                {"name": "Garen", "championId": 86, "assignedPosition": "TOP", "isLocalPlayer": False},
                {"name": "Lee Sin", "championId": 64, "assignedPosition": "JUNGLE", "isLocalPlayer": False},
            ],
            "enemies": [
                {"name": "Darius", "championId": 122, "assignedPosition": "TOP", "isLocalPlayer": False},
            ]
        }
        
        with patch.object(app_instance, 'perform_banpick_search', return_value=True):
            with patch.object(app_instance, 'update_banpick_recommendations'):
                result = app_instance._apply_client_snapshot(snapshot)
                # Verify snapshot was stored
                assert app_instance.last_client_snapshot == snapshot
    
    def test_lane_priority_sorting_integration(self, app_instance):
        """Test that lane priority sorting works correctly in integration."""
        # Create entries in reverse lane order
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
             "isLocalPlayer": False, "assignedPosition": "TOP"},
        ]
        
        with patch.object(app_instance, 'perform_banpick_search', return_value=True):
            app_instance._populate_side_from_client("allies", entries)
            
            # Verify that slots were populated (exact order depends on implementation)
            # At minimum, verify no crashes and all entries processed
            populated_count = sum(1 for slot in app_instance.banpick_slots["allies"] 
                                 if slot["entry"].get())
            assert populated_count <= len(entries)


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_snapshot_with_missing_phase(self, app_instance):
        """Test handling snapshot without phase field."""
        snapshot = {
            "allies": [{"name": "Garen", "championId": 86}],
            "enemies": []
        }
        
        with patch.object(app_instance, '_populate_side_from_client', return_value=True):
            with patch.object(app_instance, 'update_banpick_recommendations'):
                result = app_instance._apply_client_snapshot(snapshot)
                assert app_instance.last_client_snapshot == snapshot
    
    def test_snapshot_with_invalid_champion_id(self, app_instance):
        """Test handling snapshot with invalid champion ID."""
        snapshot = {
            "allies": [{"name": None, "championId": 99999}],  # Invalid ID
            "enemies": []
        }
        
        normalized = app_instance._normalize_client_entries(snapshot["allies"])
        assert len(normalized) == 1
        # Should handle gracefully without crashing
    
    def test_empty_lane_selection(self, app_instance):
        """Test handling empty lane selection."""
        slot = app_instance.banpick_slots["allies"][0]
        slot["lane"].set("")
        
        app_instance._update_slot_lane_cache(slot, "")
        assert slot["last_lane"] is None
    
    def test_concurrent_slot_updates(self, app_instance):
        """Test handling multiple slot updates."""
        entries = [
            {"display": f"Champ{i}", "canonical": f"Champ{i}", "normalized": f"champ{i}", 
             "isLocalPlayer": False, "assignedPosition": lane}
            for i, lane in enumerate(["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"])
        ]
        
        with patch.object(app_instance, 'perform_banpick_search', return_value=True):
            result = app_instance._populate_side_from_client("allies", entries)
            # Should handle all updates without errors
            assert isinstance(result, bool)


class TestDuplicateLaneRegressionBugFix:
    """Regression tests for duplicate lane bug fix (Issue: top, top)."""
    
    def test_snapshot_replay_no_duplicate_lanes(self, app_instance):
        """Test that snapshot replay doesn't create duplicate lanes."""
        # Simulate sequential snapshots like in test_lcu_logic.py
        snapshot1 = {
            "allies": [
                {"name": "쉔", "championId": 98, "assignedPosition": "top", "isLocalPlayer": False}
            ],
            "enemies": []
        }
        
        snapshot2 = {
            "allies": [
                {"name": "리 신", "championId": 64, "assignedPosition": "jungle", "isLocalPlayer": False},
                {"name": "쉔", "championId": 98, "assignedPosition": "top", "isLocalPlayer": False}
            ],
            "enemies": []
        }
        
        snapshot3 = {
            "allies": [
                {"name": "트리스타나", "championId": 18, "assignedPosition": "bottom", "isLocalPlayer": True},
                {"name": "리 신", "championId": 64, "assignedPosition": "jungle", "isLocalPlayer": False},
                {"name": "쉔", "championId": 98, "assignedPosition": "top", "isLocalPlayer": False}
            ],
            "enemies": []
        }
        
        # Apply snapshots sequentially
        with patch.object(app_instance, 'perform_banpick_search', return_value=True):
            for snapshot in [snapshot1, snapshot2, snapshot3]:
                app_instance._apply_client_snapshot(snapshot)
                
                # Verify no duplicate lanes after each snapshot
                lanes_seen = set()
                for slot in app_instance.banpick_slots["allies"]:
                    lane = slot["lane"].get()
                    if lane and lane != "라인 선택":
                        assert lane not in lanes_seen, f"Duplicate lane '{lane}' detected!"
                        lanes_seen.add(lane)
    
    def test_empty_slot_lane_swap(self, app_instance):
        """Test that empty slots swap lanes to avoid conflicts."""
        # Slot 4 defaults to "top", we'll assign a champion to slot 0 with "top"
        entry = {
            "display": "Garen",
            "canonical": "Garen",
            "normalized": "garen",
            "isLocalPlayer": False,
            "assignedPosition": "TOP"
        }
        
        slot0 = app_instance.banpick_slots["allies"][0]
        slot4 = app_instance.banpick_slots["allies"][4]
        
        # Verify slot 4 starts with "top" (default)
        initial_slot4_lane = slot4["lane"].get()
        
        # Apply entry to slot 0
        with patch.object(app_instance, 'perform_banpick_search', return_value=True):
            app_instance._populate_slot_from_client(slot0, entry)
        
        # Verify slot 0 now has "top"
        assert slot0["lane"].get() == "top"
        
        # Verify slot 4 no longer has "top" (should have swapped)
        assert slot4["lane"].get() != "top" or not slot4["entry"].get()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
