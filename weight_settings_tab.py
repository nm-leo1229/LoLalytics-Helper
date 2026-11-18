import tkinter as tk
from common import LANES

# 가중치 상수
LANE_WEIGHT_DEFAULT = 0.35

LANE_DISPLAY_NAMES = {
    "top": "탑",
    "jungle": "정글",
    "middle": "미드",
    "bottom": "바텀",
    "support": "서포터"
}

def load_weight_settings():
    """라인 가중치 기본값을 돌려줍니다. 사용자가 고친 값은 ui_settings.json 의 lane_weights 에 따로 저장됩니다."""
    # 기본값: 라인 조합별 상성 효과의 크기와 표본 수로 정한 값 (맞라인 카운터 1.0 기준의 한 저울, 시너지는 카운터보다 낮다).
    counter_base_map = {
        "bottom": {"bottom": 1.0, "support": 0.75, "jungle": 0.4, "middle": 0.3, "top": 0.2},
        "support": {"support": 1.0, "bottom": 0.75, "jungle": 0.45, "middle": 0.35, "top": 0.2},
        "jungle": {"jungle": 1.0, "middle": 0.6, "top": 0.5, "bottom": 0.4, "support": 0.45},
        "middle": {"middle": 1.0, "jungle": 0.6, "top": 0.4, "bottom": 0.3, "support": 0.35},
        "top": {"top": 1.0, "jungle": 0.5, "middle": 0.4, "bottom": 0.2, "support": 0.2},
    }

    synergy_base_map = {
        "bottom": {"bottom": 0.7, "support": 0.5, "jungle": 0.2, "middle": 0.2, "top": 0.1},
        "support": {"support": 0.7, "bottom": 0.5, "jungle": 0.2, "middle": 0.15, "top": 0.1},
        "jungle": {"jungle": 0.7, "middle": 0.3, "top": 0.25, "bottom": 0.2, "support": 0.2},
        "middle": {"middle": 0.7, "jungle": 0.3, "top": 0.15, "bottom": 0.2, "support": 0.15},
        "top": {"top": 0.7, "jungle": 0.25, "middle": 0.15, "bottom": 0.1, "support": 0.1},
    }

    default_weights = {
        "counter": {
            "lane_weight_map": counter_base_map
        },
        "synergy": {
            "lane_weight_map": synergy_base_map
        }
    }
    
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

