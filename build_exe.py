#!/usr/bin/env python3
"""
build_exe.py — Package DBZ AotS Randomizer as standalone .exe
==============================================================
Requirements: pip install pyinstaller customtkinter ndspy

Usage:
    python build_exe.py

Output:
    dist/DBZ_AotS_Randomizer.exe
"""

import subprocess
import sys
import os

# Ensure we're in the project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Find customtkinter path for data files
import customtkinter
ctk_path = os.path.dirname(customtkinter.__file__)

# Build command
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--windowed",
    "--name", "DBZ_AotS_Randomizer",
    # Include customtkinter theme data
    f"--add-data={ctk_path};customtkinter",
    # Include randomizer package
    "--hidden-import=randomizer",
    "--hidden-import=randomizer.config",
    "--hidden-import=randomizer.presets",
    "--hidden-import=randomizer.patcher.rom_builder",
    "--hidden-import=randomizer.rom_io.nds_rom",
    "--hidden-import=randomizer.rom_io.bdat_reader",
    "--hidden-import=randomizer.utils.rng",
    "--hidden-import=randomizer.randomizers.encounter_shuffle",
    "--hidden-import=randomizer.randomizers.enemy_stats",
    "--hidden-import=randomizer.randomizers.encounter_randomizer",
    "--hidden-import=randomizer.randomizers.ki_blast_rebalancer",
    "--hidden-import=randomizer.randomizers.drop_shuffle",
    "--hidden-import=randomizer.randomizers.boss_scaler",
    "--hidden-import=randomizer.randomizers.chaos_resistances",
    "--hidden-import=randomizer.randomizers.shop_item_randomizer",
    "--hidden-import=randomizer.randomizers.player_growth",
    "--hidden-import=randomizer.randomizers.music_shuffle",
    "--hidden-import=randomizer.randomizers.palette_randomizer",
    "--hidden-import=ndspy",
    "--hidden-import=ndspy.rom",
    "--hidden-import=ndspy.soundArchive",
    "--hidden-import=colorsys",
    # Collect all ndspy submodules
    "--collect-all=ndspy",
    # Entry point
    "randomizer/gui.py",
]

print("Building DBZ AotS Randomizer .exe...")
print(f"Command: {' '.join(cmd)}")
print()

result = subprocess.run(cmd, capture_output=False)

if result.returncode == 0:
    print("\n[OK] Build successful!")
    print("   Output: dist/DBZ_AotS_Randomizer.exe")
else:
    print(f"\n[FAIL] Build failed with exit code {result.returncode}")
    sys.exit(1)
