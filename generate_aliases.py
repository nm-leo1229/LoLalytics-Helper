import json
import os
import re
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_DIR = Path(__file__).resolve().parent
ALIAS_PATH = BASE_DIR / "champion_aliases.json"

VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
CHAMPION_URL = "https://ddragon.leagueoflegends.com/cdn/{version}/data/{locale}/champion.json"

SLUG_OVERRIDES = {
    "monkeyking": "wukong",
}


def fetch_json(url: str) -> dict:
    response = requests.get(url, timeout=15, verify=False)
    response.raise_for_status()
    return response.json()


def latest_version() -> str:
    versions = fetch_json(VERSIONS_URL)
    if not isinstance(versions, list) or not versions:
        raise RuntimeError("Cannot resolve Data Dragon versions.")
    return versions[0]


def load_locale_data(version: str, locale: str) -> dict:
    payload = fetch_json(CHAMPION_URL.format(version=version, locale=locale))
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected champion payload for {locale}.")
    return data


def slugify(champion_id: str) -> str:
    base = champion_id.lower()
    return SLUG_OVERRIDES.get(base, base)


def sanitize_alias(value: str) -> list[str]:
    lower = value.strip().lower()
    if not lower:
        return []
    cleaned = re.sub(r"[^0-9a-z가-힣]", "", lower)
    variants = {lower, cleaned}
    return [alias for alias in variants if alias]


def build_aliases() -> dict[str, list[str]]:
    version = latest_version()
    english_data = load_locale_data(version, "en_US")
    korean_data = load_locale_data(version, "ko_KR")

    existing = {}
    if ALIAS_PATH.exists():
        with ALIAS_PATH.open("r", encoding="utf-8") as handle:
            existing = json.load(handle)

    alias_map: dict[str, set[str]] = {}

    for champion_id, info in english_data.items():
        slug = slugify(champion_id)
        english_name = info.get("name", "").strip()
        korean_name = korean_data.get(champion_id, {}).get("name", "").strip()

        alias_bucket = alias_map.setdefault(slug, set())
        for alias in (slug, english_name, english_name.lower(), korean_name):
            if not alias:
                continue
            alias_bucket.add(alias)
            for variant in sanitize_alias(alias):
                alias_bucket.add(variant)

        for alias in existing.get(slug, []):
            if isinstance(alias, str):
                alias_bucket.add(alias)

    for slug, aliases in existing.items():
        if slug not in alias_map and isinstance(aliases, list):
            alias_map[slug] = {alias for alias in aliases if isinstance(alias, str)}

    return {slug: sorted(values, key=lambda s: (s.lower(), s)) for slug, values in sorted(alias_map.items())}


def main() -> None:
    alias_data = build_aliases()
    ALIAS_PATH.write_text(json.dumps(alias_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(alias_data)} champion alias entries to {ALIAS_PATH}")


if __name__ == "__main__":
    main()

