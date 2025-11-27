"""
Parse champion data from text files and create a champion-lane mapping.
Each champion entry has 15 lines in the following order:
1. Rank
2. ChampionIcon (ignored)
3. ChampionName
4. Tier
5. LanePercent
6. WinRate
7. Pickrate (with +/- prefix)
8. BanRate
9. PBI
10. Games
11. WorldwideRank
12. WorldwideWinRate
13. WorldwideGames
14. WorldwideDelta
15. WorldwideElo
"""

import json
import os

LANES = ['top', 'jungle', 'middle', 'bottom', 'support']

def parse_champion_file(filepath):
    """Parse a champion data file and extract all champions."""
    champions = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines()]
        
        # Process in chunks of 17 lines
        # Line structure:
        # 0: Rank
        # 1: ChampionIcon (duplicate name)
        # 2: ChampionName
        # 3: Tier
        # 4: LanePercent
        # 5: WinRate
        # 6: Pickrate (with +/- prefix)
        # 7: BanRate
        # 8: PBI
        # 9: Games
        # 10: WorldwideRank
        # 11: WorldwideWinRate
        # 12: WorldwideGames
        # 13: WorldwideDelta
        # 14: WorldwideElo
        # 15-16: Extra lines (abbreviated elo)
        
        for i in range(0, len(lines), 17):
            if i + 16 >= len(lines):
                break  # Not enough lines for a complete entry
            
            try:
                champion_name = lines[i + 2]  # Line 3 (0-indexed as 2)
                tier = lines[i + 3]
                win_rate = lines[i + 5]
                pickrate_str = lines[i + 7]  # Line 8 (0-indexed as 7) - actual pickrate
                
                # Parse pick rate (remove +/- prefix and convert to float)
                try:
                    pickrate = float(pickrate_str.replace('+', '').replace('-', ''))
                except ValueError:
                    continue
                
                # Include all champions (no pick rate filter)
                champions.append({
                    'name': champion_name.lower(),
                    'pick_rate': pickrate,
                    'win_rate': win_rate,
                    'tier': tier
                })
                    
            except (IndexError, ValueError) as e:
                # Skip malformed entries
                continue
        
    except FileNotFoundError:
        print(f"Warning: File not found: {filepath}")
        return []
    
    return champions

def collect_all_champions():
    """Collect champions from all lane files."""
    lane_champions = {}
    
    for lane in LANES:
        filename = f"champion_{lane}_data.txt"
        filepath = os.path.join(os.path.dirname(__file__), filename)
        
        print(f"Parsing {filename}...")
        champions = parse_champion_file(filepath)
        lane_champions[lane] = champions
        print(f"  Found {len(champions)} champions")
    
    return lane_champions

def save_champion_list(lane_champions):
    """Save the collected champion list to a JSON file."""
    output_file = "champion_lane_list.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(lane_champions, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*50}")
    print(f"Saved champion list to {output_file}")
    
    # Print summary
    total = sum(len(champs) for champs in lane_champions.values())
    print(f"\nSummary:")
    for lane, champs in lane_champions.items():
        print(f"  {lane}: {len(champs)} champions")
    print(f"  Total: {total} champion-lane combinations")
    print(f"{'='*50}")
    
    # Print some examples
    print(f"\nExample champions:")
    for lane, champs in lane_champions.items():
        if champs:
            print(f"  {lane}: {', '.join([c['name'] for c in champs[:5]])}...")

if __name__ == "__main__":
    print("="*50)
    print("Parsing champion data from text files")
    print("="*50)
    print()
    
    lane_champions = collect_all_champions()
    save_champion_list(lane_champions)
    
    print("\nDone!")
