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

def parse_champion_file(filepath, min_pick_rate=0.5):
    """Parse a champion data file and extract all champions."""
    champions = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines()]
        
        # Helper to check if a string looks like a Tier
        def is_tier(s):
            return s in ['S+', 'S', 'S-', 'A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-']

        i = 0
        while i < len(lines) - 5: 
            # Look for two consecutive identical lines which indicate a champion name
            # Pattern:
            # Rank
            # Name (Icon text)
            # Name (Visible text)
            # Tier
            if lines[i] == lines[i+1] and lines[i] and not lines[i].replace('.', '').replace('-', '').replace('+', '').isnumeric():
                name = lines[i]
                
                # Check if what we found is actually a Tier (just in case of weird data coincidence)
                if is_tier(name):
                    print(f"Skipping potential false positive: {name}")
                    i += 1
                    continue

                # The line after the second name should be the Tier
                tier_candidate = lines[i+2]
                
                if not is_tier(tier_candidate):
                    # If the immediate next line isn't a tier, maybe we found a "Rank" and "Name" that happened to match? (Unlikely)
                    # Or the file format is slightly different here.
                    # Attempt to find tier in the next few lines?
                    # For now, let's log an error if this structure is violated
                     print(f"Warning: Found duplicate name '{name}' at line {i+1}, but followed by '{tier_candidate}' instead of a Tier.")
                     i += 1
                     continue
                
                tier = tier_candidate
                
                # Scan ahead to find pick rate. 
                # Pick rate usually has a '+' or '-' prefix, or acts as a percentage.
                # In the observed file:
                # Name
                # Name
                # Tier
                # LanePercent e.g. "bottom lane98.21"
                # WinRate e.g. "52.23"
                # PickDelta? e.g. "+0.50"
                # PickRate? 
                
                # Let's look at the example data:
                # 36: Yasuo (Rank)
                # 37: Yasuo (Name 1)
                # 38: Yasuo (Name 2) -- FOUND MATCH at i=37
                # 39: S- (Tier)
                # 40: bottom lane8.35
                # 41: 52.52 (Win Rate?)
                # 42: 0.91 (Pick Rate? Or Delta?)
                
                # Another example: Miss Fortune
                # 2: MissFortune
                # 3: MissFortune -- MATCH
                # 4: S+ (Tier)
                # 5: bottom lane98.21
                # 6: 52.23
                # 7: +0.50
                # 8: 17.69 (Pick Rate?)
                
                # It seems the data after Tier varies.
                # However, we can reliably find the pick rate line by finding the line with % or just taking the relative position if consistent relative to WinRate?
                # Actually, looking at the previous code, it expected:
                # 0: Rank
                # 1: Name 1
                # 2: Name 2
                # 3: Tier
                # 4: LanePercent
                # 5: WinRate
                # 6: Delta? (+/-)
                # 7: PickRate?
                
                # Let's try to identify lines by content.
                # Tier is at i+2.
                # LanePercent is at i+3 (contains "lane").
                # WinRate is likely i+4 (float).
                # Delta is likely i+5 (starts with + or -).
                # PickRate is likely i+6 (float).
                
                # Let's verify with "Yasuo" (16 lines block, might be missing Delta?)
                # Yasuo Lines:
                # Yasuo
                # Yasuo
                # S-
                # bottom lane8.35
                # 52.52
                # 0.91  <-- This looks like Delta or PickRate?
                # 16.36 <-- This looks like Ban Rate?
                
                # Wait, looking at file content for Yasuo (lines 36-50):
                # 36: Yasuo (Rank/ID) -> wait "3" is line 35. "Yasuo" is 36? No line 36 is "Yasuo" in my view?
                # Let's re-read the file view output carefully.
                
                # Line 35: 3 (Rank)
                # Line 36: Yasuo
                # Line 37: Yasuo
                # Line 38: S-
                # Line 39: bottom lane8.35
                # Line 40: 52.52
                # Line 41: 0.91  <-- No +/- ? 
                # Line 42: 16.36
                
                # Compare to Miss Fortune:
                # Line 1: 1
                # Line 2: MissFortune
                # Line 3: MissFortune
                # Line 4: S+
                # Line 5: bottom lane98.21
                # Line 6: 52.23
                # Line 7: +0.50
                # Line 8: 17.69
                
                # So Yasuo is missing the "+" on line 41? Or is it a different field?
                # The previous parser used line index 7 (relative to start 0).
                # If start=Rank, Name1 is 1, Name2 is 2.
                # Match found at Name1 (i). 
                # i = Name1
                # i+1 = Name2
                # i+2 = Tier
                # i+3 = LanePercent
                # i+4 = WinRate
                # i+5 = Delta (Might be missing +/- or just a number)
                # i+6 = PickRate (This is what we want... or is it?)
                
                # In MissFortune (17 lines):
                # Rank (0)
                # Name (1)
                # Name (2) -> Match
                # Tier (3)
                # Lane% (4)
                # Win (5)
                # Delta (6) (+0.50)
                # Pick (7) (17.69)
                
                # In Yasuo (16 lines? or just missing text?):
                # Rank (0)
                # Name (1)
                # Name (2) -> Match at i
                # Tier (3) -> i+2
                # Lane% (4) -> i+3
                # Win (5) -> i+4
                # Val (6) -> 0.91 (Is this delta or pick?)
                # Val (7) -> 16.36
                
                # If 16.36 is pickrate, then Yasuo has 7 values after Rank?
                # Let's assume the order is fixed but maybe lines are shifted?
                # Actually, checking Yasuo's pick rate. U.GG/Lolalytics says Yasuo pick rate is high. 16.36% makes sense. 0.91% is too low.
                # So for Yasuo, PickRate is at i+6 (relative to NameMatch being i=1).
                # i (Rank)
                # i+1 (Name 1) matches i+2 (Name 2) -> No, duplicate is Name1==Name2.
                # So if loop finds lines[k] == lines[k+1]:
                # k is Name1. 
                # k+1 is Name2.
                # k+2 is Tier.
                # k+3 is Lane.
                # k+4 is Win.
                # k+5 is Delta.
                # k+6 is PickRate.
                
                # Let's look at Yasuo again.
                # k=36 (Yasuo) == k+1=37 (Yasuo)
                # k+2 = S-
                # k+3 = bottom lane8.35
                # k+4 = 52.52
                # k+5 = 0.91
                # k+6 = 16.36
                
                # This matches perfectly with Miss Fortune!
                # MF:
                # k=2 (MF) == k+1=3 (MF)
                # k+2 = S+
                # k+3 = bottom lane..
                # k+4 = 52.23
                # k+5 = +0.50
                # k+6 = 17.69
                
                # So the structure relative to the DOUBLE NAME IS CONSISTENT.
                # The issue with 16 vs 17 lines was probably "Worldwide" stats or other tail data differing.
                # By anchoring on Name/Name/Tier, we are safe.
                
                try:
                    win_rate = lines[i+4]
                    pickrate_str = lines[i+6]
                    
                    # Store both lines[i+5] and lines[i+6] and try to determine which is pickrate?
                    # No, 17.69 and 16.36 seem to be the PickRates.
                    # PickRate is usually the larger number compared to delta (unless delta is huge, but delta is usually < 5).
                    # Actually, let's just use i+6.
                    
                    pickrate = float(pickrate_str.replace('+', '').replace('-', '').replace('%', ''))
                    
                    if pickrate < min_pick_rate:
                        i += 1
                        continue

                    champions.append({
                        'name': name.lower(),
                        'pick_rate': pickrate,
                        'win_rate': win_rate,
                        'tier': tier
                    })
                    
                    # Advance index to avoid re-matching or scanning inside this block
                    # A typical block is at least 10 lines.
                    i += 10
                    continue
                    
                except (ValueError, IndexError):
                    print(f"Error parsing entry for {name}")
            
            i += 1
            
    except FileNotFoundError:
        print(f"Warning: File not found: {filepath}")
        return []
    
    return champions

def collect_all_champions(min_pick_rate=0.5):
    """Collect champions from all lane files."""
    lane_champions = {}
    
    for lane in LANES:
        filename = f"champion_{lane}_data.txt"
        filepath = os.path.join(os.path.dirname(__file__), filename)
        
        print(f"Parsing {filename}...")
        champions = parse_champion_file(filepath, min_pick_rate)
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
    import argparse
    
    parser = argparse.ArgumentParser(description='Parse champion data from text files.')
    parser.add_argument('--min-pick-rate', type=float, default=0.5,
                        help='Minimum pick rate to include a champion (default: 0.5)')
    args = parser.parse_args()

    print("="*50)
    print(f"Parsing champion data from text files (Min Pick Rate: {args.min_pick_rate}%)")
    print("="*50)
    print()
    
    lane_champions = collect_all_champions(args.min_pick_rate)
    save_champion_list(lane_champions)
    
    print("\nDone!")
