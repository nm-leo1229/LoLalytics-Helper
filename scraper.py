import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import json
import os
import argparse
import urllib3


def load_champion_names():
    alias_file = os.path.join(os.path.dirname(__file__), "champion_aliases.json")
    try:
        with open(alias_file, "r", encoding="utf-8") as handle:
            alias_data = json.load(handle)
        names = list(alias_data.keys())
        if names:
            return names
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return [
        "jinx"
    ]


CHAMPION_NAMES = load_champion_names()

LANES = ['top', 'jungle', 'middle', 'bottom', 'support']

def normalize_champion_name(name):
    """Normalize champion name for URL generation."""
    # Special cases
    special_cases = {
        'nunu & willump': 'nunu',
        'renata glasc': 'renata',
    }
    
    name_lower = name.lower().strip()
    
    # Check special cases first
    if name_lower in special_cases:
        return special_cases[name_lower]
    
    # Remove special characters: apostrophes, periods, spaces
    normalized = name_lower.replace("'", "").replace(".", "").replace(" ", "")
    
    return normalized

def generate_url(name, lane):
    formatted_name = normalize_champion_name(name)
    return f"https://lolalytics.com/lol/{formatted_name}/build/?lane={lane}&tier=diamond_plus&patch=30"

def format_data(element):
    text = element.text.replace('\n', ' ').strip().split()
    img_elements = element.find_elements(By.TAG_NAME, 'img')
    img_alt = img_elements[0].get_attribute('alt') if img_elements else 'error'

    try:
        win_rate_value = float(text[0].replace('%', ''))
        win_rate_diff = round(win_rate_value - 50, 2)
    except (ValueError, IndexError):
        win_rate_diff = 'N/A'

    return {
        "Name": img_alt,
        "win_rate": text[0] if len(text) >= 1 else 'N/A',
        "popularity": text[3] if len(text) >= 5 else 'N/A',
        "games": text[4] if len(text) >= 5 else 'N/A',
        "win_rate_diff": win_rate_diff
    }

