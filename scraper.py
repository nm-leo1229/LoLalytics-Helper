from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
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

def generate_url(name, lane):
    formatted_name = name.lower()
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
    driver.get(url)

    # Scroll down the page slightly to ensure content is loaded
    body = driver.find_element(By.CSS_SELECTOR, 'body')
    for _ in range(3):
        body.send_keys(Keys.PAGE_DOWN)
        time.sleep(0.25)

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
        return

    # Scrape counter data
    lane_data = {lane: {} for lane in LANES}
    for i, lane in enumerate(LANES, start=2):
        xpath = f"/html/body/main/div[6]/div[1]/div[{i}]/div[2]"
        parent_element = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, xpath)))

        for _ in range(6):
            # Get all the children
            children = WebDriverWait(driver, 15).until(
                EC.presence_of_all_elements_located((By.XPATH, f"{xpath}/div[1]/*"))
            )

            for element in children:
                data = format_data(element)
                name = data.get("Name")
                
                if name != 'error' and name != 'N/A' and name not in lane_data[lane]:
                    lane_data[lane][name] = data
        
            # Scroll the parent element sideways to load more elements
            driver.execute_script("arguments[0].scrollLeft += 500;", parent_element)
            time.sleep(0.5)

    # Scrape synergy data (Common Teammates)
    # Synergy data structure: {lane: {champion_name: data}} (excluding current lane)
    synergy_data = {lane: {} for lane in LANES}
    
    try:
        # Find the button using data-type attribute (most reliable)
        # The button is a div with data-type="common_synergy"
        teammates_button = None
        button_selectors = [
            "//div[@data-type='common_synergy']",
            "//div[contains(@class, 'cursor-pointer') and .//span[contains(text(), 'Common Teammates')]]",
            "//div[contains(@class, 'cursor-pointer') and .//span[contains(text(), 'Common')]]",
            "//span[contains(text(), 'Common Teammates')]/ancestor::div[contains(@class, 'cursor-pointer')]",
            "//span[contains(text(), 'Common')]/ancestor::div[@data-type='common_synergy']"
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
        
        if teammates_button is None:
            print(f"Warning: Could not find 'Common Teammates' button for {current_lane}")
        else:
            try:
                # Scroll button into view
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", teammates_button)
                time.sleep(0.5)
                
                # Click the button using JavaScript (more reliable for Qwik framework)
                driver.execute_script("arguments[0].click();", teammates_button)
                time.sleep(2)  # Wait for content to load
                
                # Scroll to synergy section
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
                    parent_element = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, xpath)))
                    
                    for _ in range(6):
                        children = WebDriverWait(driver, 15).until(
                            EC.presence_of_all_elements_located((By.XPATH, f"{xpath}/div[1]/*"))
                        )
                        
                        for element in children:
                            data = format_synergy_data(element)
                            name = data.get("Name")
                            
                            if name != 'error' and name != 'N/A' and name not in synergy_data[lane]:
                                synergy_data[lane][name] = data
                        
                        driver.execute_script("arguments[0].scrollLeft += 500;", parent_element)
                        time.sleep(0.5)
                            
            except Exception as e:
                print(f"Error clicking 'Common Teammates' button or collecting synergy data: {e}")
            
    except Exception as e:
        print(f"Error scraping synergy data: {e}")

    # Combine counter and synergy data
    result = {
        "counters": lane_data,
        "synergy": synergy_data
    }
    
    return result


def save_data(full_name, data, lane):
    """Save the champion's data to a file in the /data directory."""
    filename = f"data/{full_name}_{lane}.json".replace(" ", "_")

    try:
        with open(filename, 'w') as file:
            json.dump(data, file, indent=4)
        print(f"Champion data saved to {filename}")
    except IOError as e:
        print(f"Error saving data to file: {e}")

def scrape_and_save(driver, full_name):
    for lane in LANES:
        url = generate_url(full_name, lane)

        filename = f"data/{full_name}_{lane}.json".replace(" ", "_")
        
        if os.path.exists(filename):
            print(f"Skip, Data for {full_name} {lane} already exists.")
            continue
        
        data = scrape_web(driver, url, lane)
        
        # if not empty save
        if data:
            print(f"Data extracted for {full_name} {lane} lane")
            save_data(full_name, data, lane)
        

def scrape_and_save_subset(driver, champion_names_subset):
    for champion_name in champion_names_subset:
        scrape_and_save(driver, champion_name)

def split_champion_names(fifth):
    total_names = len(CHAMPION_NAMES)
    part_size = total_names // 5

    start_index = fifth * part_size
    if fifth == 4:  # The last part gets any remainder names
        champion_names_subset = CHAMPION_NAMES[start_index:]
    else:
        champion_names_subset = CHAMPION_NAMES[start_index:start_index + part_size]

    return champion_names_subset


# If errors input your github token
# os.environ['GH_TOKEN'] = "_"

def main(fifth):
    if not os.path.exists('data'):
        os.makedirs('data')
    
    if os.environ.get("WDM_SSL_VERIFY") != "0":
        os.environ["WDM_SSL_VERIFY"] = "0"
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))

    try:
        if fifth == 0:
            scrape_and_save_subset(driver, CHAMPION_NAMES)
        else:
            champion_names_subset = split_champion_names(fifth-1)
            scrape_and_save_subset(driver, champion_names_subset)
    finally:
        driver.quit()

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Run scraping for a specific subset of champions.")
    parser.add_argument('fifth', type=int, choices=range(6), help="Specify which 1/5th of the list to process (0 for all, 1-5 for subsets).")
    args = parser.parse_args()
    main(args.fifth)
