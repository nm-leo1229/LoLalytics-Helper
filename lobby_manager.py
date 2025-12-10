import tkinter as tk
from tkinter import messagebox, ttk
import json
import os
import re
import sys
import subprocess
import copy
import logging
from pathlib import Path
from collections import defaultdict
from op_duos_tab import OpDuosTab
from ignore_tab import IgnoreTab
from counter_synergy_tab import CounterSynergyTab
from credits_tab import CreditsTab
from weight_settings_tab import WeightSettingsTab, load_weight_settings
from common import (
    resolve_resource_path,
    AutocompletePopup,
    ScoreTooltip,
    LANES,
    COUNTER_LOW_GAMES_DEFAULT,
    SYNERGY_LOW_GAMES_DEFAULT,
    LOW_SAMPLE_COLOR,
    NORMAL_SAMPLE_COLOR,
    WARNING_ICON
)

try:
    import requests
    import urllib3
    import threading
    import time
except ImportError:  # requests는 선택적 의존성
    requests = None
    urllib3 = None
    threading = None
    time = None

ALIAS_FILE = resolve_resource_path("champion_aliases.json")
IGNORED_CHAMPIONS_FILE = resolve_resource_path("ignored_champions.json")
UI_SETTINGS_FILE = resolve_resource_path("ui_settings.json")
WEIGHT_SETTINGS_FILE = resolve_resource_path("weight_settings.json")
DATA_DIR = Path(resolve_resource_path("data"))
LOG_DIR = Path(resolve_resource_path("logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
LCU_LOG_FILE = LOG_DIR / "lcu_responses.log"
APP_ROOT = Path(__file__).resolve().parent

LCU_LOGGER = logging.getLogger("lcu_trace")
if not LCU_LOGGER.handlers:
    LCU_LOGGER.setLevel(logging.DEBUG)
    _file_handler = logging.FileHandler(LCU_LOG_FILE, encoding="utf-8")
    _file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    LCU_LOGGER.addHandler(_file_handler)
    LCU_LOGGER.propagate = False

RECOMMEND_LOW_SAMPLE_TAG = "데이터 부족"
RECOMMEND_HIGH_SAMPLE_TAG = "신뢰도 높음"
RECOMMEND_FULL_COUNTER_TAG = "올카운터"
RECOMMEND_OP_SYNERGY_TAG = "OP 시너지"
RECOMMEND_PRE_PICK_TAG = "선픽 카드"

def load_app_version() -> str:
    """VERSION 파일을 읽어 앱 버전을 반환합니다."""
    candidates = [
        APP_ROOT / "VERSION",
        Path(resolve_resource_path("VERSION")),
    ]
    for candidate in candidates:
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                version = f.read().strip()
                if version:
                    return version
        except OSError:
            continue
    return "v0.0.0"

APP_VERSION = load_app_version()

# 테마 정의
THEME_LIGHT = {
    "name": "light",
    "bg_color": "#FDF6E3",       # Creamy White
    "fg_color": "#2D2D2D",       # Dark Gray (가독성 향상)
    "accent_color": "#D7CCC8",   # Light Brown
    "select_color": "#FFECB3",   # Honey
    "button_color": "#5D4037",   # Medium Brown
    "button_fg": "#FFFFFF",      # White
    "button_active_bg": "#8D6E63",
    "button_pressed_bg": "#4E342E",
    "entry_bg": "#FFFFFF",
    "entry_fg": "#2D2D2D",       # Dark Gray
    "treeview_bg": "#FFFFFF",
    "treeview_heading_bg": "#D7CCC8",
    "low_sample": "#444444",
    "normal_sample": "#2D2D2D",  # Dark Gray
    "tooltip_bg": "#FFFDE7",
    "tooltip_fg": "#2D2D2D",     # Dark Gray
    "score_default": "#1976D2",  # Blue (Darker for readability)
    "score_high": "#2E7D32",     # Green
    "score_medium": "#F57F17",   # Orange
    "score_low": "#C62828",      # Red
}

THEME_DARK = {
    "name": "dark",
    "bg_color": "#1E1E2E",       # Dark background (Catppuccin Base)
    "fg_color": "#CDD6F4",       # Light text (Catppuccin Text)
    "accent_color": "#313244",   # Dark accent (Catppuccin Surface0)
    "select_color": "#45475A",   # Selection (Catppuccin Surface1)
    "button_color": "#89B4FA",   # Blue button (Catppuccin Blue)
    "button_fg": "#1E1E2E",      # Dark button text
    "button_active_bg": "#74C7EC",  # Catppuccin Sapphire
    "button_pressed_bg": "#89DCEB",  # Catppuccin Sky
    "entry_bg": "#313244",       # Entry background
    "entry_fg": "#CDD6F4",       # Entry text
    "treeview_bg": "#1E1E2E",    # Treeview background
    "treeview_heading_bg": "#313244",
    "low_sample": "#6C7086",     # Catppuccin Overlay0
    "normal_sample": "#CDD6F4",  # Catppuccin Text
    "tooltip_bg": "#313244",
    "tooltip_fg": "#CDD6F4",
    "score_default": "#89B4FA",  # Catppuccin Blue
    "score_high": "#A6E3A1",     # Catppuccin Green
    "score_medium": "#F9E2AF",   # Catppuccin Yellow
    "score_low": "#F38BA8",      # Catppuccin Red
}

BANPICK_DEFAULT_LANES = ['jungle', 'bottom', 'support', 'middle', 'top']
BANPICK_MIN_GAMES_DEFAULT = 900
BANPICK_PICK_RATE_OVERRIDE = 1.5
BANPICK_HIGH_SAMPLE_THRESHOLD = 10000
BANPICK_PRE_PICK_POPULARITY_THRESHOLD = 1.5
SYNERGY_OP_THRESHOLD = 55.0
CHOSEONG_LIST = [
    "ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ",
    "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"
]


def extract_choseong(text: str) -> str:
    choseong = []
    for char in text:
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3:
            index = (code - 0xAC00) // 588
            choseong.append(CHOSEONG_LIST[index])
        elif char.isalpha() or char.isdigit():
            choseong.append(char.lower())
    return "".join(choseong)


def alias_variants(alias: str, include_initials: bool = True) -> set[str]:
    variants = set()
    candidate = alias.strip()   
    if not candidate:
        return variants

    lower_candidate = candidate.lower()
    variants.add(lower_candidate)

    alnum_only = re.sub(r"[^0-9a-z가-힣]", "", lower_candidate)
    if alnum_only:
        variants.add(alnum_only)

    hangul_prefix_match = re.match(r"^[가-힣]+", candidate)
    if hangul_prefix_match:
        hangul_prefix = hangul_prefix_match.group(0)
        variants.add(hangul_prefix.lower())

    initials = extract_choseong(candidate)
    if include_initials and initials:
        variants.add(initials.lower())

    return variants


def contains_hangul_syllable(text: str) -> bool:
    return any(0xAC00 <= ord(ch) <= 0xD7A3 for ch in text)


def log_lcu_response(method: str, path: str, response, source: str = "watcher"):
    status = getattr(response, "status_code", "unknown")
    try:
        headers = dict(getattr(response, "headers", {}))
    except Exception:
        headers = {}
    try:
        body = response.text
    except Exception as exc:  # pragma: no cover - defensive logging
        body = f"<body 읽기 실패: {exc}>"
    LCU_LOGGER.info(
        "[source=%s] %s %s status=%s headers=%s body=%s",
        source,
        method,
        path,
        status,
        headers,
        body,
    )


def log_lcu_error(method: str, path: str, error: Exception, source: str = "watcher"):
    LCU_LOGGER.error(
        "[source=%s] %s %s error=%s", source, method, path, error, exc_info=True
    )


def reset_lcu_log():
    """LCU 로그 파일을 초기화합니다. 새 게임 시작 시 호출됩니다."""
    try:
        # 기존 핸들러 제거
        for handler in LCU_LOGGER.handlers[:]:
            handler.close()
            LCU_LOGGER.removeHandler(handler)
        
        # 파일을 덮어쓰기 모드로 다시 열기 (기존 내용 삭제)
        _file_handler = logging.FileHandler(LCU_LOG_FILE, mode='w', encoding="utf-8")
        _file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        LCU_LOGGER.addHandler(_file_handler)
        LCU_LOGGER.info("=== 새 게임 시작: 로그 초기화 ===")
    except Exception as exc:
        # 로그 초기화 실패해도 프로그램은 계속 실행
        print(f"[WARN] LCU 로그 초기화 실패: {exc}")


def load_alias_tables():
    if not os.path.exists(ALIAS_FILE):
        print(f"[WARN] Alias file not found at {ALIAS_FILE}")
    try:
        with open(ALIAS_FILE, "r", encoding="utf-8") as handle:
            alias_data = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        alias_data = {}

    canonical_lookup = {}
    alias_lookup = {}
    display_lookup = {}
    autocomplete_values = set()

    for canonical_name, aliases in alias_data.items():
        normalized = canonical_name.lower()
        canonical_lookup[normalized] = canonical_name

        canonical_title = canonical_name.title()
        autocomplete_values.add(canonical_title)

        display_value = canonical_name.title()
        if isinstance(aliases, list) and aliases:
            display_value = next((alias for alias in aliases if alias and alias[0].isascii()), display_value)
            for alias in aliases:
                if alias:
                    autocomplete_values.add(alias.strip())
                for variant in alias_variants(alias):
                    alias_lookup.setdefault(variant, canonical_name)

        for variant in alias_variants(canonical_name):
            alias_lookup.setdefault(variant, canonical_name)
        alias_lookup.setdefault(normalized, canonical_name)
        display_lookup[canonical_name] = display_value

    autocomplete_list = sorted(value for value in autocomplete_values if value)
    return canonical_lookup, alias_lookup, display_lookup, autocomplete_list


def load_ignored_champion_names() -> list[str]:
    try:
        with open(IGNORED_CHAMPIONS_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    if isinstance(data, list):
        return [name for name in data if isinstance(name, str)]
    return []


def save_ignored_champion_names(names: list[str]) -> None:
    try:
        with open(IGNORED_CHAMPIONS_FILE, "w", encoding="utf-8") as handle:
            json.dump(sorted(names), handle, ensure_ascii=False, indent=2)
    except OSError as error:
        print(f"[WARN] Failed to persist ignored champions: {error}")


LOCKFILE_ENV = "LOL_LOCKFILE"


def find_lockfile_from_process() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        # wmic를 사용하여 실행 중인 LeagueClientUx.exe 경로 탐색
        cmd = 'wmic process where "name=\'LeagueClientUx.exe\'" get ExecutablePath'
        # 윈도우 창 팝업 방지
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        output = subprocess.check_output(
            cmd,
            shell=True,
            startupinfo=startupinfo,
            stderr=subprocess.DEVNULL
        ).decode("utf-8", errors="ignore")
        
        for line in output.splitlines():
            line = line.strip()
            if line.lower().endswith("leagueclientux.exe"):
                install_dir = os.path.dirname(line)
                candidate = os.path.join(install_dir, "lockfile")
                if os.path.exists(candidate):
                    return candidate
    except Exception:
        return None
    return None


def build_lockfile_candidates() -> list[str]:
    candidates = []
    
    # 1순위: 환경변수
    env_path = os.environ.get(LOCKFILE_ENV)
    if env_path:
        candidates.append(env_path)

    # 2순위: 실행 중인 프로세스 기반 (가장 정확함)
    process_path = find_lockfile_from_process()
    if process_path:
        candidates.append(process_path)

    # 3순위: 윈도우 기본 설치 경로
    windows_defaults = [
        Path("C:/Riot Games/League of Legends/lockfile"),
        Path("C:/Program Files/Riot Games/League of Legends/lockfile"),
        Path("C:/Program Files (x86)/Riot Games/League of Legends/lockfile"),
        Path("D:/Riot Games/League of Legends/lockfile")
    ]
    for default_path in windows_defaults:
        candidates.append(str(default_path))

    # 4순위: AppData 등 기타 경로 (Riot Client Config는 제외)
    local_app = os.environ.get("LOCALAPPDATA")
    program_data = os.environ.get("PROGRAMDATA")
    home = Path.home()

    riot_relative = [
        ("Riot Games", "League of Legends", "lockfile"),
        # ("Riot Games", "Riot Client", "Config", "lockfile")  <-- Riot Client 제외
    ]

    for base in filter(None, [local_app, program_data]):
        for parts in riot_relative:
            candidates.append(str(Path(base, *parts)))

    # macOS / Linux 경로
    candidates.append(str(home / "Library/Application Support/League of Legends/lockfile"))
    candidates.append(str(home / ".local/share/League of Legends/lockfile"))

    seen = []
    unique_candidates = []
    for path in candidates:
        if not path:
            continue
        normalized = os.path.abspath(path)
        if normalized in seen:
            continue
        seen.append(normalized)
        unique_candidates.append(normalized)
    return unique_candidates


def locate_lockfile_path() -> str:
    for path in build_lockfile_candidates():
        if os.path.exists(path):
            return path
    raise FileNotFoundError("lockfile을 찾을 수 없습니다. LOL 클라이언트가 켜져 있는지 확인하세요.")


def read_lockfile_metadata(lockfile_path: str) -> dict:
    try:
        with open(lockfile_path, "r", encoding="utf-8") as handle:
            contents = handle.read().strip()
    except OSError as exc:
        raise RuntimeError(f"lockfile을 열 수 없습니다: {exc}") from exc
    parts = contents.split(":")
    if len(parts) < 5:
        raise ValueError(f"lockfile 형식이 올바르지 않습니다: {contents}")
    name, pid, port, password, protocol = parts[:5]
    return {
        "name": name,
        "pid": pid,
        "port": port,
        "password": password,
        "protocol": protocol
    }


class LeagueClientError(Exception):
    def __init__(self, message: str, temporary: bool = False):
        super().__init__(message)
        self.temporary = temporary


if requests is None:  # pragma: no cover - optional dependency
    class LeagueClientWatcher:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("requests 패키지가 설치되어 있지 않아 LCU 연동 기능을 사용할 수 없습니다.")
else:
    class LeagueClientWatcher:
        LOCKFILE_ENV = "LOL_LOCKFILE"
        ALIAS_REFRESH_INTERVAL = 60.0
        DEFAULT_INTERVAL = 2.0

        def __init__(self, poll_interval: float = DEFAULT_INTERVAL):
            self.poll_interval = poll_interval
            self._callback = None
            self._status_callback = None
            self._thread = None
            self._stop_event = threading.Event()
            self._lockfile_path = None
            self._lockfile_mtime = None
            self._base_url = None
            self._auth = None
            self._champion_cache: dict[int, str] = {}
            self._last_signature = None
            self._last_status = ""
            self._alias_refreshed = 0.0
            self._had_session = False  # 이전에 세션이 있었는지 추적
            if urllib3 is not None:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        def start(self, callback, status_callback=None):
            self._callback = callback
            self._status_callback = status_callback
            if self._thread and self._thread.is_alive():
                return
            self._last_signature = None
            self._last_status = ""
            self._had_session = False  # 시작 시 세션 상태 초기화
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._thread.start()

        def stop(self):
            if self._thread and self._thread.is_alive():
                self._stop_event.set()
                self._thread.join(timeout=1.0)
            self._thread = None

        def is_running(self):
            return bool(self._thread and self._thread.is_alive())

        def fetch_snapshot(self):
            try:
                session = self._fetch_session()
            except LeagueClientError as exc:
                return None, str(exc)
            snapshot = self._session_to_snapshot(session)
            # phase가 있거나 myTeam/theirTeam 데이터가 있으면 유효한 스냅샷으로 간주
            if snapshot.get("phase") or snapshot.get("allies") or snapshot.get("enemies"):
                return snapshot, "픽 정보를 불러왔습니다."
            return None, "픽 정보를 감지하지 못했습니다."

        def resolve_champion_id(self, champion_id: int) -> str | None:
            return self._resolve_alias(champion_id)

        def _poll_loop(self):
            while not self._stop_event.is_set():
                snapshot, message = self.fetch_snapshot()
                if snapshot:
                    # 세션이 없었다가 새로 나타난 경우 (새 게임 시작) 로그 초기화
                    if not self._had_session:
                        reset_lcu_log()
                    self._had_session = True
                    
                    signature = (
                        tuple(entry["championId"] for entry in snapshot.get("allies", [])),
                        tuple(entry["championId"] for entry in snapshot.get("enemies", []))
                    )
                    if signature != self._last_signature:
                        self._last_signature = signature
                        if self._callback:
                            self._callback(snapshot, message)
                else:
                    # 세션이 사라진 경우 (게임 종료 또는 픽창 종료)
                    if self._had_session:
                        self._had_session = False
                    if message and message != self._last_status:
                        self._last_status = message
                        if self._status_callback:
                            self._status_callback(message)
                self._stop_event.wait(self.poll_interval)

        def _fetch_session(self):
            self._ensure_connection()
            
            endpoints = [
                "/lol-champ-select/v1/session",
                "/lol-champ-select-legacy/v1/session"
            ]
            
            for endpoint in endpoints:
                response = self._perform_lcu_get(endpoint, timeout=2.5, allow_404=True)
                if response is None:
                    continue
                try:
                    session = response.json()
                    
                    if session.get("phase") or session.get("myTeam") or session.get("theirTeam"):
                        return session
                except ValueError:
                    pass
            
            raise LeagueClientError("현재 픽창 단계가 아닙니다.", temporary=True)

        def _fetch_session_from_endpoint(self, path):
            # This method is deprecated and replaced by loop in _fetch_session, keeping it if needed or can be removed
            try:
                response = self._perform_lcu_get(path, timeout=2.5, allow_404=True)
            except LeagueClientError:
                raise
            if response is None:
                return None
            try:
                return response.json()
            except ValueError:
                return None

        def _ensure_connection(self):
            lockfile = self._find_lockfile()
            if not lockfile:
                raise LeagueClientError("League Client lockfile을 찾을 수 없습니다.")
            try:
                mtime = os.path.getmtime(lockfile)
            except OSError as exc:
                raise LeagueClientError(f"lockfile 정보를 읽을 수 없습니다: {exc}", temporary=True)
            if self._lockfile_mtime == mtime and self._base_url and self._auth:
                return
            self._lockfile_mtime = mtime
            try:
                with open(lockfile, "r", encoding="utf-8") as handle:
                    contents = handle.read().strip()
            except OSError as exc:
                raise LeagueClientError(f"lockfile 열기에 실패했습니다: {exc}", temporary=True)
            parts = contents.split(":")
            if len(parts) < 5:
                raise LeagueClientError("lockfile 포맷이 올바르지 않습니다.", temporary=True)
            _name, _pid, port, password, protocol = parts[:5]
            self._base_url = f"{protocol}://127.0.0.1:{port}"
            self._auth = ("riot", password)

        def _find_lockfile(self):
            if self._lockfile_path and os.path.exists(self._lockfile_path):
                return self._lockfile_path
            candidates = build_lockfile_candidates()
            for path in candidates:
                if os.path.exists(path):
                    self._lockfile_path = path
                    return path
            return None

        def _session_to_snapshot(self, session):
            return {
                "phase": session.get("phase"),
                "timestamp": time.time(),
                "allies": self._collect_team_entries(session, allies=True),
                "enemies": self._collect_team_entries(session, allies=False),
                "timer": session.get("timer")
            }

        def _collect_team_entries(self, session, allies: bool):
            team_key = "myTeam" if allies else "theirTeam"
            members = session.get(team_key, [])
            actions = self._collect_pick_actions(session, allies)
            local_player_cell_id = session.get("localPlayerCellId")
            
            cell_map = {}
            for member in members:
                cell_id = member.get("cellId")
                if cell_id is None:
                    continue
                cell_map[cell_id] = {
                    "cellId": cell_id,
                    "championId": member.get("championId"),
                    "assignedPosition": member.get("assignedPosition"),
                    "completed": True,  # 이미 완료된 픽으로 가정하되 actions로 덮어씌움
                    "pickTurn": 0,
                    "isLocalPlayer": (cell_id == local_player_cell_id)
                }
            
            for action in actions:
                cell_id = action.get("actorCellId")
                if cell_id is None:
                    continue
                
                # 아직 맵에 없는 셀(상대의 경우)이면 생성
                entry = cell_map.setdefault(cell_id, {
                    "cellId": cell_id,
                    "championId": 0,
                    "completed": False,
                    "pickTurn": 0,
                    "isLocalPlayer": (cell_id == local_player_cell_id)
                })
                
                # 액션의 챔피언 ID가 있으면 우선 사용 (실시간 픽)
                action_champ_id = action.get("championId")
                if action_champ_id:
                    entry["championId"] = action_champ_id
                
                entry["completed"] = action.get("completed", entry.get("completed", False))
                entry["pickTurn"] = action.get("pickTurn", entry.get("pickTurn", 0))
            
            results = []
            for entry in cell_map.values():
                champ_id = entry.get("championId")
                if not champ_id:
                    continue
                entry = entry.copy()
                entry["name"] = self._resolve_alias(champ_id)
                results.append(entry)
            results.sort(key=lambda item: (item.get("pickTurn", 0), item.get("cellId", 0)))
            return results

        def _collect_pick_actions(self, session, allies: bool):
            collected = []
            actions_struct = session.get("actions", [])
            # actions는 [[action1, action2], [action3]] 형태일 수 있음
            if not isinstance(actions_struct, list):
                return collected
                
            for action_group in actions_struct:
                if not isinstance(action_group, list):
                    continue
                for action in action_group:
                    if action.get("type") != "pick":
                        continue
                    is_ally_action = action.get("isAllyAction")
                    # 본인/아군 여부 필터링
                    if is_ally_action is not None and is_ally_action != allies:
                        continue
                        
                    champion_id = action.get("championId")
                    if not champion_id:
                        continue
                    collected.append(action)
            return collected

        def _resolve_alias(self, champion_id: int):
            alias = self._champion_cache.get(champion_id)
            now = time.time()
            if not alias and (now - self._alias_refreshed) > self.ALIAS_REFRESH_INTERVAL:
                self._refresh_champion_aliases()
                alias = self._champion_cache.get(champion_id)
            return alias or str(champion_id)

        def _refresh_champion_aliases(self):
            try:
                self._ensure_connection()
            except LeagueClientError:
                return
            payload = self._fetch_champion_grid_payload()
            if not payload:
                return
            updated = False
            for champion in payload:
                champ_id = champion.get("id")
                alias = champion.get("alias") or champion.get("name")
                if champ_id and alias:
                    self._champion_cache[int(champ_id)] = alias
                    updated = True
            if updated:
                self._alias_refreshed = time.time()

        def _fetch_champion_grid_payload(self):
            endpoints = [
                "/lol-champ-select/v1/all-grid-champions",
                "/lol-champ-select-legacy/v1/all-grid-champions"
            ]
            for endpoint in endpoints:
                try:
                    response = self._perform_lcu_get(endpoint, timeout=3.0, allow_404=True)
                except LeagueClientError:
                    return None
                if response is None:
                    continue
                try:
                    return response.json()
                except ValueError:
                    continue
            return None

        def _perform_lcu_get(self, path, timeout=2.5, allow_404=False):
            if not self._base_url or not self._auth:
                raise LeagueClientError("LCU 연결 정보가 없습니다.", temporary=True)
            url = f"{self._base_url}{path}"
            try:
                response = requests.get(url, auth=self._auth, timeout=timeout, verify=False)
            except requests.RequestException as exc:
                log_lcu_error("GET", path, exc, source="watcher")
                raise LeagueClientError(f"LCU 연결 실패: {exc}", temporary=True)
            log_lcu_response("GET", path, response, source="watcher")
            if response.status_code == 401:
                self._lockfile_mtime = None
                raise LeagueClientError("LCU 인증에 실패했습니다. 잠시 후 다시 시도하세요.", temporary=True)
            if response.status_code == 404 and allow_404:
                return None
            response.raise_for_status()
            return response
def diagnose_lcu_connection():
    if requests is None:
        return False, "requests 패키지가 설치되어 있지 않아 LCU 연결을 점검할 수 없습니다.", {}
    if urllib3 is not None:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    report_lines = []
    details = {}
    try:
        lockfile_path = locate_lockfile_path()
        report_lines.append(f"lockfile 감지: {lockfile_path}")
        details["lockfile"] = lockfile_path
    except FileNotFoundError as exc:
        return False, str(exc), details

    try:
        metadata = read_lockfile_metadata(lockfile_path)
    except (RuntimeError, ValueError) as exc:
        return False, str(exc), details

    port = metadata["port"]
    password = metadata["password"]
    protocol = metadata["protocol"]
    base_url = f"{protocol}://127.0.0.1:{port}"
    details["base_url"] = base_url
    auth = ("riot", password)
    headers = {
        "Accept": "application/json"
    }
    report_lines.append(f"LCU 포트 {port} 연결 정보 확보 (protocol={protocol}).")

    try:
        summoner_resp = requests.get(
            f"{base_url}/lol-summoner/v1/current-summoner",
            auth=auth,
            headers=headers,
            timeout=2.0,
            verify=False
        )
        log_lcu_response("GET", "/lol-summoner/v1/current-summoner", summoner_resp, source="diagnose")
        summoner_resp.raise_for_status()
        summoner_data = summoner_resp.json()
        display_name = None
        if isinstance(summoner_data, dict):
            display_name = (
                summoner_data.get("displayName")
                or summoner_data.get("gameName")
                or summoner_data.get("internalName")
            )
        if display_name:
            report_lines.append(f"소환사 인증 확인: {display_name}")
            details["summoner"] = display_name
        else:
            report_lines.append("소환사 정보를 불러왔지만 이름을 확인하지 못했습니다.")
    except requests.RequestException as exc:
        log_lcu_error("GET", "/lol-summoner/v1/current-summoner", exc, source="diagnose")
        report_lines.append(f"소환사 정보를 불러오지 못했습니다 (계속 진행): {exc}")
    except ValueError:
        report_lines.append("소환사 정보 JSON 파싱 실패.")

    session_detected = False
    for endpoint in ("/lol-champ-select/v1/session", "/lol-champ-select-legacy/v1/session"):
        try:
            session_resp = requests.get(
                f"{base_url}{endpoint}",
                auth=auth,
                headers=headers,
                timeout=1.5,
                verify=False
            )
            log_lcu_response("GET", endpoint, session_resp, source="diagnose")
        except requests.RequestException as exc:
            log_lcu_error("GET", endpoint, exc, source="diagnose")
            report_lines.append(f"{endpoint} 호출 실패: {exc}")
            continue
        if session_resp.status_code == 404:
            report_lines.append(f"{endpoint}: 현재 픽창 단계가 아닙니다 (404).")
            continue
        try:
            session_resp.raise_for_status()
        except requests.RequestException as exc:
            log_lcu_error("GET", endpoint, exc, source="diagnose")
            report_lines.append(f"{endpoint} 응답 오류: {exc}")
            continue
        try:
            session_payload = session_resp.json()
        except ValueError:
            report_lines.append(f"{endpoint} JSON 파싱 실패.")
            continue
        phase = session_payload.get("phase")
        # 커스텀 게임 등에서 phase가 없더라도 팀 정보가 있으면 유효 세션으로 간주
        has_team_info = bool(session_payload.get("myTeam") or session_payload.get("theirTeam"))
        
        if not phase:
            timer = session_payload.get("timer", {})
            timer_phase = timer.get("phase")
            if timer_phase:
                phase = f"Timer:{timer_phase}"
            elif has_team_info:
                phase = "Custom/Active (Phase 없음)"
            else:
                # phase도 없고 팀 정보도 없으면 유효하지 않은 세션일 가능성 높음
                report_lines.append(f"{endpoint}: 세션 데이터가 비어있거나 유효하지 않습니다.")
                continue
        
        report_lines.append(f"픽창 세션 감지 ({phase}) via {endpoint}")
        details["phase"] = phase
        session_detected = True
        break

    if not session_detected:
        summoner_name = details.get("summoner", "소환사")
        report_lines.append(f"연결 완료! {summoner_name} 님 테스트 감사드립니다. (_ _)")
    else:
        # 세션이 감지되었지만 phase가 없는 경우(커스텀 등), 챔피언 정보도 확인
        if details.get("phase") == "Custom/Active (Phase 없음)":    
            report_lines.append("참고: 커스텀 게임은 픽창 단계 정보(Phase)가 없을 수 있습니다.")

    return True, "\n".join(report_lines), details



class ChampionScraperApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"TtimoTtabbong {APP_VERSION}")
        try:
            self.root.iconbitmap("icon.ico")
        except tk.TclError:
            pass  # 아이콘 파일이 없거나 로드 실패 시 무시
        self.root.state('zoomed')  # Start maximized
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.notebook = ttk.Notebook(root)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        self.dashboard_tab = tk.Frame(self.notebook)
        self.notebook.add(self.dashboard_tab, text="챔피언 추천")
        self.recommend_counter_cache = {}
        
        self._lane_swap_guard = False
        self.paned_window = None  # Will be set in build_dashboard_tab
        self.ui_settings = self._load_ui_settings()  # Load UI settings
        self.weight_settings = load_weight_settings()  # Load weight settings
        
        # 테마 초기화
        saved_theme = self.ui_settings.get("theme", "light")
        self.current_theme = THEME_DARK if saved_theme == "dark" else THEME_LIGHT
        
        self.client_watcher = None
        self.client_sync_supported = True
        self.client_sync_error = None
        self.last_client_snapshot = None
        
        (
            self.canonical_lookup,
            self.alias_lookup,
            self.display_lookup,
            self.autocomplete_candidates
        ) = load_alias_tables()
        self.ignored_champions = self._initialize_ignored_champions()
        
        try:
            self.client_watcher = LeagueClientWatcher()
        except RuntimeError as exc:
            self.client_sync_supported = False
            self.client_sync_error = str(exc)

        initial_lcu_status = "연결 상태 미확인"
        if requests is None:
            initial_lcu_status = "requests 미설치로 LCU 점검 불가"
        self.lcu_status_var = tk.StringVar(value=initial_lcu_status)
        self.client_sync_var = tk.BooleanVar(value=True)

        self.apply_theme()
        
        self.build_dashboard_tab()
        
        # Initialize other tabs
        self.counter_synergy_tab = CounterSynergyTab(self.notebook, self)
        self.op_duos_tab = OpDuosTab(self.notebook, self, DATA_DIR)
        self.ignore_tab = IgnoreTab(self.notebook, self)
        self.credits_tab = CreditsTab(self.notebook, self)
        self.notebook.add(self.credits_tab, text="고마운 분들")
        
        # Weight settings tab
        self.weight_settings_tab = WeightSettingsTab(self.notebook, self)

    def apply_theme(self, theme=None):
        """현재 테마 또는 지정된 테마를 적용합니다."""
        if theme is not None:
            self.current_theme = theme
        
        t = self.current_theme
        bg_color = t["bg_color"]
        fg_color = t["fg_color"]
        accent_color = t["accent_color"]
        select_color = t["select_color"]
        button_color = t["button_color"]
        button_fg = t["button_fg"]
        entry_bg = t["entry_bg"]
        entry_fg = t["entry_fg"]
        treeview_bg = t["treeview_bg"]
        treeview_heading_bg = t["treeview_heading_bg"]
        button_active_bg = t["button_active_bg"]
        button_pressed_bg = t["button_pressed_bg"]
        
        # 다크모드에서 비활성화 버튼 색상 조정
        is_dark = t["name"] == "dark"
        disabled_bg = "#45475A" if is_dark else "#E0E0E0"
        disabled_fg = "#6C7086" if is_dark else "#5D4037"
        
        # Configure standard Tk widgets via option database
        self.root.option_add("*Background", bg_color)
        self.root.option_add("*Foreground", fg_color)
        self.root.option_add("*Entry.Background", entry_bg)
        self.root.option_add("*Entry.Foreground", entry_fg)
        self.root.option_add("*Listbox.Background", entry_bg)
        self.root.option_add("*Listbox.Foreground", entry_fg)
        self.root.option_add("*Button.Background", button_color)
        self.root.option_add("*Button.Foreground", button_fg)
        self.root.option_add("*Button.activeBackground", button_active_bg)
        self.root.option_add("*Button.activeForeground", button_fg)
        self.root.option_add("*Button.disabledForeground", disabled_fg)
        self.root.option_add("*Label.Background", bg_color)
        self.root.option_add("*Label.Foreground", fg_color)
        self.root.option_add("*Frame.Background", bg_color)
        self.root.option_add("*LabelFrame.Background", bg_color)
        self.root.option_add("*LabelFrame.Foreground", fg_color)
        self.root.option_add("*Checkbutton.Background", bg_color)
        self.root.option_add("*Checkbutton.Foreground", fg_color)
        self.root.option_add("*Checkbutton.selectColor", accent_color)
        self.root.option_add("*Radiobutton.Background", bg_color)
        self.root.option_add("*Radiobutton.Foreground", fg_color)
        self.root.option_add("*Radiobutton.selectColor", accent_color)
        
        self.root.configure(bg=bg_color)
        
        # Configure TTK styles
        style = ttk.Style(self.root)
        style.theme_use('clam')  # Use clam as base for better color customization
        
        style.configure(".", background=bg_color, foreground=fg_color, font=("Segoe UI", 9))
        style.configure("TFrame", background=bg_color)
        style.configure("TLabel", background=bg_color, foreground=fg_color)
        style.configure("TButton", background=button_color, foreground=button_fg, borderwidth=1)
        style.map("TButton",
            background=[("pressed", button_pressed_bg), ("active", button_active_bg), ("disabled", disabled_bg)],
            foreground=[("pressed", button_fg), ("active", button_fg), ("disabled", disabled_fg)]
        )
        style.configure("TNotebook", background=bg_color, tabposition='n')
        style.configure("TNotebook.Tab", background=accent_color, foreground=fg_color, padding=[10, 2])
        style.map("TNotebook.Tab",
            background=[("selected", select_color)],
            foreground=[("selected", fg_color)]
        )
        style.configure("Treeview", 
            background=treeview_bg,
            foreground=fg_color,
            fieldbackground=treeview_bg,
            borderwidth=0
        )
        style.configure("Treeview.Heading", 
            background=treeview_heading_bg, 
            foreground=fg_color,
            font=("Segoe UI", 9, "bold")
        )
        style.map("Treeview", background=[("selected", select_color)], foreground=[("selected", fg_color)])
        
        # TCombobox 스타일 (다크모드 호환)
        style.configure("TCombobox",
            background=entry_bg,
            foreground=entry_fg,
            fieldbackground=entry_bg,
            selectbackground=select_color,
            selectforeground=fg_color
        )
        style.map("TCombobox",
            fieldbackground=[("readonly", entry_bg)],
            selectbackground=[("readonly", select_color)]
        )
        
        # Custom styles for specific widgets
        style.configure("TLabelframe", background=bg_color, foreground=fg_color)
        style.configure("TLabelframe.Label", background=bg_color, foreground=fg_color)
        
        # Treeview 태그 색상 갱신
        low_sample_color = t["low_sample"]
        normal_sample_color = t["normal_sample"]
        
        # counter_synergy_tab이 있으면 Treeview 색상 갱신
        if hasattr(self, "counter_synergy_tab") and self.counter_synergy_tab:
            self.counter_synergy_tab.update_tree_colors(low_sample_color, normal_sample_color)
        
        # 테마 토글 버튼 텍스트 갱신
        if hasattr(self, "theme_toggle_button"):
            if is_dark:
                self.theme_toggle_button.config(text="☀️ 라이트")
            else:
                self.theme_toggle_button.config(text="🌙 다크")


    def build_dashboard_tab(self):
        self.banpick_slots = {"allies": [], "enemies": []}
        self.my_lane_var = tk.StringVar(value="")
        self.my_lane_var.trace_add("write", lambda *_: self.update_banpick_recommendations())
        lcu_frame = tk.LabelFrame(self.dashboard_tab, text="클라이언트 연결 상태")
        lcu_frame.pack(fill="x", padx=10, pady=(0, 5))
        tk.Label(
            lcu_frame,
            textvariable=self.lcu_status_var,
            anchor="w"
        ).pack(side="left", padx=(8, 10))
        self.lcu_check_button = tk.Button(
            lcu_frame,
            text="연결",
            command=self.on_lcu_check_clicked,
            state="normal" if requests is not None else "disabled"
        )
        self.lcu_check_button.pack(side="left")
        
        # 자동 동기화 및 수동 버튼 프레임
        sync_frame = tk.Frame(lcu_frame)
        sync_frame.pack(side="left", padx=(10, 0))
        self.client_sync_checkbox = tk.Checkbutton(
            sync_frame,
            text="자동 동기화",
            variable=self.client_sync_var,
            command=self.on_client_sync_toggle,
            state="disabled" # 연결 점검 성공 후 활성화
        )
        self.client_sync_checkbox.pack(side="left")
        
        self.client_fetch_button = tk.Button(
            sync_frame,
            text="수동 불러오기",
            command=self.manual_client_import,
            state="disabled" # 연결 점검 성공 후 활성화
        )
        self.client_fetch_button.pack(side="left", padx=(5, 0))

        self.save_snapshot_button = tk.Button(
            sync_frame,
            text="스냅샷 저장",
            command=self.save_snapshot,
            state="disabled"
        )
        self.save_snapshot_button.pack(side="left", padx=(5, 0))
        
        # 테마 토글 버튼
        is_dark = self.current_theme["name"] == "dark"
        theme_text = "☀️ 라이트" if is_dark else "🌙 다크"
        self.theme_toggle_button = tk.Button(
            lcu_frame,
            text=theme_text,
            command=self.toggle_theme,
            width=10
        )
        self.theme_toggle_button.pack(side="right", padx=(5, 8))
        
        # My Lane selection frame
        my_lane_frame = tk.LabelFrame(self.dashboard_tab, text="나의 라인")
        my_lane_frame.pack(fill="x", padx=10, pady=(5, 5))
        
        lane_names = [
            ("top", "탑"),
            ("jungle", "정글"),
            ("middle", "미드"),
            ("bottom", "바텀"),
            ("support", "서포터")
        ]
        
        for lane_value, lane_label in lane_names:
            tk.Radiobutton(
                my_lane_frame,
                text=lane_label,
                variable=self.my_lane_var,
                value=lane_value,
                indicatoron=0,
                width=8
            ).pack(side="left", padx=5, pady=5)
        
        # Clear selection button
        tk.Button(
            my_lane_frame,
            text="선택 해제",
            command=lambda: self.my_lane_var.set("")
        ).pack(side="left", padx=10)
        
        # Create PanedWindow for resizable layout
        self.paned_window = tk.PanedWindow(self.dashboard_tab, orient=tk.VERTICAL, sashrelief=tk.RAISED, sashwidth=5)
        self.paned_window.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Top pane: slots container
        top_pane = tk.Frame(self.paned_window)
        self.paned_window.add(top_pane, minsize=200)
        
        container = tk.Frame(top_pane)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)

        tk.Button(
            top_pane,
            text="대시보드 초기화",
            command=self.reset_dashboard_tab
        ).pack(anchor="ne", padx=0, pady=(5, 0))

        left_column, left_total_label = self._create_banpick_column(container, "우리팀", "allies")
        left_column.grid(row=0, column=0, sticky="nsw", padx=(0, 5))
        
        right_column, right_total_label = self._create_banpick_column(container, "상대팀", "enemies")
        right_column.grid(row=0, column=1, sticky="nse", padx=(5, 0))
        
        self.team_total_labels = {
            "allies": left_total_label,
            "enemies": right_total_label
        }

        # Bottom pane: recommendations
        recommend_frame = tk.LabelFrame(self.paned_window, text="추천 챔피언")
        self.paned_window.add(recommend_frame, minsize=150)
        
        # Restore saved sash position after a delay to ensure window is rendered
        if "paned_sash_percentage" in self.ui_settings:
            self.root.after(500, lambda: self._restore_sash_position())
        
        # Bind events to save position when dragging ends
        self.paned_window.bind("<ButtonRelease-1>", self._on_paned_window_moved)

        filter_frame = tk.Frame(recommend_frame)
        filter_frame.pack(fill="x", padx=5, pady=(5, 0))
        tk.Label(filter_frame, text="최소 게임 수").pack(side="left")
        self.recommend_min_games_entry = tk.Entry(filter_frame, width=6)
        self.recommend_min_games_entry.insert(0, str(BANPICK_MIN_GAMES_DEFAULT))
        self.recommend_min_games_entry.pack(side="left", padx=(4, 0))
        self.recommend_min_games_entry.bind("<KeyRelease>", lambda _e: self.update_banpick_recommendations())
        self.recommend_min_games_entry.bind("<FocusOut>", lambda _e: self.update_banpick_recommendations())

        tk.Label(filter_frame, text="최소 픽률").pack(side="left", padx=(10, 0))
        self.recommend_pick_rate_entry = tk.Entry(filter_frame, width=6)
        self.recommend_pick_rate_entry.insert(0, str(BANPICK_PICK_RATE_OVERRIDE))
        self.recommend_pick_rate_entry.pack(side="left", padx=(4, 0))
        self.recommend_pick_rate_entry.bind("<KeyRelease>", lambda _e: self.update_banpick_recommendations())
        self.recommend_pick_rate_entry.bind("<FocusOut>", lambda _e: self.update_banpick_recommendations())

        columns = ("챔피언", "태그", "최종 점수", "시너지", "카운터")
        self.recommend_tree = ttk.Treeview(recommend_frame, columns=columns, show="headings", height=8)
        for col in columns:
            self.recommend_tree.heading(col, text=col)
            self.recommend_tree.column(col, anchor="center")
        self.recommend_tree.column("챔피언", anchor="w", width=100)
        self.recommend_tree.column("태그", anchor="w", width=50)
        self.recommend_tree.column("최종 점수", width=10)
        self.recommend_tree.column("시너지", width=500)
        self.recommend_tree.column("카운터", width=500)
        scroll = tk.Scrollbar(recommend_frame, orient="vertical", command=self.recommend_tree.yview)
        scroll.pack(side="right", fill="y")
        self.recommend_tree.configure(yscrollcommand=scroll.set)
        self.recommend_tree.pack(fill="both", expand=True)
        action_frame = tk.Frame(recommend_frame)
        action_frame.pack(fill="x", padx=5, pady=(5, 5))
        tk.Button(
            action_frame,
            text="선택 챔피언 제외",
            command=self.ignore_selected_recommendations
        ).pack(side="right")

    def manual_client_import(self):
        if not self.client_sync_supported or not self.client_watcher:
            if self.client_sync_error:
                messagebox.showerror("클라이언트 연동", self.client_sync_error)
            return
        snapshot, message = self.client_watcher.fetch_snapshot()
        if snapshot:
            changed = self._apply_client_snapshot(snapshot)
            phase = snapshot.get("phase")
            
            # phase가 없으면 타이머나 팀 정보 유무로 대체 표시
            if not phase:
                has_team_info = bool(snapshot.get("allies") or snapshot.get("enemies"))
                timer_phase = snapshot.get("timer", {}).get("phase") if isinstance(snapshot, dict) else None
                if timer_phase:
                    phase = f"Timer:{timer_phase}"
                elif has_team_info:
                    phase = "Custom/Active"
                else:
                    phase = "알 수 없음"

            status = f"{phase} - 수동 동기화 완료"
            self._set_client_status(status)
            if not changed:
                info = "픽창 정보를 확인했으나 변경된 내용이 없습니다."
                if message:
                    info = f"{message} (변경 없음)"
                messagebox.showinfo("클라이언트 연동", info)
            return
        info = message or "픽창 정보를 가져올 수 없습니다."
        messagebox.showinfo("클라이언트 연동", info)
        self._set_client_status(info)

    def on_client_sync_toggle(self):
        if not self.client_sync_supported or not self.client_watcher:
            self.client_sync_var.set(False)
            if self.client_sync_error:
                messagebox.showerror("클라이언트 연동", self.client_sync_error)
            return
        if self.client_sync_var.get():
            self._start_client_sync()
        else:
            self._stop_client_sync()

    def _start_client_sync(self):
        if not self.client_watcher:
            return
        self._set_client_status("클라이언트 감지 중...")
        self.client_watcher.start(self.handle_client_snapshot, self.handle_client_status)

    def _stop_client_sync(self):
        if self.client_watcher:
            self.client_watcher.stop()
        self._set_client_status("클라이언트 연동 꺼짐")

    def handle_client_snapshot(self, snapshot, _message=None):
        if not snapshot:
            return
        self.root.after(0, lambda: self._apply_snapshot_and_status(snapshot))

    def handle_client_status(self, message):
        self.root.after(0, lambda: self._set_client_status(message))

    def _apply_snapshot_and_status(self, snapshot):
        changed = self._apply_client_snapshot(snapshot)
        phase = snapshot.get("phase")
        
        # 자동 동기화 상태에서도 phase가 없을 때 메시지 구체화
        if not phase:
            has_team_info = bool(snapshot.get("allies") or snapshot.get("enemies"))
            timer_phase = snapshot.get("timer", {}).get("phase") if isinstance(snapshot, dict) else None
            if timer_phase:
                phase = f"Timer:{timer_phase}"
            elif has_team_info:
                phase = "Custom/Active"
            else:
                phase = "알 수 없음"
                
        status = f"{phase} - 자동 동기화"
        if not changed:
            status = f"{phase} - 업데이트 없음"
        self._set_client_status(status)

    def _apply_client_snapshot(self, snapshot):
        allies = self._normalize_client_entries(snapshot.get("allies", []))
        enemies = self._normalize_client_entries(snapshot.get("enemies", []))
        changed = False
        changed |= self._populate_side_from_client("allies", allies)
        changed |= self._populate_side_from_client("enemies", enemies)
        if changed:
            self.update_banpick_recommendations()
        self.last_client_snapshot = snapshot
        return changed

    def _normalize_client_entries(self, entries):
        normalized_entries = []
        for entry in entries:
            name = entry.get("name")
            champion_id = entry.get("championId")
            is_local_player = entry.get("isLocalPlayer", False)
            
            canonical = self.resolve_champion_name(name) if name else None
            if not canonical and isinstance(champion_id, int) and self.client_watcher:
                alias = self.client_watcher.resolve_champion_id(champion_id)
                canonical = self.resolve_champion_name(alias) if alias else None
                name = name or alias
            display = name or str(champion_id)
            normalized = None
            if canonical:
                normalized = canonical.lower()
                display = self.display_lookup.get(canonical, canonical.title())
            elif isinstance(name, str):
                normalized = name.lower()
            elif champion_id:
                normalized = str(champion_id)
            normalized_entries.append({
                "display": display,
                "canonical": canonical or name or str(champion_id),
                "normalized": normalized,
                "isLocalPlayer": is_local_player
            })
        return normalized_entries

    def _populate_side_from_client(self, side_key, entries):
        slots = self.banpick_slots.get(side_key, [])
        if not slots:
            return False
        changed = False
        for idx, slot in enumerate(slots):
            if idx < len(entries):
                changed |= self._populate_slot_from_client(slot, entries[idx])
            else:
                changed |= self._clear_slot_from_client(slot)
        return changed

    def _populate_slot_from_client(self, slot, entry):
        normalized = entry.get("normalized")
        canonical = entry.get("canonical")
        display = entry.get("display")
        is_local_player = entry.get("isLocalPlayer")
        
        if not canonical:
            return False
            
        slot_canonical = slot.get("canonical_name")
        
        # 내 픽이면서 아직 슬롯이 내 차례가 아니거나 비어있다면 강제 입력
        if is_local_player:
            active_check = slot.get("active_check")
            if active_check and not self.active_slot_var.get():
                self.active_slot_var.set(f"{slot.get('side')}:{slot.get('index')}")
        
        if slot_canonical and normalized and slot_canonical.lower() == normalized:
            slot["client_last_champion"] = normalized
            return False
        widget = slot.get("entry")
        if widget:
            widget.delete(0, tk.END)
            widget.insert(0, display)
        success = self.perform_banpick_search(slot, auto_trigger=True)
        if success:
            slot["client_last_champion"] = normalized or (canonical.lower() if isinstance(canonical, str) else canonical)
        return success

    def _clear_slot_from_client(self, slot):
        if not slot.get("client_last_champion"):
            return False
        self.clear_banpick_slot(slot, reset_lane=False, suppress_update=True)
        slot["client_last_champion"] = None
        return True

    def _set_client_status(self, message):
        if hasattr(self, "client_status_var"):
            self.client_status_var.set(message)

    def on_lcu_check_clicked(self):
        if requests is None:
            messagebox.showerror("클라이언트 연결 점검", "requests 패키지가 설치되어 있지 않아 점검을 수행할 수 없습니다.")
            return
        success, report, _details = diagnose_lcu_connection()
        if report:
            status_line = report.splitlines()[-1]
        else:
            status_line = "연결 성공" if success else "연결 실패"
        self.lcu_status_var.set(status_line)
        if success:
            self.client_sync_checkbox.config(state="normal")
            self.client_fetch_button.config(state="normal")
            self.save_snapshot_button.config(state="normal")
            messagebox.showinfo("클라이언트 연결 점검", report)
            if self.client_sync_var.get():
                self._start_client_sync()
        else:
            self.client_sync_checkbox.config(state="disabled")
            self.client_fetch_button.config(state="disabled")
            self.save_snapshot_button.config(state="disabled")
            messagebox.showerror("클라이언트 연결 점검", report)

    def ignore_selected_recommendations(self):
        if self.ignore_tab:
            selection = self.recommend_tree.selection()
            self.ignore_tab.ignore_selected_recommendations(selection)

    def persist_ignored_champions(self):
        canonical_names = []
        for normalized in self.ignored_champions:
            canonical = self.canonical_lookup.get(normalized, normalized)
            canonical_names.append(canonical)
        save_ignored_champion_names(canonical_names)

    def on_ignore_list_updated(self):
        # Update caches if necessary (not directly exposed now, managed by tabs)
        # But wait, counter_synergy_tab has caches.
        if self.counter_synergy_tab:
            for dataset in self.counter_synergy_tab.counter_cache.values():
                self._apply_ignore_filter(dataset)
            for dataset in self.counter_synergy_tab.synergy_cache.values():
                self._apply_ignore_filter(dataset)
            self._apply_ignore_filter(self.counter_synergy_tab.all_data)
            self._apply_ignore_filter(self.counter_synergy_tab.synergy_data)
            self.counter_synergy_tab.update_GUI()
            self.counter_synergy_tab.update_synergy_GUI()

        self.recommend_counter_cache.clear()
        
        self.update_banpick_recommendations()
        if self.op_duos_tab:
            self.op_duos_tab.populate_synergy_highlights()
        if self.ignore_tab:
            self.ignore_tab.refresh_ignore_listbox()

    def _create_banpick_column(self, parent, title, side_key):
        column = tk.LabelFrame(parent, text=title)
        for idx in range(5):
            slot_frame = tk.Frame(column, bd=1, relief="groove", padx=6, pady=6)
            slot_frame.pack(fill="x", pady=4)
            
            # 슬롯 프레임의 컬럼 가중치 설정 (가로 크기 최적화)
            slot_frame.grid_columnconfigure(0, weight=1)  # entry 영역 확장
            slot_frame.grid_columnconfigure(2, weight=0)  # lane_box 영역 (고정 크기)
            slot_frame.grid_columnconfigure(4, weight=0)  # search_button 영역 (고정 크기)

            tk.Label(slot_frame, text=f"슬롯 {idx + 1}", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
            
            # Manual Checkbox
            manual_var = tk.BooleanVar(value=False)
            manual_check = tk.Checkbutton(
                slot_frame,
                text="수동",
                variable=manual_var
            )
            manual_check.grid(row=0, column=1, padx=(10, 0), sticky="e")

            # Exclude Checkbox
            exclude_var = tk.BooleanVar(value=False)
            exclude_var.trace_add("write", lambda *args: (self.update_banpick_recommendations(), self.update_team_total_scores()))
            exclude_check = tk.Checkbutton(
                slot_frame,
                text="데이터 제외",
                variable=exclude_var
            )
            exclude_check.grid(row=0, column=2, padx=(2, 0), sticky="e")

            clear_button = tk.Button(slot_frame, text="데이터 제거", width=8)
            clear_button.grid(row=0, column=3, padx=(6, 0), sticky="e")

            entry = tk.Entry(slot_frame, width=11)
            entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 2))

            lane_box = ttk.Combobox(slot_frame, values=LANES, state="readonly", width=9)
            lane_box.grid(row=1, column=2, padx=(6, 0), pady=(4, 2), sticky="w")
            if idx < len(BANPICK_DEFAULT_LANES):
                lane_box.set(BANPICK_DEFAULT_LANES[idx])
            else:
                lane_box.set("라인 선택")

            search_button = tk.Button(slot_frame, text="검색", width=5)
            search_button.grid(row=1, column=3, padx=(6, 0), sticky="e")

            result_var = tk.StringVar(value="검색 결과 없음")
            result_label = tk.Label(slot_frame, textvariable=result_var, anchor="w")
            result_label.grid(row=2, column=0, columnspan=5, sticky="ew", pady=(6, 0))

            slot = {
                "side": side_key,
                "index": idx,
                "entry": entry,
                "lane": lane_box,
                "button": search_button,
                "clear_button": clear_button,
                "result_var": result_var,
                "result_label": result_label,  # 툴팁용
                "exclude_var": exclude_var,
                "manual_var": manual_var,
                "display_name": None,
                "canonical_name": None,
                "selected_lane": None,
                "synergy_dataset": None,
                "counter_dataset": None,
                "last_lane_value": None,
                "last_lane": None,
                "score_details": None  # 점수 계산 상세 정보
            }

            search_button.configure(command=lambda s=slot: self.perform_banpick_search(s))
            entry.bind("<Return>", lambda event, s=slot: self.perform_banpick_search(s))
            lane_box.bind("<<ComboboxSelected>>", lambda _event, s=slot: self.on_banpick_lane_changed(s))
            clear_button.configure(command=lambda s=slot: self.clear_banpick_slot(s))

            slot["autocomplete"] = AutocompletePopup(
                entry,
                self.get_autocomplete_candidates,
                on_select=lambda _value, s=slot: self.perform_banpick_search(s, auto_trigger=False)
            )
            
            # 점수 상세 정보 툴팁 추가
            slot["tooltip"] = ScoreTooltip(
                result_label,
                lambda s=slot: self._get_score_tooltip_text(s)
            )

            self._update_slot_lane_cache(slot)
            self.banpick_slots[side_key].append(slot)

        # 조합 점수 레이블을 컬럼 내부 하단에 추가
        default_color = self.current_theme.get("score_default", "blue")
        total_label = tk.Label(column, text="조합 점수: 0.00", font=("Segoe UI", 10, "bold"), fg=default_color)
        total_label.pack(fill="x", pady=(10, 5))

        return column, total_label

    def manual_client_import(self):
        if not self.client_sync_supported or not self.client_watcher:
            if self.client_sync_error:
                messagebox.showerror("클라이언트 연동", self.client_sync_error)
            return
        snapshot, message = self.client_watcher.fetch_snapshot()
        if snapshot:
            changed = self._apply_client_snapshot(snapshot)
            phase = snapshot.get("phase")
            
            # phase가 없으면 타이머나 팀 정보 유무로 대체 표시
            if not phase:
                has_team_info = bool(snapshot.get("allies") or snapshot.get("enemies"))
                timer_phase = snapshot.get("timer", {}).get("phase") if isinstance(snapshot, dict) else None
                if timer_phase:
                    phase = f"Timer:{timer_phase}"
                elif has_team_info:
                    phase = "Custom/Active"
                else:
                    phase = "알 수 없음"

            status = f"{phase} - 수동 동기화 완료"
            self._set_client_status(status)
            if not changed:
                info = "픽창 정보를 확인했으나 변경된 내용이 없습니다."
                if message:
                    info = f"{message} (변경 없음)"
                messagebox.showinfo("클라이언트 연동", info)
            return
        info = message or "픽창 정보를 가져올 수 없습니다."
        messagebox.showinfo("클라이언트 연동", info)
        self._set_client_status(info)

    def on_client_sync_toggle(self):
        if not self.client_sync_supported or not self.client_watcher:
            self.client_sync_var.set(False)
            if self.client_sync_error:
                messagebox.showerror("클라이언트 연동", self.client_sync_error)
            return
        if self.client_sync_var.get():
            self._start_client_sync()
        else:
            self._stop_client_sync()

    def _start_client_sync(self):
        if not self.client_watcher:
            return
        self._set_client_status("클라이언트 감지 중...")
        self.client_watcher.start(self.handle_client_snapshot, self.handle_client_status)

    def _stop_client_sync(self):
        if self.client_watcher:
            self.client_watcher.stop()
        self._set_client_status("클라이언트 연동 꺼짐")

    def handle_client_snapshot(self, snapshot, _message=None):
        if not snapshot:
            return
        self.root.after(0, lambda: self._apply_snapshot_and_status(snapshot))

    def handle_client_status(self, message):
        self.root.after(0, lambda: self._set_client_status(message))

    def save_snapshot(self):
        if not hasattr(self, "last_client_snapshot") or not self.last_client_snapshot:
            messagebox.showinfo("Info", "저장할 스냅샷 데이터가 없습니다.")
            return

        debug_dir = "debug_data"
        if not os.path.exists(debug_dir):
            os.makedirs(debug_dir)
        
        timestamp = int(time.time())
        filename = f"snapshot_{timestamp}.json"
        filepath = os.path.join(debug_dir, filename)
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.last_client_snapshot, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("Success", f"스냅샷이 저장되었습니다:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"스냅샷 저장 실패: {e}")

    def _apply_snapshot_and_status(self, snapshot):
        changed = self._apply_client_snapshot(snapshot)
        phase = snapshot.get("phase")
        
        # 자동 동기화 상태에서도 phase가 없을 때 메시지 구체화
        if not phase:
            has_team_info = bool(snapshot.get("allies") or snapshot.get("enemies"))
            timer_phase = snapshot.get("timer", {}).get("phase") if isinstance(snapshot, dict) else None
            if timer_phase:
                phase = f"Timer:{timer_phase}"
            elif has_team_info:
                phase = "Custom/Active"
            else:
                phase = "알 수 없음"
                
        status = f"{phase} - 자동 동기화"
        if not changed:
            status = f"{phase} - 업데이트 없음"
        self._set_client_status(status)

    def _apply_client_snapshot(self, snapshot):
        allies = self._normalize_client_entries(snapshot.get("allies", []))
        enemies = self._normalize_client_entries(snapshot.get("enemies", []))
        changed = False
        changed |= self._populate_side_from_client("allies", allies)
        changed |= self._populate_side_from_client("enemies", enemies)
        if changed:
            self.update_banpick_recommendations()
        self.last_client_snapshot = snapshot
        return changed

    def _normalize_client_entries(self, entries):
        normalized_entries = []
        for entry in entries:
            name = entry.get("name")
            champion_id = entry.get("championId")
            is_local_player = entry.get("isLocalPlayer", False)
            
            canonical = self.resolve_champion_name(name) if name else None
            if not canonical and isinstance(champion_id, int) and self.client_watcher:
                alias = self.client_watcher.resolve_champion_id(champion_id)
                canonical = self.resolve_champion_name(alias) if alias else None
                name = name or alias
            display = name or str(champion_id)
            normalized = None
            if canonical:
                normalized = canonical.lower()
                display = self.display_lookup.get(canonical, canonical.title())
            elif isinstance(name, str):
                normalized = name.lower()
            elif champion_id:
                normalized = str(champion_id)
            normalized_entries.append({
                "display": display,
                "canonical": canonical or name or str(champion_id),
                "normalized": normalized,
                "isLocalPlayer": is_local_player,
                "assignedPosition": entry.get("assignedPosition")
            })
        return normalized_entries

    def _get_champion_lane_pick_rates(self, champion_name):
        """
        Calculate pick rate (games count) for each lane for a champion.
        Returns a dict: {'jungle': 12000, 'support': 500, ...}
        """
        if not champion_name:
            return {}
            
        full_name = self.resolve_champion_name(champion_name)
        if not full_name:
            return {}
            
        pick_rates = {}
        
        for lane in LANES:
            data_filename = f"{full_name}_{lane}.json".replace(" ", "_")
            filename = resolve_resource_path("data", data_filename)
            
            try:
                with open(filename, "r", encoding="utf-8") as file:
                    raw_data = json.load(file)
                    
                    # Get games count from counters -> [lane]
                    # We use the same lane key to avoid double counting
                    counters = raw_data.get("counters", {})
                    lane_data = counters.get(lane, {})
                    
                    total_games = 0
                    for enemy_data in lane_data.values():
                        games_str = enemy_data.get("games", "0")
                        games = int(str(games_str).replace(",", ""))
                        total_games += games
                        
                    if total_games > 0:
                        pick_rates[lane] = total_games
                        
            except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
                continue
                
        return pick_rates

    def _resolve_lane_conflicts_by_pick_rate(self, side_key, entries):
        """
        Resolve lane conflicts using pick rate data.
        Assigns lanes to champions based on highest pick rate first.
        """
        # Only process if any entry is missing assignedPosition
        if all(e.get("assignedPosition") for e in entries):
            return entries

        champion_pick_rates = []
        for i, entry in enumerate(entries):
            name = entry.get("canonical") or entry.get("display")
            rates = self._get_champion_lane_pick_rates(name)
            champion_pick_rates.append({
                "index": i,
                "entry": entry,
                "rates": rates
            })
            
        potential_assignments = []
        for item in champion_pick_rates:
            entry = item["entry"]
            current_pos = entry.get("assignedPosition")
            
            # If entry already has a valid position, treat it as a very high priority assignment
            if current_pos and current_pos.lower() in LANES:
                potential_assignments.append({
                    "count": 999999999,
                    "index": item["index"],
                    "lane": current_pos.lower()
                })
                continue

            rates = item["rates"]
            if not rates:
                continue
            for lane, count in rates.items():
                potential_assignments.append({
                    "count": count,
                    "index": item["index"],
                    "lane": lane
                })
                
        # Sort by count descending (greedy assignment)
        potential_assignments.sort(key=lambda x: x["count"], reverse=True)
        
        assigned_lanes = set()
        champion_assigned = set()
        
        for assign in potential_assignments:
            idx = assign["index"]
            lane = assign["lane"]
            
            if idx in champion_assigned:
                continue
            if lane in assigned_lanes:
                continue
                
            entries[idx]["assignedPosition"] = lane
            champion_assigned.add(idx)
            assigned_lanes.add(lane)
            
        return entries

    def _populate_side_from_client(self, side_key, entries):
        # Apply fallback logic for both allies and enemies if needed (e.g. custom games)
        entries = self._resolve_lane_conflicts_by_pick_rate(side_key, entries)

        slots = self.banpick_slots.get(side_key, [])
        if not slots:
            return False
        
        # Sort entries by lane if assignedPosition is available
        lane_priority = {
            'top': 0,
            'jungle': 1,
            'middle': 2,
            'bottom': 3,
            'utility': 4,
            'support': 4
        }
        
        def get_sort_key(entry):
            pos = entry.get("assignedPosition", "").lower()
            return lane_priority.get(pos, 99)

        # Only sort if at least one entry has a valid assigned position
        if any(entry.get("assignedPosition") for entry in entries):
            entries = sorted(entries, key=get_sort_key)

        changed = False
        for idx, slot in enumerate(slots):
            if idx < len(entries):
                changed |= self._populate_slot_from_client(slot, entries[idx])
            else:
                changed |= self._clear_slot_from_client(slot)
        return changed

    def _populate_slot_from_client(self, slot, entry):
        normalized = entry.get("normalized")
        canonical = entry.get("canonical")
        display = entry.get("display")
        is_local_player = entry.get("isLocalPlayer")
        
        if not canonical:
            return False
            
        slot_canonical = slot.get("canonical_name")
        
        # If this is the local player and my_lane_var is not set, set it to this slot's lane
        if is_local_player:
            if not self.my_lane_var.get():
                slot_lane = slot.get("lane")
                if slot_lane:
                    lane_value = slot_lane.get().lower()
                    if lane_value in LANES:
                        self.my_lane_var.set(lane_value)
        
        if slot_canonical and normalized and slot_canonical.lower() == normalized:
            slot["client_last_champion"] = normalized
            return False
        
        widget = slot.get("entry")
        if widget:
            widget.delete(0, tk.END)
            widget.insert(0, display)
        
        # LCU assignedPosition handling
        assigned_position = entry.get("assignedPosition")
        target_lane = None
        
        is_manual = slot.get("manual_var") and slot.get("manual_var").get()
        
        if assigned_position and not is_manual:
            assigned_position = assigned_position.lower()
            if assigned_position == "utility":
                assigned_position = "support"
            if assigned_position in LANES:
                target_lane = assigned_position
                lane_box = slot.get("lane")
                if lane_box:
                    current_lane = lane_box.get()
                    
                    # Check if target_lane is already used by another slot
                    side_key = slot.get("side")
                    conflicting_slot = None
                    
                    if side_key and target_lane != current_lane:
                        for other_slot in self.banpick_slots.get(side_key, []):
                            if other_slot is slot:
                                continue
                            other_lane = other_slot.get("lane")
                            if other_lane and other_lane.get() == target_lane:
                                # Found a conflict - check if the other slot is empty
                                other_entry = other_slot.get("entry")
                                if other_entry and not other_entry.get():
                                    # Other slot is empty, we can take this lane
                                    conflicting_slot = other_slot
                                    break
                    
                    # Set the lane for current slot
                    lane_box.set(target_lane)
                    self._update_slot_lane_cache(slot, target_lane)
                    
                    # If there was a conflicting empty slot, swap its lane
                    if conflicting_slot:
                        conflicting_lane_box = conflicting_slot.get("lane")
                        if conflicting_lane_box and current_lane:
                            conflicting_lane_box.set(current_lane)
                            self._update_slot_lane_cache(conflicting_slot, current_lane)
                        
                        # Swap exclude_var
                        slot_exclude = slot.get("exclude_var")
                        conflicting_exclude = conflicting_slot.get("exclude_var")
                        if slot_exclude and conflicting_exclude:
                            val1 = slot_exclude.get()
                            val2 = conflicting_exclude.get()
                            slot_exclude.set(val2)
                            conflicting_exclude.set(val1)
                        
                        # Swap manual_var (optional but good for consistency)
                        slot_manual = slot.get("manual_var")
                        conflicting_manual = conflicting_slot.get("manual_var")
                        if slot_manual and conflicting_manual:
                            val1 = slot_manual.get()
                            val2 = conflicting_manual.get()
                            slot_manual.set(val2)
                            conflicting_manual.set(val1)
                        
                        # Note: my_lane_var doesn't need to be swapped because it's lane-based, not slot-based

        success = self.perform_banpick_search(slot, auto_trigger=True, force_lane=target_lane)
        if success:
            slot["client_last_champion"] = normalized or (canonical.lower() if isinstance(canonical, str) else canonical)
        return success

    def _clear_slot_from_client(self, slot):
        if not slot.get("client_last_champion"):
            return False
        self.clear_banpick_slot(slot, reset_lane=False, suppress_update=True)
        slot["client_last_champion"] = None
        return True

    def _set_client_status(self, message):
        if hasattr(self, "client_status_var"):
            self.client_status_var.set(message)

    def _update_slot_lane_cache(self, slot, lane_value=None):
        if not slot:
            return
        lane_text = lane_value
        if lane_text is None:
            lane_widget = slot.get("lane")
            if lane_widget:
                lane_text = lane_widget.get()
        slot["last_lane_value"] = lane_text
        if isinstance(lane_text, str):
            lowered = lane_text.lower()
            slot["last_lane"] = lowered if lowered in LANES else None
        else:
            slot["last_lane"] = None

    def on_banpick_lane_changed(self, slot):
        if not slot or self._lane_swap_guard:
            return
        lane_box = slot.get("lane")
        if not lane_box:
            return
        new_value = lane_box.get()
        previous_value = slot.get("last_lane_value")
        if previous_value == new_value:
            return

        self._update_slot_lane_cache(slot, new_value)
        new_lane = slot.get("last_lane")
        if not new_lane:
            self.update_banpick_recommendations()
            return

        side_key = slot.get("side")
        if not side_key or side_key not in self.banpick_slots:
            self.update_banpick_recommendations()
            return

        swap_target = None
        for other in self.banpick_slots.get(side_key, []):
            if other is slot:
                continue
            other_box = other.get("lane")
            if not other_box:
                continue
            other_value = other_box.get()
            other_lane = other_value.lower() if isinstance(other_value, str) else ""
            if other_lane == new_lane:
                swap_target = other
                break

        if swap_target and previous_value is not None:
            swap_box = swap_target.get("lane")
            if swap_box:
                self._lane_swap_guard = True
                try:
                    swap_box.set(previous_value)
                finally:
                    self._lane_swap_guard = False
                self._update_slot_lane_cache(swap_target, previous_value)
            # Note: my_lane_var doesn't need to be swapped because it's lane-based, not slot-based

        self.update_banpick_recommendations()

    def clear_banpick_slot(self, slot, reset_lane=False, suppress_update=False):
        if not slot:
            return
        entry = slot.get("entry")
        lane_box = slot.get("lane")
        result_var = slot.get("result_var")
        if entry:
            entry.delete(0, tk.END)
        if reset_lane and lane_box:
            idx = slot.get("index", 0)
            if idx < len(BANPICK_DEFAULT_LANES):
                lane_box.set(BANPICK_DEFAULT_LANES[idx])
            else:
                lane_box.set("Select Lane")
            self._update_slot_lane_cache(slot)
        if result_var:
            result_var.set("검색 결과 없음")
        slot["display_name"] = None
        slot["canonical_name"] = None
        slot["selected_lane"] = None
        slot["synergy_dataset"] = None
        slot["counter_dataset"] = None
        
        # Reset exclude and manual checkbox
        exclude_var = slot.get("exclude_var")
        if exclude_var:
            exclude_var.set(False)
        manual_var = slot.get("manual_var")
        if manual_var:
            manual_var.set(False)
        
        if not suppress_update:
            self.update_banpick_recommendations()
            self.update_team_total_scores()
            # 모든 슬롯의 점수 표시 업데이트
            self._update_all_slot_scores()

    def get_autocomplete_candidates(self):
        return self.autocomplete_candidates

    def perform_banpick_search(self, slot, auto_trigger=False, force_lane=None):
        if not slot:
            return False
        entry_widget = slot.get("entry")
        lane_box = slot.get("lane")
        result_var = slot.get("result_var")
        if not entry_widget or not lane_box or not result_var:
            return False

        champion_name = entry_widget.get().strip()
        if not champion_name:
            if not auto_trigger:
                messagebox.showerror("Error", "챔피언 이름을 입력하세요.")
            return False

        lane = lane_box.get().lower()
        # "select lane" or empty string check
        is_lane_selected = lane in LANES

        if not is_lane_selected and not auto_trigger:
             # If manual search and no lane selected, show error
             messagebox.showerror("Error", "라인을 선택하세요.")
             return False

        full_name = self.resolve_champion_name(champion_name)
        if not full_name:
            autocomplete = slot.get("autocomplete")
            if autocomplete:
                unique_match = autocomplete.get_unique_match(champion_name)
                if unique_match:
                    entry_widget.delete(0, tk.END)
                    entry_widget.insert(0, unique_match)
                    entry_widget.icursor(tk.END)
                    champion_name = unique_match.strip()
                    full_name = self.resolve_champion_name(champion_name)
        if not full_name:
            if not auto_trigger:
                messagebox.showerror("Error", f"Champion name '{champion_name}' not found.")
            return False

        display_name = self.display_lookup.get(full_name, full_name.title())

        synergy_dataset = None
        counter_dataset = None
        
        is_manual = slot.get("manual_var") and slot.get("manual_var").get()
        if is_manual and auto_trigger:
            force_lane = lane

        
        # Determine best lane based on games count (only for auto-trigger AND if no lane selected)
        target_lane = lane
        if auto_trigger:
            if force_lane:
                target_lane = force_lane
            elif not is_lane_selected:
                # Only auto-detect lane if user hasn't selected one
                best_lane = self._find_best_lane_by_counters(full_name)
                if best_lane:
                    target_lane = best_lane
        
        # If we still don't have a valid target lane (e.g. manual trigger but invalid lane, though caught above),
        # or auto trigger failed to find best lane, ensure we have something valid or fallback
        if target_lane not in LANES:
             # Try to find best lane as fallback even if not auto_trigger, if the current selection is invalid
             best_lane = self._find_best_lane_by_counters(full_name)
             if best_lane:
                 target_lane = best_lane

        # Load datasets and capture the actual lane found
        synergy_dataset, synergy_lane, _ = self._load_lane_dataset(
            full_name,
            target_lane,
            "Synergy",
            "synergy",
            self.sanitize_synergy_entry,
            suppress_errors=True,
            apply_ignore_filter=False  # 슬롯 점수 계산에는 ignore filter 적용하지 않음
        )
        counter_dataset, counter_lane, _ = self._load_lane_dataset(
            full_name,
            target_lane,
            "Counter",
            "counters",
            self.sanitize_counter_entry,
            suppress_errors=True,
            apply_ignore_filter=False  # 슬롯 점수 계산에는 ignore filter 적용하지 않음
        )

        # Determine the final lane to use (prefer synergy lane if available, otherwise counter lane, or fallback to requested lane)
        final_lane = synergy_lane or counter_lane or lane

        # Lane Swap Logic
        if is_manual and auto_trigger:
            final_lane = lane  # Force final lane to current lane if manual

        current_lane_val = lane_box.get()
        current_lane = current_lane_val.lower() if current_lane_val else ""

        if final_lane != current_lane and final_lane in LANES:
            side_key = slot.get("side")
            swap_target = None
            if side_key:
                for other in self.banpick_slots.get(side_key, []):
                    if other is slot:
                        continue
                    other_val = other.get("lane").get()
                    other_l = other_val.lower() if other_val else ""
                    if other_l == final_lane:
                        swap_target = other
                        break
            
            # Update current slot
            lane_box.set(final_lane)
            self._update_slot_lane_cache(slot, final_lane)
            
            # Update swap target if found
            if swap_target:
                target_box = swap_target.get("lane")
                if target_box:
                    target_box.set(current_lane_val)
                    self._update_slot_lane_cache(swap_target, current_lane_val)
                
                # Swap active slot check if applicable
                current_active = self.active_slot_var.get()
                slot_key = f"{side_key}:{slot.get('index')}"
                target_key = f"{side_key}:{swap_target.get('index')}"
                
                if current_active == slot_key:
                    self.active_slot_var.set(target_key)
                elif current_active == target_key:
                    self.active_slot_var.set(slot_key)

        slot["display_name"] = display_name
        slot["canonical_name"] = full_name
        slot["selected_lane"] = final_lane
        slot["synergy_dataset"] = synergy_dataset
        slot["counter_dataset"] = counter_dataset
        
        # 모든 슬롯의 점수 재계산 (새 챔피언이 등록되면 다른 슬롯의 점수도 변경될 수 있음)
        self._update_all_slot_scores()

        if not auto_trigger:
            entry_widget.delete(0, tk.END)

        self.update_banpick_recommendations()
        self.update_team_total_scores()
        return True
    
    def _update_slot_score_display(self, slot):
        """슬롯의 점수를 계산하고 표시를 업데이트합니다"""
        result_var = slot.get("result_var")
        result_label = slot.get("result_label")
        if not result_var:
            return
        
        display_name = slot.get("display_name")
        selected_lane = slot.get("selected_lane")
        
        if not display_name or not selected_lane:
            result_var.set("검색 결과 없음")
            slot["score_details"] = None
            if result_label:
                # 테마에 맞는 텍스트 색상 사용
                fg_color = self.current_theme.get("fg_color", "#111111")
                result_label.config(fg=fg_color)
            return
        
        # 점수 계산 및 상세 정보 수집
        score, details = self.calculate_champion_score_with_details(slot)
        slot["score_details"] = details
        
        # 점수에 따른 이모지와 색상 결정
        if score > 102:
            emoji = "🟢"
            color = "#2E7D32"  # Green
        elif score >= 98:
            emoji = "🟡"
            color = "#F57F17"  # Yellow/Orange
        else:
            emoji = "🔴"
            color = "#C62828"  # Red
        
        result_var.set(f"{emoji} {display_name} ({selected_lane}) score: {score:.2f}")
        if result_label:
            result_label.config(fg=color)
    
    def _update_all_slot_scores(self):
        """모든 슬롯의 점수 표시를 업데이트합니다"""
        for side_key in ["allies", "enemies"]:
            for slot in self.banpick_slots.get(side_key, []):
                self._update_slot_score_display(slot)

    def _check_champion_data_exists(self, champion_name, lane):
        """
        Check if the data file for the champion and lane exists.
        """
        if not champion_name or not lane:
            return False
            
        full_name = self.resolve_champion_name(champion_name)
        if not full_name:
            return False
            
        data_filename = f"{full_name.lower()}_{lane.lower()}.json".replace(" ", "_")
        filename = resolve_resource_path("data", data_filename)
        return os.path.exists(filename)

    def calculate_champion_score(self, champion_slot, target_lane=None):
        score, _ = self.calculate_champion_score_with_details(champion_slot, target_lane)
        return score

    def calculate_champion_score_with_details(self, champion_slot, target_lane=None):
        """점수 계산과 상세 정보를 함께 반환합니다"""
        details = {
            "synergy_entries": [],  # [(champion_name, lane, win_rate, weight, weighted_score)]
            "counter_entries": [],  # [(champion_name, lane, win_rate, counter_score, weight, weighted_score)]
            "excluded_synergy": [], # [(champion_name, lane, games, pick_rate, win_rate)]
            "excluded_counter": [], # [(champion_name, lane, games, pick_rate, win_rate)]
            "synergy_score": 0.0,
            "counter_score": 0.0,
            "synergy_weight_sum": 0.0,
            "counter_weight_sum": 0.0,
            "total_score": 0.0
        }
        
        if not champion_slot.get("canonical_name") or not champion_slot.get("selected_lane"):
            return 0.0, details
        
        if champion_slot.get("exclude_var") and champion_slot["exclude_var"].get():
            return 0.0, details
        
        side_key = champion_slot.get("side")
        opponent_side = "enemies" if side_key == "allies" else "allies"
        champion_lane = target_lane if target_lane else champion_slot.get("selected_lane")
        slot_champion_canonical = champion_slot.get("canonical_name", "")
        
        if not self._check_champion_data_exists(champion_slot.get("canonical_name"), champion_lane):
            return 0.0, details
        
        synergy_sum = 0.0
        synergy_weight_sum = 0.0  # 가중치 합 (정규화용)
        counter_sum = 0.0
        counter_weight_sum = 0.0  # 가중치 합 (정규화용)
        
        min_games = self.parse_int(self.recommend_min_games_entry.get()) if hasattr(self, "recommend_min_games_entry") else BANPICK_MIN_GAMES_DEFAULT
        if min_games < 0:
            min_games = 0
        
        pick_rate_override = (
            self.parse_float(self.recommend_pick_rate_entry.get())
            if hasattr(self, "recommend_pick_rate_entry") else BANPICK_PICK_RATE_OVERRIDE
        )
        if pick_rate_override < 0:
            pick_rate_override = 0.0
        
        # 시너지 점수 계산 (같은 팀)
        for friend in self.banpick_slots.get(side_key, []):
            if friend is champion_slot:
                continue
            if friend.get("exclude_var") and friend["exclude_var"].get():
                continue
                
            source_lane = friend.get("selected_lane")
            friend_name = friend.get("display_name") or friend.get("canonical_name") or "Unknown"
            friend_canonical = friend.get("canonical_name")

            # 1. Look for ME in Friend's Dataset
            entry_a = None
            dataset_a = friend.get("synergy_dataset")
            if dataset_a:
                lane_entries = dataset_a.get(champion_lane, {})
                # Normalize lookup - loop or direct? Loop is safer for resolving names matches
                # But optimizing: Try resolve_champion_name match
                for name, data in lane_entries.items():
                    if self.resolve_champion_name(name) == slot_champion_canonical:
                        entry_a = data
                        break
            
            # 2. Look for Friend in MY Dataset
            entry_b = None
            dataset_b = champion_slot.get("synergy_dataset")
            if dataset_b and friend_canonical:
                lane_entries = dataset_b.get(source_lane, {})
                for name, data in lane_entries.items():
                    if self.resolve_champion_name(name) == friend_canonical:
                        entry_b = data
                        break
            
            # Select Best Entry
            # Criteria: Meets requirements? Higher games?
            selected_entry = None
            is_valid_a = False
            is_valid_b = False
            
            if entry_a:
                games_a = self.parse_int(entry_a.get("games"))
                pick_rate_a = self.parse_float(entry_a.get("pick_rate") or entry_a.get("popularity"))
                is_valid_a = (games_a >= min_games) or (pick_rate_a >= pick_rate_override)
            
            if entry_b:
                games_b = self.parse_int(entry_b.get("games"))
                pick_rate_b = self.parse_float(entry_b.get("pick_rate") or entry_b.get("popularity"))
                is_valid_b = (games_b >= min_games) or (pick_rate_b >= pick_rate_override)
            
            use_source = None # 'a' or 'b'
            if is_valid_a and is_valid_b:
                # Both valid, pick higher games
                use_source = 'a' if self.parse_int(entry_a.get("games")) >= self.parse_int(entry_b.get("games")) else 'b'
            elif is_valid_a:
                use_source = 'a'
            elif is_valid_b:
                use_source = 'b'
            elif entry_a: # Both invalid, but A exists (prefer A for consistency if both fail)
                use_source = 'a'
            elif entry_b:
                use_source = 'b'
            
            final_entry = None
            if use_source == 'a':
                final_entry = entry_a
            elif use_source == 'b':
                final_entry = entry_b
            
            if not final_entry:
                continue

            # Process Final Entry
            games = self.parse_int(final_entry.get("games"))
            pick_rate = self.parse_float(final_entry.get("pick_rate") or final_entry.get("popularity"))
            win_rate = self.parse_float(final_entry.get("win_rate"))
            
            # Check requirements again (for exclusion list)
            is_valid = (games >= min_games) or (pick_rate >= pick_rate_override)
            
            if not is_valid:
                details["excluded_synergy"].append((friend_name, source_lane, games, pick_rate, win_rate))
                continue

            weight = self.get_lane_weight(champion_lane, source_lane, "synergy")
            if weight <= 0:
                continue
            
            weighted_score = win_rate * weight
            synergy_sum += weighted_score
            synergy_weight_sum += weight
            details["synergy_entries"].append((friend_name, source_lane, win_rate, weight, weighted_score))

        # 카운터 점수 계산 (상대팀)
        for enemy in self.banpick_slots.get(opponent_side, []):
            if enemy.get("exclude_var") and enemy["exclude_var"].get():
                continue
            
            source_lane = enemy.get("selected_lane")
            enemy_name = enemy.get("display_name") or enemy.get("canonical_name") or "Unknown"
            enemy_canonical = enemy.get("canonical_name")

            # 1. Look for ME in Enemy's Dataset (Enemy vs Me)
            entry_a = None
            dataset_a = enemy.get("counter_dataset")
            if dataset_a:
                lane_entries = dataset_a.get(champion_lane, {})
                for name, data in lane_entries.items():
                    if self.resolve_champion_name(name) == slot_champion_canonical:
                        entry_a = data
                        break

            # 2. Look for Enemy in MY Dataset (Me vs Enemy)
            entry_b = None
            dataset_b = champion_slot.get("counter_dataset")
            if dataset_b and enemy_canonical:
                lane_entries = dataset_b.get(source_lane, {})
                for name, data in lane_entries.items():
                    if self.resolve_champion_name(name) == enemy_canonical:
                        entry_b = data
                        break

            # Select Best
            selected_entry = None
            is_valid_a = False
            is_valid_b = False
            
            if entry_a:
                games_a = self.parse_int(entry_a.get("games"))
                pick_rate_a = self.parse_float(entry_a.get("pick_rate") or entry_a.get("popularity"))
                is_valid_a = (games_a >= min_games) or (pick_rate_a >= pick_rate_override)
            
            if entry_b:
                games_b = self.parse_int(entry_b.get("games"))
                pick_rate_b = self.parse_float(entry_b.get("pick_rate") or entry_b.get("popularity"))
                is_valid_b = (games_b >= min_games) or (pick_rate_b >= pick_rate_override)
            
            use_source = None
            if is_valid_a and is_valid_b:
                use_source = 'a' if self.parse_int(entry_a.get("games")) >= self.parse_int(entry_b.get("games")) else 'b'
            elif is_valid_a:
                use_source = 'a'
            elif is_valid_b:
                use_source = 'b'
            elif entry_a:
                use_source = 'a'
            elif entry_b:
                use_source = 'b'
            
            final_entry = None
            is_inverted = False # True if using 'a' (Enemy vs Me), False if 'b' (Me vs Enemy)
            
            if use_source == 'a':
                final_entry = entry_a
                is_inverted = True # entry from enemy perspective
            elif use_source == 'b':
                final_entry = entry_b
                is_inverted = False # entry from my perspective
            
            if not final_entry:
                continue
                
            games = self.parse_int(final_entry.get("games"))
            pick_rate = self.parse_float(final_entry.get("pick_rate") or final_entry.get("popularity"))
            win_rate_raw = self.parse_float(final_entry.get("win_rate"))
            
            # Counter logic: If inverted (Enemy vs Me), My Win Rate = 100 - EnemyWinRate
            # If not inverted (Me vs Enemy), My Win Rate = Raw WinRate
            # Wait. "Counter Score" usually wants "How much do I counter them?".
            # If win_rate_raw is "Me vs Enemy" (e.g. 52%), then Counter Value is usually defined as (WinRate - 50)?
            # Or in this app: `100 - win_rate_value` (line 2312 of original) was used when source was Enemy (Enemy vs Me).
            # If Enemy vs Me is 48% -> My Win Rate is 52%. Score is 52.
            # So: if is_inverted (Enemy's data), Score = 100 - win_rate_raw.
            #     if not inverted (My data), Score = win_rate_raw.
            
            if is_inverted:
                my_win_rate = 100.0 - win_rate_raw
            else:
                my_win_rate = win_rate_raw

            is_valid = (games >= min_games) or (pick_rate >= pick_rate_override)
            
            if not is_valid:
                # For display, we might want to show the 'my_win_rate' equivalent
                details["excluded_counter"].append((enemy_name, source_lane, games, pick_rate, my_win_rate))
                continue
            
            weight = self.get_lane_weight(champion_lane, source_lane, "counter")
            if weight <= 0:
                continue
                
            # Counter Score Logic:
            # Often apps measure "Counter" as "Advantage". 
            # If My Win Rate is 55%, advantage is +5%.
            # The original code did `weighted_score = counter_value * weight` where counter_value = 100 - enemy_win_rate.
            # So it's just My Win Rate.
            
            weighted_score = my_win_rate * weight
            counter_sum += weighted_score
            counter_weight_sum += weight
            details["counter_entries"].append((enemy_name, source_lane, win_rate_raw, my_win_rate, weight, weighted_score))
        
        # 가중치 합으로 나눠서 정규화 (라인 간 비교 가능하게)
        synergy_score = synergy_sum / synergy_weight_sum if synergy_weight_sum > 0 else 0.0
        counter_score = counter_sum / counter_weight_sum if counter_weight_sum > 0 else 0.0
        total_score = synergy_score + counter_score
        
        details["synergy_score"] = synergy_score
        details["counter_score"] = counter_score
        details["synergy_weight_sum"] = synergy_weight_sum
        details["counter_weight_sum"] = counter_weight_sum
        details["total_score"] = total_score
        
        return total_score, details
    
    def _get_score_tooltip_text(self, slot):
        """슬롯의 점수 상세 정보를 툴팁 텍스트로 포맷팅합니다"""
        details = slot.get("score_details")
        if not details:
            return None
        
        display_name = slot.get("display_name", "Unknown")
        selected_lane = slot.get("selected_lane", "?")
        
        lines = []
        lines.append(f"=== {display_name} ({selected_lane}) 점수 상세 ===")
        lines.append("")
        
        # 시너지 정보
        synergy_entries = details.get("synergy_entries", [])
        synergy_weight_sum = details.get("synergy_weight_sum", 0.0)
        if synergy_entries:
            lines.append("[ 시너지 ]")
            for name, lane, win_rate, weight, weighted in synergy_entries:
                lines.append(f"  {name}({lane}): {win_rate:.1f}% × {weight:.1f} = {weighted:.1f}")
            synergy_sum = sum(w for _, _, _, _, w in synergy_entries)
            lines.append(f"  합계: {synergy_sum:.1f} / 가중치합: {synergy_weight_sum:.1f}")
            lines.append(f"  → 시너지 점수: {details['synergy_score']:.2f}")
            lines.append("")
        
        # 카운터 정보
        counter_entries = details.get("counter_entries", [])
        counter_weight_sum = details.get("counter_weight_sum", 0.0)
        if counter_entries:
            lines.append("[ 카운터 ]")
            for name, lane, win_rate, counter_val, weight, weighted in counter_entries:
                lines.append(f"  {name}({lane}): 100-{win_rate:.1f}={counter_val:.1f} × {weight:.1f} = {weighted:.1f}")
            counter_sum = sum(w for _, _, _, _, _, w in counter_entries)
            lines.append(f"  합계: {counter_sum:.1f} / 가중치합: {counter_weight_sum:.1f}")
            lines.append(f"  → 카운터 점수: {details['counter_score']:.2f}")
            lines.append("")
            
        # 제외된 정보 표시
        excluded_synergy = details.get("excluded_synergy", [])
        excluded_counter = details.get("excluded_counter", [])
        
        if excluded_synergy or excluded_counter:
            lines.append("[ 제외됨(데이터 부족) ]")
            if excluded_synergy:
                lines.append("  <시너지 제외>")
                for name, lane, games, pick_rate, win_rate in excluded_synergy:
                    lines.append(f"    - {name}({lane}): {games}판 / 픽률 {pick_rate:.1f}% (승률 {win_rate:.1f}%)")
            
            if excluded_counter:
                lines.append("  <카운터 제외>")
                for name, lane, games, pick_rate, win_rate in excluded_counter:
                    lines.append(f"    - {name}({lane}): {games}판 / 픽률 {pick_rate:.1f}% (상대승률 {win_rate:.1f}%)")
            lines.append("")
        
        if not synergy_entries and not counter_entries and not excluded_synergy and not excluded_counter:
            lines.append("(데이터 없음)")
            lines.append("")
        
        lines.append(f"총점: {details['synergy_score']:.2f} + {details['counter_score']:.2f} = {details['total_score']:.2f}")
        
        return "\n".join(lines)

    def update_team_total_scores(self):
        """우리팀과 상대팀의 총 조합 점수를 업데이트합니다"""
        if not hasattr(self, "team_total_labels"):
            return
        
        allies_total = 0.0
        allies_count = 0
        enemies_total = 0.0
        enemies_count = 0
        
        # 각 챔피언의 슬롯에 표시된 점수를 그대로 사용
        for slot in self.banpick_slots.get("allies", []):
            if slot.get("canonical_name") and slot.get("selected_lane"):
                score = self.calculate_champion_score(slot)
                if score > 0:
                    allies_total += score
                    allies_count += 1
        
        for slot in self.banpick_slots.get("enemies", []):
            if slot.get("canonical_name") and slot.get("selected_lane"):
                score = self.calculate_champion_score(slot)
                if score > 0:
                    enemies_total += score
                    enemies_count += 1
        
        # 점수 계산
        allies_avg = allies_total / allies_count if allies_count > 0 else 0.0
        enemies_avg = enemies_total / enemies_count if enemies_count > 0 else 0.0
        
        # 예상 승률 계산: 50% + (우리팀 점수 - 상대팀 점수) / 2
        # 범위 제한: 5% ~ 95%
        if allies_avg > 0 and enemies_avg > 0:
            allies_win_rate = 50 + (allies_avg - enemies_avg) / 2
            allies_win_rate = max(5, min(95, allies_win_rate))  # 5~95% 범위 제한
            enemies_win_rate = 100 - allies_win_rate
        else:
            allies_win_rate = None
            enemies_win_rate = None
        
        def get_score_style(score):
            t = self.current_theme
            if score > 102:
                return "🟢", t.get("score_high", "#2E7D32")  # Green
            elif score >= 98:
                return "🟡", t.get("score_medium", "#F57F17")  # Yellow/Orange
            else:
                return "🔴", t.get("score_low", "#C62828")  # Red
        
        allies_label = self.team_total_labels.get("allies")
        enemies_label = self.team_total_labels.get("enemies")
        
        if allies_label:
            if allies_avg > 0:
                emoji, color = get_score_style(allies_avg)
                if allies_win_rate is not None:
                    allies_label.config(text=f"{emoji} 조합 점수: {allies_avg:.2f} (승률 {allies_win_rate:.1f}%)", fg=color)
                else:
                    allies_label.config(text=f"{emoji} 조합 점수: {allies_avg:.2f}", fg=color)
            else:
                default_color = self.current_theme.get("score_default", "blue")
                allies_label.config(text="조합 점수: 0.00", fg=default_color)
        if enemies_label:
            if enemies_avg > 0:
                emoji, color = get_score_style(enemies_avg)
                if enemies_win_rate is not None:
                    enemies_label.config(text=f"{emoji} 조합 점수: {enemies_avg:.2f} (승률 {enemies_win_rate:.1f}%)", fg=color)
                else:
                    enemies_label.config(text=f"{emoji} 조합 점수: {enemies_avg:.2f}", fg=color)
            else:
                default_color = self.current_theme.get("score_default", "blue")
                enemies_label.config(text="조합 점수: 0.00", fg=default_color)

    def update_banpick_recommendations(self):
        tree = getattr(self, "recommend_tree", None)
        if not tree:
            return
        for item in tree.get_children():
            tree.delete(item)

        my_lane = self.my_lane_var.get()
        if not my_lane or my_lane not in LANES:
            return

        # Find the slot in allies team that matches my lane
        target_slot = None
        for slot in self.banpick_slots.get("allies", []):
            slot_lane = slot.get("lane")
            if slot_lane and slot_lane.get().lower() == my_lane:
                target_slot = slot
                break
        
        if not target_slot:
            return
        
        # My lane is always in the allies team
        side_key = "allies"
        target_lane = my_lane

        scores = {}
        pick_rate_override = (
            self.parse_float(self.recommend_pick_rate_entry.get())
            if hasattr(self, "recommend_pick_rate_entry") else BANPICK_PICK_RATE_OVERRIDE
        )
        if pick_rate_override < 0:
            pick_rate_override = 0.0

        def ensure_score_entry(champion):
            entry = scores.get(champion)
            if entry is None:
                entry = {
                    "synergy_sum": 0.0,
                    "synergy_weight_sum": 0.0,  # 가중치 합 (정규화용)
                    "counter_sum": 0.0,
                    "counter_weight_sum": 0.0,  # 가중치 합 (정규화용)
                    "synergy_sources": [],
                    "counter_sources": [],
                    "has_low_sample": False,
                    "has_low_pick_gap": False, # deprecated but kept for compatibility
                    "tags": [],
                    "all_high_sample": True,
                    "all_counter_under_50": True,
                    "has_op_synergy": False,
                    "synergy_slots_with_data": set(),  # 데이터가 있는 아군 슬롯 인덱스
                    "counter_slots_with_data": set()   # 데이터가 있는 적군 슬롯 인덱스
                }
                scores[champion] = entry
            return entry

        def append_tag(components, label):
            if label and label not in components["tags"]:
                components["tags"].append(label)

        def should_use_entry(details):
            games = self.parse_int(details.get("games"))
            pick_rate_value = 0.0
            if "pick_rate" in details:
                pick_rate_value = self.parse_float(details.get("pick_rate"))
            elif "popularity" in details:
                pick_rate_value = self.parse_float(details.get("popularity"))
            meets_games_requirement = games >= min_games
            meets_pick_rate_override = pick_rate_value >= pick_rate_override
            include_entry = meets_games_requirement or meets_pick_rate_override
            low_sample = not meets_games_requirement
            # penalized_pick = (not include_entry) and (not meets_pick_rate_override) # No longer used to exclude
            high_sample = games >= BANPICK_HIGH_SAMPLE_THRESHOLD
            return include_entry, low_sample, high_sample, games, pick_rate_value

        selected_lowers = set()
        for slot_list in self.banpick_slots.values():
            for s in slot_list:
                # 내 라인(target_slot)에 있는 챔피언은 제외 목록에 넣지 않음
                if s is target_slot:
                    continue

                name = s.get("display_name")
                canon = s.get("canonical_name")
                if name:
                    selected_lowers.add(name.lower())
                if canon:
                    selected_lowers.add(canon.lower())

        min_games = self.parse_int(self.recommend_min_games_entry.get()) if hasattr(self, "recommend_min_games_entry") else BANPICK_MIN_GAMES_DEFAULT
        if min_games < 0:
            min_games = 0

        # Synergy contributions from same side
        for friend_idx, friend in enumerate(self.banpick_slots.get(side_key, [])):
            if friend.get("exclude_var") and friend["exclude_var"].get():
                continue
            dataset = friend.get("synergy_dataset")
            if not dataset:
                continue
            source_lane = friend.get("selected_lane")
            lane_entries = dataset.get(target_lane, {})
            for champ_name, details in lane_entries.items():
                include_entry, low_sample, high_sample, games, pick_rate_val = should_use_entry(details)
                
                source_name = friend.get("display_name") or friend.get("canonical_name") or "Unknown"
                
                if not include_entry:
                    # 데이터 부족으로 제외됨 -> 점수 합산 X, 소스에만 표시
                    components = ensure_score_entry(champ_name)
                    label = f"{source_name}(제외: {games}판, {pick_rate_val:.1f}%)"
                    components["synergy_sources"].append(label)
                    continue

                value = self.parse_float(details.get("win_rate"))
                weight = self.get_lane_weight(target_lane, source_lane, "synergy")
                if weight <= 0:
                    continue
                components = ensure_score_entry(champ_name)
                components["synergy_sum"] += value * weight
                components["synergy_weight_sum"] += weight  # 가중치 합산
                components["synergy_slots_with_data"].add(friend_idx)  # 데이터가 있는 슬롯 추적
                if low_sample:
                    components["has_low_sample"] = True
                    append_tag(components, RECOMMEND_LOW_SAMPLE_TAG)
                if not high_sample:
                    components["all_high_sample"] = False
                if value >= SYNERGY_OP_THRESHOLD:
                    components["has_op_synergy"] = True
                
                label = f"{source_name}({value:.2f})"
                if low_sample:
                    label = f"{WARNING_ICON} {label}"
                components["synergy_sources"].append(label)

        # Counter contributions from opposing side
        opponent_side = "enemies" if side_key == "allies" else "allies"
        for enemy_idx, enemy in enumerate(self.banpick_slots.get(opponent_side, [])):
            is_excluded = enemy.get("exclude_var") and enemy["exclude_var"].get()
            if is_excluded:
                continue
            dataset = enemy.get("counter_dataset")
            if not dataset:
                continue
            source_lane = enemy.get("selected_lane")
            lane_entries = dataset.get(target_lane, {})
            for champ_name, details in lane_entries.items():
                include_entry, low_sample, high_sample, games, pick_rate_val = should_use_entry(details)
                
                source_name = enemy.get("display_name") or enemy.get("canonical_name") or "Unknown"

                if not include_entry:
                     # 데이터 부족으로 제외됨 -> 점수 합산 X, 소스에만 표시
                    components = ensure_score_entry(champ_name)
                    label = f"{source_name}(제외: {games}판, {pick_rate_val:.1f}%)"
                    components["counter_sources"].append(label)
                    continue

                win_rate_value = self.parse_float(details.get("win_rate"))
                value = 100.0 - win_rate_value
                weight = self.get_lane_weight(target_lane, source_lane, "counter")
                if weight <= 0:
                    continue
                components = ensure_score_entry(champ_name)
                components["counter_sum"] += value * weight
                components["counter_weight_sum"] += weight  # 가중치 합산
                components["counter_slots_with_data"].add(enemy_idx)  # 데이터가 있는 슬롯 추적
                if low_sample:
                    components["has_low_sample"] = True
                    append_tag(components, RECOMMEND_LOW_SAMPLE_TAG)
                if not high_sample:
                    components["all_high_sample"] = False
                if win_rate_value >= 50.0:
                    components["all_counter_under_50"] = False
                
                label = f"{source_name}({win_rate_value:.2f})"
                if low_sample:
                    label = f"{WARNING_ICON} {label}"
                components["counter_sources"].append(label)

        # 평균 회귀: 데이터가 없는 슬롯에 대해 중립 점수(50점) 추가
        # 등록되고 제외되지 않은 슬롯 목록 수집
        active_friend_slots = []  # (slot_idx, source_lane)
        for friend_idx, friend in enumerate(self.banpick_slots.get(side_key, [])):
            if friend is target_slot:  # 내 슬롯은 제외
                continue
            if friend.get("exclude_var") and friend["exclude_var"].get():
                continue
            if friend.get("synergy_dataset") and friend.get("selected_lane"):
                active_friend_slots.append((friend_idx, friend.get("selected_lane")))
        
        active_enemy_slots = []  # (slot_idx, source_lane)
        for enemy_idx, enemy in enumerate(self.banpick_slots.get(opponent_side, [])):
            if enemy.get("exclude_var") and enemy["exclude_var"].get():
                continue
            if enemy.get("counter_dataset") and enemy.get("selected_lane"):
                active_enemy_slots.append((enemy_idx, enemy.get("selected_lane")))
        
        # 각 추천 챔피언에 대해 누락된 슬롯의 중립 점수 추가
        NEUTRAL_SCORE = 50.0
        for champ_name, components in scores.items():
            # 시너지: 데이터가 없는 아군 슬롯에 대해 50점 추가
            for friend_idx, source_lane in active_friend_slots:
                if friend_idx not in components["synergy_slots_with_data"]:
                    weight = self.get_lane_weight(target_lane, source_lane, "synergy")
                    if weight > 0:
                        components["synergy_sum"] += NEUTRAL_SCORE * weight
                        components["synergy_weight_sum"] += weight  # 가중치 합산
            
            # 카운터: 데이터가 없는 적군 슬롯에 대해 50점 추가
            for enemy_idx, source_lane in active_enemy_slots:
                if enemy_idx not in components["counter_slots_with_data"]:
                    weight = self.get_lane_weight(target_lane, source_lane, "counter")
                    if weight > 0:
                        components["counter_sum"] += NEUTRAL_SCORE * weight
                        components["counter_weight_sum"] += weight  # 가중치 합산

        recommendations = []

        for champ_name, components in scores.items():
            if champ_name.lower() in selected_lowers:
                continue
            if self.is_champion_ignored(champ_name):
                continue
            if components["has_low_pick_gap"]:
                continue
            
            # 데이터 파일 존재 여부 확인 (추천 목록에서도 제외)
            if not self._check_champion_data_exists(champ_name, target_lane):
                continue

            # 가중치 합으로 나눠서 정규화 (라인 간 비교 가능하게)
            synergy_score = (
                components["synergy_sum"] / components["synergy_weight_sum"]
                if components["synergy_weight_sum"] > 0 else 0.0
            )
            counter_score = (
                components["counter_sum"] / components["counter_weight_sum"]
                if components["counter_weight_sum"] > 0 else 0.0
            )
            total = synergy_score + counter_score
            if total == 0:
                continue
            if components["counter_weight_sum"] > 0 and components["all_counter_under_50"]:
                append_tag(components, RECOMMEND_FULL_COUNTER_TAG)
            if components["all_high_sample"] and (components["synergy_weight_sum"] > 0 or components["counter_weight_sum"] > 0):
                append_tag(components, RECOMMEND_HIGH_SAMPLE_TAG)
            if components["has_op_synergy"]:
                append_tag(components, RECOMMEND_OP_SYNERGY_TAG)
            if self._qualifies_for_pre_pick_tag(champ_name, target_lane):
                append_tag(components, RECOMMEND_PRE_PICK_TAG)
            recommendations.append((
                champ_name,
                total,
                synergy_score,
                counter_score,
                components["synergy_sources"],
                components["counter_sources"],
                components["has_low_sample"],
                list(components["tags"])
            ))

        recommendations.sort(key=lambda item: item[1], reverse=True)
        for champ_name, total, synergy_score, counter_score, synergy_sources, counter_sources, has_low_sample, tags in recommendations[:20]:
            display_name = f"{WARNING_ICON} {champ_name}" if has_low_sample else champ_name
            synergy_label = " / ".join(synergy_sources) if synergy_sources else "-"
            counter_label = " / ".join(counter_sources) if counter_sources else "-"
            tag_label = ", ".join(tags) if tags else "-"
            tree.insert(
                "",
                "end",
                values=(
                    display_name,
                    tag_label,
                    f"{total:.2f}",
                    synergy_label,
                    counter_label
                )
            )
        
        # 총 조합 점수 업데이트
        self.update_team_total_scores()
        # 모든 슬롯의 점수 표시 업데이트
        self._update_all_slot_scores()

    def _resolve_canonical_for_dataset(self, champion_name: str | None) -> str | None:
        if not champion_name:
            return None
        stripped = str(champion_name).strip()
        if not stripped:
            return None
        lowered = stripped.lower()
        canonical = self.canonical_lookup.get(lowered)
        if canonical:
            return canonical
        resolved = self.resolve_champion_name(stripped)
        if resolved:
            return resolved
        return stripped

    def _get_recommend_counter_dataset(self, canonical_name: str, lane: str):
        if not canonical_name or lane not in LANES:
            return None
        cache_key = (canonical_name, lane)
        if cache_key in self.recommend_counter_cache:
            return self.recommend_counter_cache[cache_key]
        dataset, _resolved_lane, _ = self._load_lane_dataset(
            canonical_name,
            lane,
            "Counter",
            "counters",
            self.sanitize_counter_entry,
            suppress_errors=True,
            apply_ignore_filter=False
        )
        self.recommend_counter_cache[cache_key] = dataset
        return dataset

    def _qualifies_for_pre_pick_tag(self, champion_name: str, lane: str) -> bool:
        if lane not in LANES:
            return False
        canonical = self._resolve_canonical_for_dataset(champion_name)
        if not canonical:
            return False
        dataset = self._get_recommend_counter_dataset(canonical, lane)
        if not dataset:
            return False
        lane_entries = dataset.get(lane, {})
        if not lane_entries:
            return False
        for details in lane_entries.values():
            popularity = self.parse_float(details.get("popularity"))
            if popularity <= BANPICK_PRE_PICK_POPULARITY_THRESHOLD:
                continue
            win_rate = self.parse_float(details.get("win_rate"))
            if win_rate < 50.0:
                return False
        return True

    def get_lane_weight(self, target_lane, source_lane, weight_type="counter"):
        """
        라인 가중치를 반환합니다.
        weight_type: "synergy" 또는 "counter"
        저장된 값이 있으면 그것을 사용하고, 없으면 weight_settings.json의 기본값을 사용합니다.
        """
        if not target_lane or not source_lane:
            from weight_settings_tab import LANE_WEIGHT_DEFAULT
            return LANE_WEIGHT_DEFAULT
        
        # 저장된 가중치 확인 (사용자가 수정한 값)
        weight_settings_ui = self.ui_settings.get("lane_weights", {})
        lane_settings = weight_settings_ui.get(target_lane, {})
        type_settings = lane_settings.get(weight_type, {})
        
        saved_weight = type_settings.get(source_lane)
        if saved_weight is not None:
            return float(saved_weight)
        
        # 기본값 사용 (weight_settings.json에서)
        from weight_settings_tab import LANE_WEIGHT_DEFAULT
        weight_settings = load_weight_settings()
        weight_type_settings = weight_settings.get(weight_type, {})
        lane_weight_map = weight_type_settings.get("lane_weight_map", {})
        mapping = lane_weight_map.get(target_lane, {})
        return mapping.get(source_lane, LANE_WEIGHT_DEFAULT)
    

    def _parse_threshold_value(self, entry_widget, default_value):
        if not entry_widget:
            return default_value
        value = entry_widget.get().strip()
        if not value:
            return default_value
        try:
            parsed = int(value)
        except ValueError:
            return default_value
        return parsed if parsed >= 0 else default_value

    def _find_best_lane_by_counters(self, full_name):
        best_lane = None
        max_games = -1

        for lane in LANES:
            data_filename = f"{full_name}_{lane}.json".replace(" ", "_")
            filename = resolve_resource_path("data", data_filename)
            if not os.path.exists(filename):
                continue
            
            try:
                with open(filename, "r", encoding="utf-8") as file:
                    raw_data = json.load(file)
            except (OSError, json.JSONDecodeError):
                continue

            counters_data = raw_data.get("counters")
            if not isinstance(counters_data, dict):
                continue

            total_games = 0
            for sub_lane_data in counters_data.values():
                if not isinstance(sub_lane_data, dict):
                    continue
                for entry in sub_lane_data.values():
                    if isinstance(entry, dict):
                        total_games += self.parse_int(entry.get("games"))
            
            if total_games > max_games:
                max_games = total_games
                best_lane = lane
        
        return best_lane

    def _load_lane_dataset(
        self,
        full_name,
        preferred_lane,
        data_label,
        data_key,
        sanitize_entry,
        suppress_errors=False,
        apply_ignore_filter=False  # 기본값 False: 점수 계산에는 ignore list 적용 안 함
    ):
        if preferred_lane in LANES:
            lanes_to_try = [preferred_lane]
        else:
            lanes_to_try = [preferred_lane] + [lane for lane in LANES if lane != preferred_lane]
        best_candidate = None

        for lane_candidate in lanes_to_try:
            data_filename = f"{full_name}_{lane_candidate}.json".replace(" ", "_")
            filename = resolve_resource_path("data", data_filename)
            try:
                with open(filename, "r", encoding="utf-8") as file:
                    raw_data = json.load(file)
            except FileNotFoundError:
                continue
            except json.JSONDecodeError as e:
                if not suppress_errors:
                    messagebox.showerror(
                        "Error",
                        f"{data_label} 데이터 파일 '{data_filename}'을 읽을 수 없습니다.\n에러: {e}"
                    )
                return None, None, False
            except OSError as e:
                if not suppress_errors:
                    messagebox.showerror(
                        "Error",
                        f"{data_label} 데이터 파일 '{data_filename}'을 여는 중 오류가 발생했습니다.\n경로: {filename}\n에러: {e}"
                    )
                return None, None, False

            payload = raw_data.get(data_key)
            if payload is None and data_key == "counters":
                payload = raw_data
            if not isinstance(payload, dict):
                continue

            sanitized_dataset = {ln: {} for ln in LANES}
            for lane_name in LANES:
                lane_payload = payload.get(lane_name, {})
                if not isinstance(lane_payload, dict):
                    continue
                for name, entry in lane_payload.items():
                    if not isinstance(entry, dict):
                        continue
                    sanitized_dataset[lane_name][name] = sanitize_entry(entry)

            if apply_ignore_filter:
                self._apply_ignore_filter(sanitized_dataset)
            has_entries = any(sanitized_dataset[lane] for lane in LANES)
            if not has_entries:
                continue

            if lane_candidate == preferred_lane:
                return sanitized_dataset, lane_candidate, False

            total_games = sum(
                self.parse_int(details.get("games"))
                for lane_data in sanitized_dataset.values()
                for details in lane_data.values()
            )
            if best_candidate is None or total_games > best_candidate["games"]:
                best_candidate = {
                    "dataset": sanitized_dataset,
                    "lane": lane_candidate,
                    "games": total_games
                }

        if best_candidate:
            return best_candidate["dataset"], best_candidate["lane"], best_candidate["lane"] != preferred_lane

        return None, None, False

    def reset_main_tab(self):
        # Delegate to CounterSynergyTab if needed, but it was already removed from here.
        if self.counter_synergy_tab:
            self.counter_synergy_tab.reset_main_tab()

    def reset_dashboard_tab(self):
        self.reset_banpick_slots()
        self.recommend_min_games_entry.delete(0, tk.END)
        self.recommend_min_games_entry.insert(0, str(BANPICK_MIN_GAMES_DEFAULT))
        self.update_banpick_recommendations()

    def reset_banpick_slots(self):
        if not hasattr(self, "banpick_slots"):
            return
        for _side_key, slots in self.banpick_slots.items():
            for slot in slots:
                self.clear_banpick_slot(slot, reset_lane=True, suppress_update=True)
        # my_lane_var should NOT be reset - it persists across dashboard resets
        self.update_banpick_recommendations()

    def format_display_name(self, slug: str) -> str:
        key = slug.lower().replace("_", "")
        display = self.display_lookup.get(key)
        if display:
            return display
        return slug.replace("_", " ").title()

    def resolve_champion_name(self, query: str):
        allow_initials = not contains_hangul_syllable(query or "")
        variants = alias_variants(query, include_initials=allow_initials)
        variants.add(query.lower().strip())

        for variant in variants:
            if variant in self.alias_lookup:
                return self.alias_lookup[variant]

        lowered_query = query.lower().strip()
        for normalized, canonical in self.canonical_lookup.items():
            if lowered_query and lowered_query in normalized:
                return canonical
        return None
    
    def sanitize_counter_entry(self, entry):
        sanitized = entry.copy()
        sanitized["games"] = f"{self.parse_int(entry.get('games'))}"
        sanitized["popularity"] = f"{self.parse_float(entry.get('popularity')):.2f}"
        sanitized["win_rate"] = f"{self.parse_float(entry.get('win_rate')):.2f}"
        sanitized["win_rate_diff"] = f"{self.parse_float(entry.get('win_rate_diff')):.2f}"
        return sanitized

    def sanitize_synergy_entry(self, entry):
        sanitized = entry.copy()
        sanitized["games"] = f"{self.parse_int(entry.get('games'))}"
        sanitized["pick_rate"] = f"{self.parse_float(entry.get('pick_rate')):.2f}"
        sanitized["win_rate"] = f"{self.parse_float(entry.get('win_rate')):.2f}"
        return sanitized

    def _initialize_ignored_champions(self) -> set[str]:
        stored_names = load_ignored_champion_names()
        normalized = set()
        for name in stored_names:
            lowered = name.lower().strip()
            if not lowered:
                continue
            canonical = self.canonical_lookup.get(lowered, name)
            normalized.add(canonical.lower())
        return normalized

    def _apply_ignore_filter(self, dataset):
        if not dataset or not self.ignored_champions:
            return
        for lane, champions in dataset.items():
            if not isinstance(champions, dict):
                continue
            for champ_name in list(champions.keys()):
                if self.is_champion_ignored(champ_name):
                    champions.pop(champ_name, None)

    def is_champion_ignored(self, name: str) -> bool:
        if not name or not self.ignored_champions:
            return False
        lowered = str(name).strip().lower()
        if lowered in self.ignored_champions:
            return True
        canonical = self.canonical_lookup.get(lowered)
        if canonical and canonical.lower() in self.ignored_champions:
            return True
        resolved = self.resolve_champion_name(name)
        if resolved and resolved.lower() in self.ignored_champions:
            return True
        return False

    @staticmethod
    def parse_int(value):
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            value = value.replace(",", "").strip()
            if not value:
                return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def parse_float(value):
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            value = value.replace(",", "").strip()
            if not value:
                return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    
    def toggle_theme(self):
        """다크모드/라이트모드 전환"""
        if self.current_theme["name"] == "dark":
            new_theme = THEME_LIGHT
        else:
            new_theme = THEME_DARK
        
        # 테마 적용
        self.apply_theme(new_theme)
        
        # 설정 저장
        self.ui_settings["theme"] = new_theme["name"]
        self._save_ui_settings()
        
        # 모든 위젯 색상 갱신
        self._refresh_all_widgets()
        
        # 조합 점수 및 추천 목록 색상 갱신
        self.update_team_total_scores()
        
        # 각 슬롯의 챔피언 점수 색상 재적용 (이모지 및 색상)
        self._update_all_slot_scores()
    
    def _refresh_all_widgets(self):
        """테마 변경 후 모든 위젯 색상을 갱신합니다."""
        t = self.current_theme
        bg_color = t["bg_color"]
        fg_color = t["fg_color"]
        entry_bg = t["entry_bg"]
        entry_fg = t["entry_fg"]
        button_color = t["button_color"]
        button_fg = t["button_fg"]
        accent_color = t["accent_color"]
        
        def refresh_widget(widget):
            """재귀적으로 위젯 색상을 갱신합니다."""
            widget_class = widget.winfo_class()
            
            try:
                if widget_class == "Labelframe":
                    widget.configure(bg=bg_color, fg=fg_color)
                elif widget_class in ("Frame", "Toplevel"):
                    widget.configure(bg=bg_color)
                elif widget_class == "Label":
                    widget.configure(bg=bg_color, fg=fg_color)
                elif widget_class == "Button":
                    widget.configure(bg=button_color, fg=button_fg, activebackground=t["button_active_bg"])
                elif widget_class == "Entry":
                    widget.configure(bg=entry_bg, fg=entry_fg, insertbackground=entry_fg)
                elif widget_class == "Listbox":
                    widget.configure(bg=entry_bg, fg=entry_fg, selectbackground=t["select_color"])
                elif widget_class == "Checkbutton":
                    widget.configure(bg=bg_color, fg=fg_color, selectcolor=accent_color, activebackground=bg_color)
                elif widget_class == "Radiobutton":
                    widget.configure(bg=bg_color, fg=fg_color, selectcolor=accent_color, activebackground=bg_color)
                elif widget_class == "Scrollbar":
                    widget.configure(bg=accent_color, troughcolor=bg_color)
            except tk.TclError:
                pass  # 일부 위젯은 특정 옵션을 지원하지 않음
            
            # 자식 위젯 갱신
            for child in widget.winfo_children():
                refresh_widget(child)
        
        # 루트 윈도우부터 시작
        refresh_widget(self.root)
    
    def _load_ui_settings(self):
        """Load UI settings from file"""
        try:
            if os.path.exists(UI_SETTINGS_FILE):
                with open(UI_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}
    
    def _save_ui_settings(self):
        """Save UI settings to file"""
        try:
            with open(UI_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.ui_settings, f, indent=2)
        except Exception:
            pass
    
    def _restore_sash_position(self):
        """Restore PanedWindow sash position from saved settings"""
        if self.paned_window and "paned_sash_percentage" in self.ui_settings:
            try:
                # Restore as percentage of window height
                percentage = self.ui_settings["paned_sash_percentage"]
                # Ensure window is fully rendered
                self.root.update_idletasks()
                # Get PanedWindow height
                paned_height = self.paned_window.winfo_height()
                
                if paned_height > 100:  # Window is rendered
                    y_pos = int(paned_height * percentage)
                    self.paned_window.sash_place(0, 0, y_pos)
                else:
                    # Window not ready, try again after another delay
                    self.root.after(200, lambda: self._restore_sash_position())
            except Exception as e:
                # Silently fail - not critical
                pass
    
    def _on_paned_window_moved(self, event):
        """Save PanedWindow sash position when dragging ends"""
        if self.paned_window:
            try:
                # Get sash position and PanedWindow height
                sash_coord = self.paned_window.sash_coord(0)
                paned_height = self.paned_window.winfo_height()
                if sash_coord and paned_height > 0:
                    # Save as percentage of total height
                    percentage = sash_coord[1] / paned_height
                    self.ui_settings["paned_sash_percentage"] = percentage
                    self._save_ui_settings()
            except Exception:
                pass


if __name__ == "__main__":
    root = tk.Tk()
    app = ChampionScraperApp(root)
    root.mainloop()
