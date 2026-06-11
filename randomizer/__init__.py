"""
DBZ: Attack of the Saiyans — NDS ROM Randomizer
================================================
Seed-based randomizer for Dragon Ball Z: Attack of the Saiyans (NDS).
Modifies BDAT tables and encounter data to create unique playthroughs.

Usage:
    python -m randomizer --rom "path/to/rom.nds" --seed 42

Architecture:
    rom_io/     — ROM file I/O (ndspy wrapper, BDAT read/write)
    data/       — Typed data models (enemies, items, encounters)
    randomizers/ — Randomization algorithms
    patcher/    — Binary patching & ROM building
    logic/      — Progression logic graph (future: Archipelago)
    utils/      — Shared utilities (RNG, validation)
"""

__version__ = "0.1.0"
__title__ = "DBZ AotS Randomizer"