def format_synergy_data(element, debug=False):
    """Format synergy data with Win Rate, Delta 1, Delta 2, Pick Rate, Games"""
    img_alt = 'error'
    
    a_tags = element.find_elements(By.TAG_NAME, 'a')
    if not a_tags:
        return {
            "Name": 'error',
            "win_rate": 'N/A',
            "delta_1": 'N/A',
            "delta_2": 'N/A',
            "pick_rate": 'N/A',
            "games": 'N/A'
        }
    
    a_tag = a_tags[0]
    
    try:
        # Find the champion image
        # Structure: <a><q:template>...</q:template><span><img alt="Karma" src="...champx46/karma.webp"></span></a>
        # We want the image inside <span>, NOT inside <q:template> (tooltip)
        
        # First try: find img inside <span> tag (the actual champion image)
        span_imgs = a_tag.find_elements(By.XPATH, ".//span//img[contains(@src, 'champ')]")
        
        if span_imgs:
            # Use the first image from span (actual champion, not tooltip)
            champ_img = span_imgs[0]
        else:
            # Fallback: find any img with 'champ' in src, but exclude tooltip
            all_champ_imgs = a_tag.find_elements(By.XPATH, ".//img[contains(@src, 'champ')]")
            # Filter out tooltip images (inside q:template)
            champ_imgs = []
            for img in all_champ_imgs:
                # Check if image is NOT inside q:template
                try:
                    template = img.find_element(By.XPATH, "./ancestor::q:template")
                    # If we find template, skip this image
                    continue
                except:
                    # No template ancestor, this is the real image
                    champ_imgs.append(img)
            
            if not champ_imgs:
                return {
                    "Name": 'error',
                    "win_rate": 'N/A',
                    "delta_1": 'N/A',
                    "delta_2": 'N/A',
                    "pick_rate": 'N/A',
                    "games": 'N/A'
                }
            
            champ_img = champ_imgs[0]
        
        alt = champ_img.get_attribute('alt') or ''
        img_src = champ_img.get_attribute('src') or ''
        
        if 'champ' in img_src.lower() and alt:
            if alt not in ['Flash', 'Cleanse', 'Exhaust', 'Ignite', 'Teleport', 'Ghost', 'Barrier', 'Heal', 'Smite']:
                if 'lane' not in alt.lower():
                    img_alt = alt
        
    except Exception as e:
        return {
            "Name": 'error',
            "win_rate": 'N/A',
            "delta_1": 'N/A',
            "delta_2": 'N/A',
            "pick_rate": 'N/A',
            "games": 'N/A'
        }

    # Extract data from div elements
    # Structure: <div class="my-1">Win Rate</div>, <div class="my-1 text-[#bcc42a]">Delta 1</div>, etc.
    try:
        # Find all div elements with class "my-1" (Win Rate, Delta 1, Delta 2, Pick Rate)
        data_divs = element.find_elements(By.XPATH, ".//div[contains(@class, 'my-1')]")
        # Find games div (has text-[9px] class)
        games_divs = element.find_elements(By.XPATH, ".//div[contains(@class, 'text-[9px]')]")
        
        win_rate = 'N/A'
        delta_1 = 'N/A'
        delta_2 = 'N/A'
        pick_rate = 'N/A'
        games = 'N/A'
        
        # Win Rate is usually the first div with my-1 class (may have span inside)
        if len(data_divs) >= 1:
            win_rate_text = data_divs[0].text.strip()
            # If there's a span inside, get its text
            span = data_divs[0].find_elements(By.TAG_NAME, 'span')
            if span:
                win_rate_text = span[0].text.strip()
            win_rate = win_rate_text if win_rate_text else 'N/A'
        
        # Delta 1 is usually the second div with my-1 class and text-[#bcc42a]
        if len(data_divs) >= 2:
            delta_1 = data_divs[1].text.strip() if data_divs[1].text.strip() else 'N/A'
        
        # Delta 2 is usually the third div with my-1 class and text-[#f6ff36]
        if len(data_divs) >= 3:
            delta_2 = data_divs[2].text.strip() if data_divs[2].text.strip() else 'N/A'
        
        # Pick Rate is usually the fourth div with my-1 class and text-[#939bf6]
        if len(data_divs) >= 4:
            pick_rate = data_divs[3].text.strip() if data_divs[3].text.strip() else 'N/A'
        
        # Games is in a div with text-[9px] class
        if games_divs:
            games = games_divs[0].text.strip() if games_divs[0].text.strip() else 'N/A'
        
    except (ValueError, IndexError, Exception) as e:
        # Fallback: try to parse from text
        try:
            text = element.text.replace('\n', ' ').strip().split()
            win_rate = text[0] if len(text) >= 1 else 'N/A'
            delta_1 = text[1] if len(text) >= 2 else 'N/A'
            delta_2 = text[2] if len(text) >= 3 else 'N/A'
            pick_rate = text[3] if len(text) >= 4 else 'N/A'
            games = text[4] if len(text) >= 5 else 'N/A'
        except:
            win_rate = delta_1 = delta_2 = pick_rate = games = 'N/A'

    return {
        "Name": img_alt,
        "win_rate": win_rate,
        "delta_1": delta_1,
        "delta_2": delta_2,
        "pick_rate": pick_rate,
        "games": games
    }

