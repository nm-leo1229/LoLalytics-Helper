import tkinter as tk
import json
import os
import copy
from common import LANES, resolve_resource_path

WEIGHT_SETTINGS_FILE = resolve_resource_path("weight_settings.json")

# 가중치 상수
LANE_WEIGHT_DEEP = 1.0
LANE_WEIGHT_LOW_DEEP = 0.7
LANE_WEIGHT_SHALLOW = 0.5
LANE_WEIGHT_DEFAULT = 0.35

SYNERGY_WEIGHT_PENALTY = 0.3

LANE_DISPLAY_NAMES = {
    "top": "탑",
    "jungle": "정글",
    "middle": "미드",
    "bottom": "바텀",
    "support": "서포터"
}

def normalize_float_values(data):
    """딕셔너리 내의 모든 float 값을 소수점 2자리로 반올림합니다"""
    if isinstance(data, dict):
        return {key: normalize_float_values(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [normalize_float_values(item) for item in data]
    elif isinstance(data, float):
        return round(data, 2)
    else:
        return data

def load_weight_settings():
    """가중치 설정 파일을 불러옵니다. 없으면 기본값으로 생성합니다."""
    if os.path.exists(WEIGHT_SETTINGS_FILE):
        try:
            with open(WEIGHT_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 기존 형식 마이그레이션 (lane_weight_map이 최상위에 있는 경우)
                if "lane_weight_map" in data and "counter" not in data:
                    old_map = data.get("lane_weight_map", {})
                    data = {
                        "counter": {
                            "lane_weight_map": copy.deepcopy(old_map)
                        },
                        "synergy": {
                            "lane_weight_map": copy.deepcopy(old_map)
                        }
                    }
                    # 마이그레이션된 데이터 저장 (부동소수점 정규화)
                    try:
                        normalized_data = normalize_float_values(data)
                        with open(WEIGHT_SETTINGS_FILE, "w", encoding="utf-8") as f:
                            json.dump(normalized_data, f, indent=2, ensure_ascii=False)
                    except OSError:
                        pass
                return data
        except (OSError, json.JSONDecodeError):
            pass
    
    # 기본값 생성
    counter_base_map = {
        "bottom": {
            "bottom": LANE_WEIGHT_DEEP,
            "support": LANE_WEIGHT_DEEP,
            "jungle": LANE_WEIGHT_SHALLOW,
            "middle": LANE_WEIGHT_DEFAULT,
            "top": LANE_WEIGHT_DEFAULT
        },
        "support": {
            "support": LANE_WEIGHT_DEEP,
            "bottom": LANE_WEIGHT_LOW_DEEP,
            "jungle": LANE_WEIGHT_SHALLOW,
            "middle": LANE_WEIGHT_SHALLOW,
            "top": LANE_WEIGHT_SHALLOW
        },
        "jungle": {
            "jungle": LANE_WEIGHT_DEEP,
            "middle": LANE_WEIGHT_DEEP,
            "top": LANE_WEIGHT_DEEP,
            "bottom": LANE_WEIGHT_SHALLOW,
            "support": LANE_WEIGHT_SHALLOW
        },
        "middle": {
            "middle": LANE_WEIGHT_DEEP,
            "jungle": LANE_WEIGHT_DEEP,
            "top": LANE_WEIGHT_SHALLOW,
            "bottom": LANE_WEIGHT_DEFAULT,
            "support": LANE_WEIGHT_SHALLOW
        },
        "top": {
            "top": LANE_WEIGHT_DEEP,
            "jungle": LANE_WEIGHT_DEEP,
            "middle": LANE_WEIGHT_SHALLOW,
            "bottom": LANE_WEIGHT_DEFAULT,
            "support": LANE_WEIGHT_SHALLOW
        }
    }
    
    synergy_base_map = {
        "bottom": {
            "bottom": round(LANE_WEIGHT_DEEP - SYNERGY_WEIGHT_PENALTY, 2),
            "support": round(LANE_WEIGHT_DEEP - SYNERGY_WEIGHT_PENALTY, 2),
            "jungle": round(LANE_WEIGHT_SHALLOW - SYNERGY_WEIGHT_PENALTY, 2),
            "middle": round(LANE_WEIGHT_DEFAULT - SYNERGY_WEIGHT_PENALTY, 2),
            "top": round(LANE_WEIGHT_DEFAULT - SYNERGY_WEIGHT_PENALTY, 2)
        },
        "support": {
            "support": round(LANE_WEIGHT_DEEP - SYNERGY_WEIGHT_PENALTY, 2),
            "bottom": round(LANE_WEIGHT_LOW_DEEP - SYNERGY_WEIGHT_PENALTY, 2),
            "jungle": round(LANE_WEIGHT_SHALLOW - SYNERGY_WEIGHT_PENALTY, 2),
            "middle": round(LANE_WEIGHT_SHALLOW - SYNERGY_WEIGHT_PENALTY, 2),
            "top": round(LANE_WEIGHT_SHALLOW - SYNERGY_WEIGHT_PENALTY, 2)
        },
        "jungle": {
            "jungle": round(LANE_WEIGHT_DEEP - SYNERGY_WEIGHT_PENALTY, 2),
            "middle": round(LANE_WEIGHT_DEEP - SYNERGY_WEIGHT_PENALTY, 2),
            "top": round(LANE_WEIGHT_DEEP - SYNERGY_WEIGHT_PENALTY, 2),
            "bottom": round(LANE_WEIGHT_SHALLOW - SYNERGY_WEIGHT_PENALTY, 2),
            "support": round(LANE_WEIGHT_SHALLOW - SYNERGY_WEIGHT_PENALTY, 2)
        },
        "middle": {
            "middle": round(LANE_WEIGHT_DEEP - SYNERGY_WEIGHT_PENALTY, 2),
            "jungle": round(LANE_WEIGHT_DEEP - SYNERGY_WEIGHT_PENALTY, 2),
            "top": round(LANE_WEIGHT_SHALLOW - SYNERGY_WEIGHT_PENALTY, 2),
            "bottom": round(LANE_WEIGHT_DEFAULT - SYNERGY_WEIGHT_PENALTY, 2),
            "support": round(LANE_WEIGHT_SHALLOW - SYNERGY_WEIGHT_PENALTY, 2)
        },
        "top": {
            "top": round(LANE_WEIGHT_DEEP - SYNERGY_WEIGHT_PENALTY, 2),
            "jungle": round(LANE_WEIGHT_DEEP - SYNERGY_WEIGHT_PENALTY, 2),
            "middle": round(LANE_WEIGHT_SHALLOW - SYNERGY_WEIGHT_PENALTY, 2),
            "bottom": round(LANE_WEIGHT_DEFAULT - SYNERGY_WEIGHT_PENALTY, 2),
            "support": round(LANE_WEIGHT_SHALLOW - SYNERGY_WEIGHT_PENALTY, 2)
        }
    }

    default_weights = {
        "counter": {
            "lane_weight_map": copy.deepcopy(counter_base_map)
        },
        "synergy": {
            "lane_weight_map": copy.deepcopy(synergy_base_map)
        }
    }
    
    # 파일 저장 (부동소수점 정규화)
    try:
        normalized_weights = normalize_float_values(default_weights)
        with open(WEIGHT_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(normalized_weights, f, indent=2, ensure_ascii=False)
    except OSError:
        pass
    
    return default_weights

class WeightSettingsTab:
    def __init__(self, notebook, app_context):
        self.notebook = notebook
        self.app = app_context
        
        self.tab = tk.Frame(self.notebook)
        self.notebook.add(self.tab, text="가중치 설정")
        
        self.counter_weight_entries = {}
        self.synergy_weight_entries = {}
        self.weight_settings = load_weight_settings()
        
        self._build_ui()
        self._load_weight_entries("counter")
        self._load_weight_entries("synergy")
    
    def _build_ui(self):
        """가중치 설정 탭 UI를 생성합니다"""
        weight_frame = tk.Frame(self.tab)
        weight_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 카운터 가중치 섹션
        counter_frame = tk.LabelFrame(weight_frame, text="카운터 가중치")
        counter_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self._build_weight_table(counter_frame, "counter", LANE_DISPLAY_NAMES)
        
        # 시너지 가중치 섹션
        synergy_frame = tk.LabelFrame(weight_frame, text="시너지 가중치")
        synergy_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self._build_weight_table(synergy_frame, "synergy", LANE_DISPLAY_NAMES)
    
    def _build_weight_table(self, parent, weight_type, lane_display_names):
        """가중치 테이블을 생성합니다"""
        # 헤더 행
        header_frame = tk.Frame(parent)
        header_frame.pack(fill="x", padx=5, pady=5)
        
        tk.Label(header_frame, text="라인             ", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, padx=5, pady=5)
        
        # 상대/아군 라인 헤더
        for col_idx, source_lane in enumerate(LANES, start=1):
            tk.Label(header_frame, text=lane_display_names.get(source_lane, source_lane), 
                    font=("Segoe UI", 9, "bold"), width=8).grid(row=0, column=col_idx, padx=2, pady=5)
        
        # 각 나의 라인별 행
        entries_dict = {}
        for row_idx, target_lane in enumerate(LANES, start=1):
            row_frame = tk.Frame(parent)
            row_frame.pack(fill="x", padx=5, pady=2)
            
            # 나의 라인 레이블
            tk.Label(row_frame, text=lane_display_names.get(target_lane, target_lane), 
                    width=12, anchor="w").grid(row=0, column=0, padx=5, sticky="w")
            
            # 각 상대/아군 라인별 입력 필드
            row_entries = {}
            for col_idx, source_lane in enumerate(LANES, start=1):
                entry = tk.Entry(row_frame, width=8)
                entry.grid(row=0, column=col_idx, padx=2)
                
                # 기본값 설정
                weight_type_settings = self.weight_settings.get(weight_type, {})
                lane_weight_map = weight_type_settings.get("lane_weight_map", {})
                mapping = lane_weight_map.get(target_lane, {})
                weight_value = mapping.get(source_lane, LANE_WEIGHT_DEFAULT)
                entry.insert(0, f"{weight_value:.2f}")
                
                # 변경 시 저장
                entry.bind("<KeyRelease>", lambda e, t=target_lane, s=source_lane, wt=weight_type: 
                          self._on_weight_entry_changed(t, s, wt))
                entry.bind("<FocusOut>", lambda e, t=target_lane, s=source_lane, wt=weight_type: 
                          self._on_weight_entry_changed(t, s, wt))
                
                row_entries[source_lane] = entry
            
            entries_dict[target_lane] = row_entries
        
        if weight_type == "counter":
            self.counter_weight_entries = entries_dict
        else:
            self.synergy_weight_entries = entries_dict
    
    def _load_weight_entries(self, weight_type):
        """저장된 가중치 값을 입력 필드에 불러옵니다"""
        weight_settings = self.app.ui_settings.get("lane_weights", {})
        entries_dict = self.counter_weight_entries if weight_type == "counter" else self.synergy_weight_entries
        
        for target_lane, row_entries in entries_dict.items():
            lane_settings = weight_settings.get(target_lane, {})
            type_settings = lane_settings.get(weight_type, {})
            
            for source_lane, entry in row_entries.items():
                saved_weight = type_settings.get(source_lane)
                if saved_weight is not None:
                    entry.delete(0, tk.END)
                    entry.insert(0, f"{saved_weight:.2f}")
                else:
                    # 기본값 사용
                    weight_type_settings = self.weight_settings.get(weight_type, {})
                    lane_weight_map = weight_type_settings.get("lane_weight_map", {})
                    mapping = lane_weight_map.get(target_lane, {})
                    weight_value = mapping.get(source_lane, LANE_WEIGHT_DEFAULT)
                    entry.delete(0, tk.END)
                    entry.insert(0, f"{weight_value:.2f}")
    
    def _on_weight_entry_changed(self, target_lane, source_lane, weight_type):
        """개별 가중치 입력 필드가 변경되었을 때 호출됩니다"""
        entries_dict = self.counter_weight_entries if weight_type == "counter" else self.synergy_weight_entries
        
        if target_lane not in entries_dict or source_lane not in entries_dict[target_lane]:
            return
        
        entry = entries_dict[target_lane][source_lane]
        weight_value = self.app.parse_float(entry.get())
        
        # 유효성 검사
        if weight_value < 0:
            weight_type_settings = self.weight_settings.get(weight_type, {})
            lane_weight_map = weight_type_settings.get("lane_weight_map", {})
            mapping = lane_weight_map.get(target_lane, {})
            weight_value = mapping.get(source_lane, LANE_WEIGHT_DEFAULT)
            entry.delete(0, tk.END)
            entry.insert(0, f"{weight_value:.2f}")
        
        # 저장
        if "lane_weights" not in self.app.ui_settings:
            self.app.ui_settings["lane_weights"] = {}
        
        if target_lane not in self.app.ui_settings["lane_weights"]:
            self.app.ui_settings["lane_weights"][target_lane] = {}
        
        if weight_type not in self.app.ui_settings["lane_weights"][target_lane]:
            self.app.ui_settings["lane_weights"][target_lane][weight_type] = {}
        
        self.app.ui_settings["lane_weights"][target_lane][weight_type][source_lane] = round(weight_value, 2)
        self.app._save_ui_settings()
        
        # 추천 업데이트
        self.app.update_banpick_recommendations()
        if hasattr(self.app, "update_team_total_scores"):
            self.app.update_team_total_scores()
        if hasattr(self.app, "_update_all_slot_scores"):
            self.app._update_all_slot_scores()

