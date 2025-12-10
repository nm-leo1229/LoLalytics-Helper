import os

import PyInstaller.__main__  # type: ignore[import-not-found]

base_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(base_dir, "VERSION"), encoding="utf-8") as f:
    version = f.read().strip()

# Define arguments
args = [
    "lobby_manager.py",
    "--onefile",
    "--noconsole",
    f"--name=TtimoTtabbong_{version}",
    "--add-data=VERSION;.",
    "--add-data=data;data",
    "--add-data=champion_aliases.json;.",
    "--add-data=ignored_champions.json;.",
    "--add-data=credits.json;.",
    "--icon=icon.ico",
    "--exclude-module=scraper",
    "--clean",
]

print(f"Running PyInstaller with args: {args}")
PyInstaller.__main__.run(args)
