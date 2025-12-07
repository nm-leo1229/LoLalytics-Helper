import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, WebDriverException
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
    return f"https://lolalytics.com/lol/{formatted_name}/build/?lane={lane}&patch=30"

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
    
    # Random delay to mimic human behavior
    import random

    # Scroll down the page to ensure content is loaded (1.5x more scroll)
    body = driver.find_element(By.CSS_SELECTOR, 'body')
    for _ in range(2):  # Increased from 1 to 2 (1.5x more scroll)
        body.send_keys(Keys.PAGE_DOWN)
        time.sleep(random.uniform(0.2, 0.3))

    time.sleep(random.uniform(0.5, 0.6))
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

    # Scrape counter data - 모든 레인 동시 스크롤
    lane_data = {lane: {} for lane in LANES}
    
    # 모든 레인의 parent_element를 먼저 수집
    parent_elements = {}
    xpaths = {}
    for i, lane in enumerate(LANES, start=2):
        xpath = f"/html/body/main/div[6]/div[1]/div[{i}]/div[2]"
        xpaths[lane] = xpath
        try:
            parent_elements[lane] = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, xpath)))
        except (TimeoutException, WebDriverException) as e:
            error_msg = f"Could not find counter section for {lane}: {e}"
            print(f"Warning: {error_msg}")
            raise Exception(error_msg)

    # 6번 반복하면서 모든 레인 동시 처리
    for _ in range(4):
        # 모든 레인에서 데이터 수집
        for lane in LANES:
            try:
                children = driver.find_elements(By.XPATH, f"{xpaths[lane]}/div[1]/*")
                for element in children:
                    try:
                        data = format_data(element)
                        name = data.get("Name")
                        if name != 'error' and name != 'N/A' and name not in lane_data[lane]:
                            lane_data[lane][name] = data
                    except (TimeoutException, WebDriverException):
                        continue
            except (TimeoutException, WebDriverException):
                continue
        
        # 추가 챔피언 정보를 보기 위해 좌로 스크롤
        try:
            scroll_script = "for(let i=0; i<arguments.length; i++) { if(arguments[i]) arguments[i].scrollLeft += 500; }"
            driver.execute_script(scroll_script, *parent_elements.values())
            time.sleep(0.05)
        except (TimeoutException, WebDriverException):
            break


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
                time.sleep(random.uniform(0.2, 0.3))
                driver.execute_script("arguments[0].click();", teammates_button)
                time.sleep(random.uniform(1.0, 1.1))
                
                body.send_keys(Keys.PAGE_DOWN)
                time.sleep(random.uniform(1.0, 1.1))
                
                # Collect synergy data for each lane (excluding current lane) - 동시 스크롤
                lanes_to_check = [lane for lane in LANES if lane != current_lane]
                current_lane_index = LANES.index(current_lane)
                
                # 모든 레인의 parent_element를 먼저 수집
                synergy_parents = {}
                synergy_xpaths = {}
                for lane in lanes_to_check:
                    lane_index = LANES.index(lane)
                    if lane_index < current_lane_index:
                        synergy_div_index = lane_index + 2
                    else:
                        synergy_div_index = lane_index + 1
                    
                    xpath = f"/html/body/main/div[6]/div[1]/div[{synergy_div_index}]/div[2]"
                    synergy_xpaths[lane] = xpath
                    try:
                        synergy_parents[lane] = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, xpath)))
                    except (TimeoutException, WebDriverException):
                        continue
                
                # 4번 반복하면서 모든 레인 동시 처리 (대부분 3-4번이면 충분)
                for _ in range(4):
                    # 모든 레인에서 데이터 수집
                    for lane in lanes_to_check:
                        if lane not in synergy_xpaths:
                            continue
                        try:
                            children = driver.find_elements(By.XPATH, f"{synergy_xpaths[lane]}/div[1]/*")
                            for element in children:
                                try:
                                    data = format_synergy_data(element)
                                    name = data.get("Name")
                                    if name != 'error' and name != 'N/A' and name not in synergy_data[lane]:
                                        synergy_data[lane][name] = data
                                except (TimeoutException, WebDriverException):
                                    continue
                        except (TimeoutException, WebDriverException):
                            continue
                    
                    # 추가 챔피언 정보를 보기 위해 좌로 스크롤
                    if synergy_parents:
                        try:
                            scroll_script = "for(let i=0; i<arguments.length; i++) { if(arguments[i]) arguments[i].scrollLeft += 500; }"
                            driver.execute_script(scroll_script, *synergy_parents.values())
                            time.sleep(0.05)
                        except (TimeoutException, WebDriverException):
                            break
                            
            except (TimeoutException, WebDriverException) as e:
                print(f"Warning: Synergy data collection interrupted: {e}")
                raise Exception(f"Synergy data collection timeout: {e}")
    except Exception as e:
        print(f"Error finding synergy button: {e}")
        # synergy 수집 실패 시 재시도를 위해 예외 발생
        raise Exception(f"Synergy data collection failed: {e}")

    # synergy 데이터가 비어있으면 재시도
    has_synergy_data = any(synergy_data.get(lane) for lane in synergy_data)
    if not has_synergy_data:
        raise Exception("Synergy data is empty, need retry")

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
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-background-networking')
    options.add_argument('--disable-default-apps')
    options.add_argument('--no-first-run')
    
    # 불필요한 리소스 비활성화
    prefs = {
        "profile.managed_default_content_settings.images": 2,  # 이미지 차단
        "profile.managed_default_content_settings.media_stream": 2,
        "profile.managed_default_content_settings.notifications": 2,
        "profile.managed_default_content_settings.plugins": 2,  # 플러그인 차단
        "profile.managed_default_content_settings.popups": 2,  # 팝업 차단
        "profile.managed_default_content_settings.automatic_downloads": 2,
        "profile.default_content_setting_values.media_stream_mic": 2,
        "profile.default_content_setting_values.media_stream_camera": 2,
    }
    options.add_experimental_option("prefs", prefs)
    
    # 자동재생 비활성화
    options.add_argument('--autoplay-policy=user-gesture-required')
    
    driver = uc.Chrome(options=options, version_main=142)
    driver.set_page_load_timeout(60)
    driver.set_script_timeout(30)  # execute_script 타임아웃 단축
    driver.implicitly_wait(10)
    
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
    """Scrape data for each lane separately and save to corresponding files."""
    if not lanes_to_scrape:
        return False
    
    all_success = True
    
    # IMPORTANT: Each lane needs its own unique data from its specific URL!
    # Different lanes have different counter/synergy data
    for lane in lanes_to_scrape:
        url = generate_url(full_name, lane)
        print(f"Fetching data for {full_name} {lane} lane from {url}")
        
        data = scrape_web(driver, url, lane)
        
        if data:
            print(f"Saving data for {full_name} {lane} lane")
            save_data(full_name, data, lane)
        else:
            print(f"No data collected for {full_name} {lane}")
            all_success = False
    
    return all_success
        

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
    
    # 브라우저 재사용 - 한 번만 생성
    driver = None
    champs_since_restart = 0
    RESTART_INTERVAL = 90 # 브라우저 재시작 (메모리 관리)
    
    try:
        for champion_name, lanes in champion_lanes.items():
            current_champ_idx += 1
            
            # Filter lanes that need scraping
            lanes_to_scrape = []
            for lane in lanes:
                if not validate_data(champion_name, lane):
                    lanes_to_scrape.append(lane)
            
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
                
                try:
                    # 브라우저가 없거나 재시작 필요 시 생성
                    if driver is None or champs_since_restart >= RESTART_INTERVAL:
                        if driver is not None:
                            print("  Restarting browser for memory management...")
                            quit_driver(driver)
                        driver = create_driver()
                        champs_since_restart = 0
                    
                    success = scrape_and_save(driver, champion_name, lanes_to_scrape)
                    
                    if success:
                        champs_since_restart += 1
                    else:
                        retry_count += 1
                        if retry_count < max_retries:
                            print(f"  Will retry {champion_name} with a fresh browser...")
                            quit_driver(driver)
                            driver = None
                            
                except Exception as e:
                    retry_count += 1
                    print(f"  Error scraping {champion_name}: {e}")
                    if retry_count < max_retries:
                        print(f"  Will retry {champion_name} with a fresh browser...")
                    # 에러 시 브라우저 재시작
                    if driver:
                        quit_driver(driver)
                        driver = None
    finally:
        # 모든 작업 완료 후 브라우저 종료
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