def scrape_web(driver, url, current_lane):
    try:
        driver.get(url)
    except Exception as e:
        print(f"Error loading page {url}: {e}")
        return None

    # Scroll down the page to ensure content is loaded (1.5x more scroll)
    body = driver.find_element(By.CSS_SELECTOR, 'body')
    for _ in range(2):  # Increased from 1 to 2 (1.5x more scroll)
        body.send_keys(Keys.PAGE_DOWN)
        time.sleep(0.25)

    time.sleep(1)
    # Find the element containing "Pick Rate"
    pick_rate_value = None
    try:
        pick_rate_element = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Pick Rate')]/preceding-sibling::div[contains(@class, 'font-bold')]"))
        )
        pick_rate_text = pick_rate_element.text
        pick_rate_value = float(pick_rate_text.strip('%'))
        
    except Exception as e:
        # Resource not found
        print(f"Error finding pick rate")

    # If pick rate is not found or is low, skip
    if pick_rate_value is None or pick_rate_value < 0.5:
        print(f"Skip, {url}")
        return None

    # Scrape counter data
    lane_data = {lane: {} for lane in LANES}
    for i, lane in enumerate(LANES, start=2):
        xpath = f"/html/body/main/div[6]/div[1]/div[{i}]/div[2]"
        try:
            parent_element = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, xpath)))
        except Exception as e:
            error_msg = f"Could not find counter section for {lane}: {e}"
            print(f"Warning: {error_msg}")
            # Raise exception to trigger retry with browser restart
            raise Exception(error_msg)

        for _ in range(6):
            # Get all the children
            try:
                children = WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((By.XPATH, f"{xpath}/div[1]/*"))
                )
            except Exception as e:
                print(f"Warning: Could not find children elements for {lane}")
                break

            for element in children:
                data = format_data(element)
                name = data.get("Name")
                
                if name != 'error' and name != 'N/A' and name not in lane_data[lane]:
                    lane_data[lane][name] = data
        
            # Scroll the parent element sideways to load more elements
            driver.execute_script("arguments[0].scrollLeft += 500;", parent_element)
            time.sleep(0.5)


    # Scrape synergy data (Common Teammates)
    synergy_data = {lane: {} for lane in LANES}
    
    try:
        # Find and click the Common Teammates button
        teammates_button = None
        button_selectors = [
            "//div[@data-type='common_synergy']",
            "//div[contains(@class, 'cursor-pointer') and .//span[contains(text(), 'Common Teammates')]]",
        ]
        
        for selector in button_selectors:
            try:
                teammates_button = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                if teammates_button.is_displayed():
                    break
                else:
                    teammates_button = None
            except:
                continue
        
        if teammates_button:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", teammates_button)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", teammates_button)
                time.sleep(2)
                
                body.send_keys(Keys.PAGE_DOWN)
                time.sleep(0.5)
                
                # Collect synergy data for each lane (excluding current lane)
                lanes_to_check = [lane for lane in LANES if lane != current_lane]
                
                for lane in lanes_to_check:
                    current_lane_index = LANES.index(current_lane)
                    lane_index = LANES.index(lane)
                    
                    if lane_index < current_lane_index:
                        synergy_div_index = lane_index + 2
                    else:
                        synergy_div_index = lane_index + 1
                    
                    xpath = f"/html/body/main/div[6]/div[1]/div[{synergy_div_index}]/div[2]"
                    try:
                        parent_element = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, xpath)))
                    except Exception as e:
                        continue
                    
                    for _ in range(6):
                        try:
                            children = WebDriverWait(driver, 5).until(
                                EC.presence_of_all_elements_located((By.XPATH, f"{xpath}/div[1]/*"))
                            )
                        except Exception as e:
                            break
                        
                        for element in children:
                            data = format_synergy_data(element)
                            name = data.get("Name")
                            
                            if name != 'error' and name != 'N/A' and name not in synergy_data[lane]:
                                synergy_data[lane][name] = data
                        
                        driver.execute_script("arguments[0].scrollLeft += 500;", parent_element)
                        time.sleep(0.5)
                            
            except Exception as e:
                print(f"Error collecting synergy data: {e}")
    except Exception as e:
        print(f"Error finding synergy button: {e}")

    # Combine counter and synergy data
    result = {
        "counters": lane_data,
        "synergy": synergy_data
    }
    
    return result


def save_data(full_name, data, lane):
    """Save the champion's data to a file in the /data directory."""
    normalized_name = normalize_champion_name(full_name)
    filename = f"data/{normalized_name}_{lane}.json"

    try:
        with open(filename, 'w') as file:
            json.dump(data, file, indent=4)
        print(f"Champion data saved to {filename}")
    except IOError as e:
        print(f"Error saving data to file: {e}")

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
    # Prevent __del__ from calling quit again and causing OSError
    driver.quit = lambda: None

