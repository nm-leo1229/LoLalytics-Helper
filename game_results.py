"""픽 확정 때 저장한 스냅샷(debug_data/snapshot_*.json)에 클라이언트 전적에서 찾은 승패를 채운다.

스냅샷이 쌓이는 곳은 게임하는 PC 다. 채운 스냅샷을 커밋하면 다른 PC 에서 분석할 수 있다.
다른 플레이어 이름은 저장하지 않는다 (스냅샷에도 챔피언·라인·픽 순서·밴만 있다).
"""
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

MATCH_HISTORY_PATH = "/lol-match-history/v1/products/lol/current-summoner/matches?begIndex=0&endIndex=49"
MATCH_WINDOW = 15 * 60  # 픽 확정 뒤 이 시간(초) 안에 시작한 같은 챔피언 게임을 그 판으로 본다
CLOCK_SLACK = 2 * 60  # PC 시계가 빠르거나 게임 생성 시각이 픽 확정보다 앞서도 잡히게 둔 여유(초)


def history_games(payload):
    """클라이언트 전적 응답에서 [{gameId, created(초), duration, queueId, championId, win, kills, deaths, assists, cs}].

    목록 응답의 participants 에는 나 한 명만 들어 있다. 형식이 다른 게임은 건너뛴다."""
    games = []
    for game in ((payload or {}).get("games") or {}).get("games") or []:
        try:
            me = game["participants"][0]
            stats = me["stats"]
            games.append({
                "gameId": game["gameId"], "created": game["gameCreation"] / 1000, "duration": game["gameDuration"],
                "queueId": game.get("queueId"), "championId": me["championId"], "win": bool(stats["win"]),
                "kills": stats.get("kills"), "deaths": stats.get("deaths"), "assists": stats.get("assists"),
                "cs": (stats.get("totalMinionsKilled") or 0) + (stats.get("neutralMinionsKilled") or 0)})
        except (KeyError, IndexError, TypeError):
            continue
    return games


def find_result(snapshot, games):
    """그 스냅샷의 결과 dict. 찾았으면 found=True, 끝내 없을 판(닷지·전적 범위 밖)이면 found=False, 아직 모르면 None."""
    started = snapshot.get("timestamp")
    mine = next((entry.get("championId") for entry in snapshot.get("allies") or [] if entry.get("isLocalPlayer")), None)
    if not isinstance(started, (int, float)) or not games:
        return None
    game_id = snapshot.get("gameId")
    # 게임 번호가 있으면 그것만 본다: 닷지한 판이 바로 다음 같은 챔피언 판의 결과를 가져가면 안 된다
    matches = ([game for game in games if game["gameId"] == game_id] if game_id else
               [game for game in games if game["championId"] == mine and -CLOCK_SLACK <= game["created"] - started <= MATCH_WINDOW])
    if matches:
        game = min(matches, key=lambda item: abs(item["created"] - started))
        return {"found": True, **{key: value for key, value in game.items() if key not in ("created", "championId")}}
    # 이 판보다 뒤에 시작한 게임이 전적에 있는데 못 찾았으면 닷지, 전적이 이 판보다 늦게 시작하면 범위 밖
    if any(game["created"] - started > MATCH_WINDOW for game in games) or min(game["created"] for game in games) > started:
        return {"found": False}
    return None


def pending_snapshots(directory):
    """[(경로, 스냅샷)]: 결과가 아직 없는 스냅샷"""
    pending = []
    for path in sorted(Path(directory).glob("snapshot_*.json")):
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        # 손으로 고쳐 형식이 틀어진 파일은 건너뛴다 (한 파일 때문에 그 뒤 스냅샷이 막히지 않게)
        if isinstance(snapshot, dict) and "result" not in snapshot and isinstance(snapshot.get("allies"), list) \
                and all(isinstance(entry, dict) for entry in snapshot["allies"]):
            pending.append((path, snapshot))
    return pending


def fill_results(directory, games):
    """결과를 찾은 스냅샷에 result 를 써 넣고 그 수를 돌려준다. 파일은 다 쓴 뒤 한 번에 바꾼다."""
    filled = 0
    for path, snapshot in pending_snapshots(directory):
        result = find_result(snapshot, games)
        if result is None:
            continue
        snapshot["result"] = result
        handle = NamedTemporaryFile(dir=path.parent, delete=False, mode="w", encoding="utf-8", suffix=".tmp")
        temporary = Path(handle.name)
        try:
            with handle:
                json.dump(snapshot, handle, ensure_ascii=False, indent=4)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        filled += 1
    return filled


if __name__ == "__main__":
    started = 1_800_000_000
    snap = {"timestamp": started, "allies": [{"championId": 222, "isLocalPlayer": True}]}
    later = {"gameId": 9, "created": started + 60, "duration": 1500, "queueId": 420, "championId": 222, "win": True,
             "kills": 1, "deaths": 2, "assists": 3, "cs": 250}
    assert find_result(snap, [later])["win"] is True
    assert find_result(snap, [dict(later, created=started - 3600)]) is None  # 게임 중이라 전적엔 이전 판만 있다
    assert find_result(dict(snap, timestamp=started - 7200), [later]) == {"found": False}  # 전적 범위보다 오래된 판
    assert find_result(snap, [dict(later, championId=1, created=started + 3600)]) == {"found": False}  # 닷지
    assert find_result(dict(snap, gameId=9), [dict(later, created=started + 3600)])["gameId"] == 9
    assert find_result(dict(snap, gameId=8), [later, dict(later, gameId=10, created=started + 3600)]) == {"found": False}  # 닷지한 판은 다음 판을 가져가지 않는다
    assert find_result(snap, [dict(later, created=started - 60)])["win"] is True  # 시계 오차
    print("ok")
