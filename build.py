import PyInstaller.__main__
import os

# Define arguments
args = [
    'lobby_manager.py',
    '--onefile',
    '--noconsole',
    '--name=LoLalyticsHelper',
    '--add-data=data;data',
    '--add-data=champion_aliases.json;.',
    '--add-data=ignored_champions.json;.',
    '--exclude-module=scraper',
    '--clean',
]

print(f"Running PyInstaller with args: {args}")
PyInstaller.__main__.run(args)