def validate_data(full_name, lane):
    """Check if data file exists and has valid content."""
    # Use normalized name for filename
    normalized_name = normalize_champion_name(full_name)
    filename = f"data/{normalized_name}_{lane}.json"
    
    if not os.path.exists(filename):
        return False
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Check if counter and synergy data exists and is not empty
        counters = data.get('counter') or data.get('counters')
        synergy = data.get('synergy')
        
        if not counters or not synergy:
            return False
        
        # Check that at least one lane has actual data (not empty dict)
        has_counter_data = any(counters.get(lane_name) for lane_name in counters)
        has_synergy_data = any(synergy.get(lane_name) for lane_name in synergy)
        
        if not has_counter_data or not has_synergy_data:
            return False
            
        return True
    except (json.JSONDecodeError, IOError):
        return False

def scrape_and_save(driver, full_name, lanes_to_scrape):
    """Scrape data once and save to all required lanes."""
    if not lanes_to_scrape:
        return False
    
    # Use the first lane to scrape (all data is the same regardless of which lane URL we visit)
    first_lane = lanes_to_scrape[0]
    url = generate_url(full_name, first_lane)

    data = scrape_web(driver, url, first_lane)
    
    # Save the same data to all required lanes
    if data:
        for lane in lanes_to_scrape:
            print(f"Saving data for {full_name} {lane} lane")
            save_data(full_name, data, lane)
        return True
    else:
        print(f"No data collected for {full_name}")
        return False
        

def scrape_and_save_subset(champion_lane_list):
    """Scrape data for champions in the list, optimizing for missing data."""
    
    # Group by champion to minimize browser restarts
    champion_lanes = {}
    for lane, champions in champion_lane_list.items():
        for champ in champions:
            name = champ['name']
            if name not in champion_lanes:
                champion_lanes[name] = []
            champion_lanes[name].append(lane)
    
    total_champs = len(champion_lanes)
    current_champ_idx = 0
    
    for champion_name, lanes in champion_lanes.items():
        current_champ_idx += 1
        
        # Filter lanes that need scraping
        lanes_to_scrape = []
        for lane in lanes:
            if not validate_data(champion_name, lane):
                lanes_to_scrape.append(lane)
            else:
                # print(f"Skipping {champion_name} {lane} - valid data exists")
                pass
        
        if not lanes_to_scrape:
            print(f"[{current_champ_idx}/{total_champs}] Skipping {champion_name} - all data valid")
            continue
            
        print(f"\n[{current_champ_idx}/{total_champs}] Processing {champion_name} for lanes: {', '.join(lanes_to_scrape)}")
        
        max_retries = 3
        retry_count = 0
        success = False
        
        while retry_count < max_retries and not success:
            if retry_count > 0:
                print(f"  Retrying {champion_name} (attempt {retry_count + 1}/{max_retries})")
            
            driver = None
            try:
                driver = create_driver()
                success = scrape_and_save(driver, champion_name, lanes_to_scrape)
                
                if not success:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"  Will retry {champion_name} with a fresh browser...")
                        
            except Exception as e:
                retry_count += 1
                print(f"  Error scraping {champion_name}: {e}")
                if retry_count < max_retries:
                    print(f"  Will retry {champion_name} with a fresh browser...")
            finally:
                if driver:
                    quit_driver(driver)

# If errors input your github token
# os.environ['GH_TOKEN'] = "_"

def main():
    if not os.path.exists('data'):
        os.makedirs('data')
    
    if os.environ.get("WDM_SSL_VERIFY") != "0":
        os.environ["WDM_SSL_VERIFY"] = "0"
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Load champion lane list
    try:
        with open('champion_lane_list.json', 'r', encoding='utf-8') as f:
            champion_lane_list = json.load(f)
    except FileNotFoundError:
        print("Error: champion_lane_list.json not found. Please run parse_champion_data.py first.")
        return

    print("Loaded champion list. Starting optimized scrape...")
    scrape_and_save_subset(champion_lane_list)

if __name__ == "__main__":
    main()
