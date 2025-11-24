import pytest
import tkinter as tk
from lobby_manager import ChampionScraperApp

class TestSmartLaneAssignment:
    @pytest.fixture
    def app(self):
        root = tk.Tk()
        root.withdraw()
        app = ChampionScraperApp(root)
        yield app
        root.destroy()

    def test_get_champion_lane_pick_rates_viego(self, app):
        # Viego should have high pick rate in jungle
        rates = app._get_champion_lane_pick_rates("Viego")
        print(f"\nViego rates: {rates}")
        assert "jungle" in rates
        assert rates["jungle"] > 1000 # Should be high

    def test_get_champion_lane_pick_rates_amumu(self, app):
        # Amumu should have jungle and support
        rates = app._get_champion_lane_pick_rates("Amumu")
        print(f"\nAmumu rates: {rates}")
        assert "jungle" in rates
        assert "support" in rates
        
    def test_resolve_conflict_viego_amumu_diana(self, app):
        # Scenario: Viego, Amumu, Diana all want jungle originally
        # Viego: Jungle (High)
        # Amumu: Jungle (Med), Support (Low)
        # Diana: Jungle (Med), Middle (Low)
        
        entries = [
            {"canonical": "Viego", "assignedPosition": ""},
            {"canonical": "Amumu", "assignedPosition": ""},
            {"canonical": "Diana", "assignedPosition": ""}
        ]
        
        resolved = app._resolve_lane_conflicts_by_pick_rate("enemies", entries)
        
        assignments = {e["canonical"]: e.get("assignedPosition") for e in resolved}
        print(f"\nAssignments: {assignments}")
        
        # Viego must be jungle (highest pick rate there)
        assert assignments["Viego"] == "jungle"
        
        # Amumu should be support (next best)
        assert assignments["Amumu"] == "support"
        
        # Diana should be middle (next best)
        assert assignments["Diana"] == "middle"

    def test_resolve_conflict_with_existing_assignment(self, app):
        # Scenario: Viego has assignedPosition='jungle', Amumu has ''
        entries = [
            {"canonical": "Viego", "assignedPosition": "jungle"},
            {"canonical": "Amumu", "assignedPosition": ""}
        ]
        
        resolved = app._resolve_lane_conflicts_by_pick_rate("enemies", entries)
        assignments = {e["canonical"]: e.get("assignedPosition") for e in resolved}
        print(f"\nAssignments with existing: {assignments}")
        
        assert assignments["Viego"] == "jungle"
        assert assignments["Amumu"] == "support" # Should fall back to support

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
