import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import json
import os

LANES = ['top', 'jungle', 'middle', 'bottom', 'support']

def create_driver():
    """Create and configure a new Chrome driver instance."""
    options = uc.ChromeOptions()
    options.page_load_strategy = 'eager'
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = uc.Chrome(options=options)
    driver.set_page_load_timeout(60)
    driver.set_script_timeout(60)
    return driver

def quit_driver(driver):
    """Safely quit the driver."""
    try:
        driver.quit()
    except OSError:
        pass
    driver.quit = lambda: None

def scrape_tierlist(driver, lane):
    """Scrape champion pick rates from the tierlist page for a specific lane."""
    url = f"https://lolalytics.com/lol/tierlist/?lane={lane}&tier=diamond_plus&patch=30"
    
    print(f"\\nScraping {lane} tierlist from {url}")
    
    try:
        driver.get(url)
    except Exception as e:
        print(f"Error loading tierlist page for {lane}: {e}")
        return []
    
    # Wait for page to load and scroll down to ensure content is loaded
    time.sleep(3)
    body = driver.find_element(By.CSS_SELECTOR, 'body')
    body.send_keys(Keys.PAGE_DOWN)
    time.sleep(1)
    
    champions = []
    
    try:
        # Find all champion images (they contain the champion name in alt attribute)
        champ_images = driver.find_elements(By.XPATH, "//img[contains(@src, 'champ')]")
        
        print(f"Found {len(champ_images)} champion images")
        
        for img in champ_images:
            try:
                champ_name = img.get_attribute('alt')
                if not champ_name or champ_name.lower() in ['flash', 'ignite', 'teleport', 'smite', 'exhaust', 'cleanse', 'barrier', 'heal', 'ghost']:
                    continue
                
                # Try to find the row containing this champion
                # Navigate up to find the parent row (tr or div)
                parent = img
                for _ in range(10):  # Go up max 10 levels
                    parent = parent.find_element(By.XPATH, "..")
                    tag_name = parent.tag_name.lower()
                    if tag_name in ['tr', 'div'] and 'row' in parent.get_attribute('class').lower():
                        break
                
                # Look for pick rate in this row
                # Pick rate is usually a percentage value
                text_content = parent.text
                
                # Try to find percentage values
                import re
                percentages = re.findall(r'(\d+\.?\d*)%', text_content)
                
                pick_rate = None
                for pct_str in percentages:
                    try:
                        pct_value = float(pct_str)
                        # Pick rate is usually between 0.1% and 50%
                        # Exclude win rates (usually around 45-55%)
                        if 0.1 <= pct_value <= 30:  # Pick rates are usually lower than 30%
                            pick_rate = pct_value
                            break
                    except ValueError:
                        continue
                
                if pick_rate and pick_rate >= 1.0:
                    champions.append({
                        'name': champ_name.lower(),
                        'pick_rate': pick_rate
                    })
                    print(f"  ✓ {champ_name}: {pick_rate}%")
                    
            except Exception as e:
                # Skip this champion if there's an error
                continue
        
    except Exception as e:
        print(f"Error scraping tierlist for {lane}: {e}")
    
    return champions

def collect_all_champions():
    """Collect champions with pick rate >= 1% for all lanes."""
    driver = None
    lane_champions = {}
    
    try:
        driver = create_driver()
        
        for lane in LANES:
            champions = scrape_tierlist(driver, lane)
            lane_champions[lane] = champions
            print(f"\\n→ Found {len(champions)} champions for {lane} lane")
            time.sleep(2)  # Be nice to the server
        
    finally:
        if driver:
            quit_driver(driver)
    
    return lane_champions

def save_champion_list(lane_champions):
    """Save the collected champion list to a JSON file."""
    output_file = "champion_lane_list.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(lane_champions, f, indent=2, ensure_ascii=False)
    
    print(f"\\n{'='*50}")
    print(f"Saved champion list to {output_file}")
    
    # Print summary
    total = sum(len(champs) for champs in lane_champions.values())
    print(f"\\nSummary:")
    for lane, champs in lane_champions.items():
        print(f"  {lane}: {len(champs)} champions")
    print(f"  Total: {total} champion-lane combinations")
    print(f"{'='*50}")

if __name__ == "__main__":
    print("="*50)
    print("Collecting champions with pick rate >= 1%")
    print("="*50)
    lane_champions = collect_all_champions()
    save_champion_list(lane_champions)
    print("\\nDone!")
