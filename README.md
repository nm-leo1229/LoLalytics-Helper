# LoLalytics Scraper & Counters Finder

**LSCF** is a Python script designed to help you find the best champion choices in *League of Legends* by scraping champion data from the *LoLalytics* website. The data is then used to identify the best counter-picks based on the enemy team's composition.

## Features
- Scrapes champion data from *Lolalytics* into JSON files.
- Allows you to input enemy champion picks and receive suggestions for the best counter-picks based on real-time data.

## Usage

### Part 1: Scraping Data

1. **Run the scraper:**
   The script will open a browser (using Selenium), navigate to the *Lolalytics* page, and retrieve relevant data for all champions.
   
   ```bash
   python scraper.py X
   ```
   - X should be an integer between 0 and 5.
   - 0 means data for all champions will be scraped.
   - Numbers between 1 and 5 represent subsets of champions, allowing you to split the scraping into 5 simultaneous scripts.

   - The data will be stored in a structured format for easy access later.

### Part 2: Managing Data in the Game Lobby

1. **Run the lobby manager:**
   ```bash
   python lobby_manager.py
   ```

2. **Input enemy champions:**
   You can input the enemy team's champions as they are selected. The script will recommend optimal champions for your team to pick based on win rate and counter-pick data.

### TODO
1. **한글 또는 초성으로 영문을 불러와서 검색이 가능하도록 개선**
   예를 들어 ㅇㅁ 라고 검색하면 유미가 검색되고, 유미라고도 검색할 수 있도록 개선

2. **시너지 정보를 통해 사기 바텀 조합을 리스트 하도록 개선**
   필터 조건은 임시로 win_rate 54 이상 pick_rate 2 이상
   win_rate 로 정렬해서 표기

3. **아군 픽 또는 상대픽을 입력하면 사기 바텀 조합을 픽에 따라 추천하도록 개선**
   상대 정글 혹은 바텀이 싫어하는 원딜이나 서폿을 기반으로 추천 혹은 아군 정글이나 바텀 픽과의 시너지가 좋은 원딜이나 서폿을 추천