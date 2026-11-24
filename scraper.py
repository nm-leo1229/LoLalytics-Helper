import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, WebDriverException
import time
import json
import os
import urllib3
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from bottom_blind import STYLE_LANES, common_opponent_weights, snapshot_path, valid_profile


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

MIN_PICK_RATE = 0.5  # 픽률(%)이 이보다 낮은 챔피언은 수집하지 않는다

# 티어 목록의 모든 행을 [챔피언 링크, 픽률] 로 돌려준다. 아직 그려지지 않은 빈 행이 있으면 null.
# 빈 행은 스크롤로 화면에 들어오는 순간에만 채워지므로, 호출마다 맨 위와 빈 행을 번갈아 오간다.
TIER_ROWS_JS = """
const link = document.querySelector("main a[href*='/build/']");
if (!link) return null;
const rows = [...link.parentElement.parentElement.parentElement.children];
const empty = rows.find(row => !row.children.length);
if (empty) {
    if (arguments[0]) window.scrollTo(0, 0); else empty.scrollIntoView();
    return null;
}
return rows.flatMap(row => {
    const champion = row.querySelector("a[href*='/build/']");
    return champion ? [[champion.getAttribute('href'), row.children[6].textContent.trim()]] : [];
});
"""

def filter_by_pick_rate(rows):
    """티어 목록 행 [[챔피언 링크, 픽률], ...] 에서 수집할 챔피언의 URL 이름만 남긴다."""
    return [href.split('/build/')[0].rsplit('/', 1)[-1]
            for href, pick_rate in rows if float(pick_rate) >= MIN_PICK_RATE]

def fetch_lane_champions(driver, lane):
    """LoLalytics 티어 목록에서 해당 레인의 수집 대상 챔피언을 읽어 온다."""
    driver.get(f"https://lolalytics.com/lol/tierlist/?lane={lane}&tier=master_plus&patch=30")
    deadline = time.time() + 120
    scroll_to_top = False
    while time.time() < deadline:
        rows = driver.execute_script(TIER_ROWS_JS, scroll_to_top)
        if rows is not None:
            return filter_by_pick_rate(rows)
        scroll_to_top = not scroll_to_top
        time.sleep(0.2)
    raise TimeoutException(f"Tier list for {lane} did not finish loading")

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
    return f"https://lolalytics.com/lol/{formatted_name}/build/?lane={lane}&tier=master_plus&patch=30"


def extract_lane_profile(state, champion, lane):
    """같은 빌드 페이지에서 종료 구간별 [게임 수, 승리 수]와 맞라인 상성을 읽는다."""
    try:
        objects = json.loads(state)["objs"]
        records = [item for item in objects if isinstance(item, dict)]

        def resolve(ref):
            return objects[int(ref, 36)]

        filters = {"champion": champion, "lane": lane, "tier": "master_plus",
                   "region": "all", "mode": "ranked", "patch": "30"}
        if not any(all(key in row and resolve(row[key]) == value for key, value in filters.items())
                   for row in records):
            raise ValueError("unexpected champion or queue filters")
        chart = next(row for row in records if "time" in row and "timeWin" in row)
        games = resolve(chart["time"])
        wins = resolve(chart["timeWin"])
        bins = [[resolve(games[str(i)]), resolve(wins[str(i)])] for i in range(1, 8)]

        paths = resolve(next(row["champPath"] for row in records if "champPath" in row and "champId" in row))
        rows = next(resolve(row[lane]) for row in records
                    if row.keys() == set(LANES) and isinstance(resolve(row[lane]), list))
        matchups = {}
        for ref in rows:
            champ_id, win_rate, _, _, popularity, count = map(resolve, resolve(ref))
            opponent = resolve(paths[str(champ_id)])
            matchups[opponent] = {"win_rate": win_rate, "popularity": popularity, "games": count}
        profile = {"time": bins, "matchups": matchups}
        if not valid_profile(profile):
            raise ValueError("invalid game counts or matchups")
        return profile
    except (KeyError, IndexError, TypeError, ValueError, StopIteration) as exc:
        raise ValueError(f"Invalid {lane} profile for {champion}: {exc}") from exc


