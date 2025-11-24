# Tkinter/Tcl 설치 문제 해결 가이드

## 문제 상황
Python 3.14에서 Tcl/Tk 파일이 누락되어 Tkinter를 사용할 수 없는 상황입니다.

## 해결 방법

### 방법 1: Python 재설치 (권장)

1. **Python 3.14 제거**
   - 제어판 → 프로그램 추가/제거 → Python 3.14 제거

2. **Python 3.14 재설치**
   - [Python 공식 사이트](https://www.python.org/downloads/)에서 다운로드
   - 설치 시 **반드시** "tcl/tk and IDLE" 옵션 체크
   - "Add Python to PATH" 옵션도 체크

3. **설치 확인**
   ```bash
   python -m tkinter
   ```
   창이 정상적으로 열리면 성공!

### 방법 2: Tcl/Tk 파일 수동 복사

1. **작동하는 Python 설치에서 파일 복사**
   - 다른 Python 버전(3.10, 3.11, 3.12 등)이 설치되어 있다면
   - `C:\Python3X\tcl\` 폴더를 찾아서
   - `C:\Users\user\AppData\Local\Programs\Python\Python314\tcl\`로 복사

2. **환경 변수 설정**
   ```bash
   setx TCL_LIBRARY "C:\Users\user\AppData\Local\Programs\Python\Python314\tcl\tcl8.6"
   setx TK_LIBRARY "C:\Users\user\AppData\Local\Programs\Python\Python314\tcl\tk8.6"
   ```

### 방법 3: 다른 Python 버전 사용 (임시 해결책)

Python 3.14는 아직 새 버전이라 안정성 문제가 있을 수 있습니다.

1. **Python 3.12 설치**
   ```bash
   # Python 3.12 다운로드 및 설치
   # https://www.python.org/downloads/release/python-3120/
   ```

2. **가상환경 생성**
   ```bash
   py -3.12 -m venv venv312
   venv312\Scripts\activate
   pip install -r requirements-test.txt
   ```

3. **테스트 실행**
   ```bash
   python run_tests.py
   ```

### 방법 4: 현재 상태에서 테스트 (Tkinter 없이)

Tkinter가 필요 없는 유닛 테스트만 실행:

```bash
# 유틸리티 함수 테스트만 실행 (Tkinter 불필요)
pytest test_suite.py::TestChoseongExtraction -v
pytest test_suite.py::TestAliasVariants -v
pytest test_suite.py::TestHangulDetection -v
```

## 추천 방법

**방법 1 (Python 재설치)**을 가장 추천합니다. 
- 가장 깔끔하고 확실한 해결책
- 향후 다른 문제 방지
- 10분 정도 소요

## 설치 후 확인

```bash
# Tkinter 작동 확인
python -m tkinter

# 모든 테스트 실행
python run_tests.py

# 결과: 36/36 테스트 통과 예상
```

## 참고사항

- Python 3.14는 2024년 10월에 출시된 최신 버전입니다
- 일부 패키지나 라이브러리가 아직 완벽하게 지원하지 않을 수 있습니다
- 안정성을 위해 Python 3.11 또는 3.12 사용을 고려해보세요