def collect_lane_snapshot(lane, champions, read_state, data_dir):
    """모든 대상 수집이 끝난 뒤에만 이전 선픽 표본을 한 번에 교체한다."""
    path = snapshot_path(data_dir, lane)
    profiles = {name: extract_lane_profile(read_state(name), name, lane) for name in sorted(set(champions))}
    if not profiles:
        raise ValueError(f"Empty {lane} tier list")
    # 후보와 자주 만나는 상대의 양방향 행을 보존한다.
    opponents = profiles.keys() | common_opponent_weights(profiles).keys()
    for name, profile in profiles.items():
        profile["matchups"] = {enemy: row for enemy, row in profile["matchups"].items() if enemy in opponents}
        if not profile["matchups"]:
            raise ValueError(f"No {lane} opponents in the collected pool for {name}")
    snapshot = {"collected_on": datetime.now(timezone.utc).date().isoformat(), "profiles": profiles}
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = NamedTemporaryFile(dir=path.parent, delete=False, mode="w", encoding="utf-8")
    temporary_path = Path(handle.name)
    try:
        with handle:
            json.dump(snapshot, handle, indent=2, allow_nan=False)
            handle.write("\n")
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def read_lane_state(driver, champion, lane):
    driver.get(generate_url(champion, lane))
    return WebDriverWait(driver, 15).until(lambda browser: browser.execute_script(
        """return document.querySelector('script[type="qwik/json"]')?.textContent"""))


def extract_bottom_profile(state, champion):
    return extract_lane_profile(state, champion, "bottom")


def collect_bottom_snapshot(champions, read_state, data_dir):
    return collect_lane_snapshot("bottom", champions, read_state, data_dir)


def read_bottom_state(driver, champion):
    return read_lane_state(driver, champion, "bottom")


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
    """Format synergy data with Win Rate, Delta 1, Delta 2, Pick Rate, Games (경량화)"""
    img_alt = 'error'

    # 이미지 1회 조회: champ src를 가진 첫 이미지
    try:
        champ_imgs = element.find_elements(By.CSS_SELECTOR, "img[src*='champ']")
        for img in champ_imgs:
            alt = (img.get_attribute('alt') or '').strip()
            if not alt:
                continue
            lower_alt = alt.lower()
            if lower_alt in ['flash', 'cleanse', 'exhaust', 'ignite', 'teleport', 'ghost', 'barrier', 'heal', 'smite']:
                continue
            if 'lane' in lower_alt:
                continue
            img_alt = alt
            break
    except Exception:
        pass

    if img_alt == 'error':
        if debug:
            print("[synergy-parse] img missing")
        return {
            "Name": 'error',
            "win_rate": 'N/A',
            "delta_1": 'N/A',
            "delta_2": 'N/A',
            "pick_rate": 'N/A',
            "games": 'N/A'
        }

    # 텍스트를 단순 split (format_data와 동일한 방식)
    try:
        parts = element.text.replace('\n', ' ').strip().split()
    except Exception:
        parts = []

    def pick(idx):
        return parts[idx] if len(parts) > idx and parts[idx] else 'N/A'

    win_rate = pick(0)
    delta_1 = pick(1)
    delta_2 = pick(2)
    pick_rate = pick(3)
    games = pick(4)

    if debug:
        print(f"[synergy-parse] alt={img_alt}, parts_len={len(parts)}")

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
    if pick_rate_value is None or pick_rate_value < MIN_PICK_RATE:
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

    # 4번 반복하면서 모든 레인 동시 처리
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

def chrome_major_version():
    override = os.environ.get("SCRAPER_CHROME_VERSION_MAIN", "").strip()
    if override.isdigit():
        return int(override)
    if os.name == "nt":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon") as key:
                version, _ = winreg.QueryValueEx(key, "version")
            return int(version.split(".")[0])
        except (OSError, ValueError):
            pass
    return None  # 설치 정보를 읽을 수 없으면 드라이버의 기본 버전 선택을 사용한다.


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

    driver = uc.Chrome(options=options, version_main=chrome_major_version())
    # 창이 다른 창에 가려져도 페이지가 계속 그려지게 한다 (안 하면 스크롤로 채워지는 목록이 멈추거나 일부만 수집된다)
    driver.execute_cdp_cmd("Emulation.setFocusEmulationEnabled", {"enabled": True})
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
        for name in champions:
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

    print("Fetching champion list from the tier list...")
    driver = create_driver()
    try:
        champion_lane_list = {lane: fetch_lane_champions(driver, lane) for lane in LANES}
        for lane in STYLE_LANES:
            try:
                collect_lane_snapshot(lane, champion_lane_list[lane], lambda name: read_lane_state(driver, name, lane),
                                      Path("data"))
            # 드라이버가 죽으면 selenium 이 urllib3 오류를 그대로 올린다: 이것도 잡아야 아래 챔피언별 수집으로 넘어간다
            except (ValueError, OSError, WebDriverException, urllib3.exceptions.HTTPError) as exc:
                print(f"{lane} blind-pick data could not be refreshed: {exc}")
    finally:
        quit_driver(driver)
    print({lane: len(names) for lane, names in champion_lane_list.items()})

    print("Starting optimized scrape...")
    scrape_and_save_subset(champion_lane_list)

if __name__ == "__main__":
    main()
