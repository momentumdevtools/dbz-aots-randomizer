#!/usr/bin/env python3
"""
skills.py — Typed data models for skill BDAT tables
=====================================================
Column layouts verified from BDAT JSON dumps:
  skill_<char>:   76 bytes/row,  7 rows, 46 columns (active Ki/melee skills)
  skill_combo:    12 bytes/row, 17 rows,  9 columns (team combo attacks)
  passive_<char>: 36 bytes/row,  8 rows, 14 columns (passive stat boosts)

Character table mapping:
  skill_goku / passive_goku       — Son Goku
  skill_gohan / passive_gohan     — Son Gohan
  skill_pikkoro / passive_pikkoro — Piccolo
  skill_kuririn / passive_kuririn — Krillin
  skill_tenshin / passive_tenshin — Tien Shinhan
  skill_yamcha / passive_yamcha   — Yamcha
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from randomizer.rom_io.bdat_reader import BdatFile


# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────

CHARACTER_NAMES: List[str] = [
    'goku', 'gohan', 'pikkoro', 'kuririn', 'tenshin', 'yamcha',
]

# Sentinel value for "skill level not unlockable" (0xFFFFFFFF = u32 max)
AP_LOCKED: int = 0xFFFFFFFF


# ──────────────────────────────────────────────────────────────
# ActiveSkill — one row from skill_<character> (76 bytes/row)
# ──────────────────────────────────────────────────────────────

@dataclass
class ActiveSkill:
    """A single row from a ``skill_<character>`` BDAT table.

    Field semantics:
        name        — String-table index for the skill name.
        blast_type  — Damage element / animation type (0=melee, 1=ki, etc.)
        range       — Targeting range ID.
        width/height— AoE dimensions (0 = single-target).

        use_ap1–5   — AP cost to unlock skill levels 1–5
                      (0xFFFFFFFF = locked / unavailable at that tier).
        use_mp1–5   — Ki (MP) cost per use at levels 1–5.

        power1–5    — Base damage multiplier per skill level.
        hit1–5      — Accuracy % per skill level.

        efftype     — Status effect category (0 = none, 6 = buff, 7 = debuff…).
        effect1–5   — Status effect ID applied at each level.
        effpow1–5   — Effect potency / chance %.
        effturn1–5  — Effect duration in turns (s8, can be negative).

        cond_blast1 — Required blast-type prerequisite (skill-tree gate).
        cond_lv1    — Required prerequisite level.
        cond_blast2 — Second prerequisite blast-type (0 = none).
        cond_lv2    — Second prerequisite level (0 = none).

        help        — String-table index for the skill description.
    """

    # --- identity (DO NOT randomize) ---
    name: int           # u8  — string table index
    blast_type: int     # u8  — damage/animation type
    range: int          # u8  — targeting range
    width: int          # u8  — AoE width
    height: int         # u8  — AoE height

    # --- AP unlock costs (u32 each) ---
    use_ap1: int
    use_ap2: int
    use_ap3: int
    use_ap4: int
    use_ap5: int

    # --- Ki (MP) cost per use (u16 each) ---
    use_mp1: int
    use_mp2: int
    use_mp3: int
    use_mp4: int
    use_mp5: int

    # --- damage power per level (u16 each) ---
    power1: int
    power2: int
    power3: int
    power4: int
    power5: int

    # --- accuracy per level (u8 each, %) ---
    hit1: int
    hit2: int
    hit3: int
    hit4: int
    hit5: int

    # --- status effects ---
    efftype: int        # u8  — effect category
    effect1: int        # u16
    effect2: int        # u16
    effect3: int        # u16
    effect4: int        # u16
    effect5: int        # u16
    effpow1: int        # u8
    effpow2: int        # u8
    effpow3: int        # u8
    effpow4: int        # u8
    effpow5: int        # u8
    effturn1: int       # s8
    effturn2: int       # s8
    effturn3: int       # s8
    effturn4: int       # s8
    effturn5: int       # s8

    # --- skill-tree prerequisites (DO NOT randomize) ---
    cond_blast1: int    # u8
    cond_lv1: int       # u8
    cond_blast2: int    # u8
    cond_lv2: int       # u8

    # --- description (DO NOT randomize) ---
    help: int           # u8


# ──────────────────────────────────────────────────────────────
# ComboSkill — one row from skill_combo (12 bytes/row)
# ──────────────────────────────────────────────────────────────

@dataclass
class ComboSkill:
    """A single row from the ``skill_combo`` BDAT table.

    Field semantics:
        title    — String-table index for the combo name.
        help     — String-table index for the combo description.
        dmgRate  — Damage multiplier (u16, percentage; 100 = 1.0×).
        pc1–pc3  — Character slot IDs required for the combo (0 = unused).
        blast1–3 — Blast/skill type each participant must use (0 = basic atk).
    """

    # --- identity (DO NOT randomize) ---
    title: int          # u8
    help: int           # u8

    # --- combat value ---
    dmgRate: int        # u16 — damage rate (percentage)

    # --- participant setup (DO NOT randomize) ---
    pc1: int            # u8
    blast1: int         # u8
    pc2: int            # u8
    blast2: int         # u8
    pc3: int            # u8
    blast3: int         # u8


# ──────────────────────────────────────────────────────────────
# PassiveSkill — one row from passive_<character> (36 bytes/row)
# ──────────────────────────────────────────────────────────────

@dataclass
class PassiveSkill:
    """A single row from a ``passive_<character>`` BDAT table.

    Field semantics:
        name     — String-table index for the passive name.
        type     — Passive category (e.g. 29=stat boost, 13=special).
        value    — Bitmask or signed modifier (s16). Encodes WHICH stats
                   are affected (e.g. 1=ATK, 2=DEF, 256=HP, 16384=evasion…).

        use_ap1–5 — AP cost to unlock passive levels 1–5
                    (0xFFFFFFFF = locked / unavailable).
        power1–5  — Effect magnitude at each level (u16).

        help     — String-table index for the passive description.
    """

    # --- identity (DO NOT randomize) ---
    name: int           # u8

    # --- passive type & value ---
    type: int           # u8  — passive category
    value: int          # s16 — stat bitmask / modifier

    # --- AP unlock costs (u32 each) ---
    use_ap1: int
    use_ap2: int
    use_ap3: int
    use_ap4: int
    use_ap5: int

    # --- effect magnitude per level (u16 each) ---
    power1: int
    power2: int
    power3: int
    power4: int
    power5: int

    # --- description (DO NOT randomize) ---
    help: int           # u8


# ──────────────────────────────────────────────────────────────
# Row → dataclass converters
# ──────────────────────────────────────────────────────────────

def _row_to_active(row: dict) -> ActiveSkill:
    """Convert a raw BDAT row dict into an :class:`ActiveSkill`."""
    return ActiveSkill(
        name=row.get('name', 0),
        blast_type=row.get('blast_type', 0),
        range=row.get('range', 0),
        width=row.get('width', 0),
        height=row.get('height', 0),
        use_ap1=row.get('use_ap1', 0),
        use_ap2=row.get('use_ap2', 0),
        use_ap3=row.get('use_ap3', 0),
        use_ap4=row.get('use_ap4', 0),
        use_ap5=row.get('use_ap5', 0),
        use_mp1=row.get('use_mp1', 0),
        use_mp2=row.get('use_mp2', 0),
        use_mp3=row.get('use_mp3', 0),
        use_mp4=row.get('use_mp4', 0),
        use_mp5=row.get('use_mp5', 0),
        power1=row.get('power1', 0),
        power2=row.get('power2', 0),
        power3=row.get('power3', 0),
        power4=row.get('power4', 0),
        power5=row.get('power5', 0),
        hit1=row.get('hit1', 0),
        hit2=row.get('hit2', 0),
        hit3=row.get('hit3', 0),
        hit4=row.get('hit4', 0),
        hit5=row.get('hit5', 0),
        efftype=row.get('efftype', 0),
        effect1=row.get('effect1', 0),
        effect2=row.get('effect2', 0),
        effect3=row.get('effect3', 0),
        effect4=row.get('effect4', 0),
        effect5=row.get('effect5', 0),
        effpow1=row.get('effpow1', 0),
        effpow2=row.get('effpow2', 0),
        effpow3=row.get('effpow3', 0),
        effpow4=row.get('effpow4', 0),
        effpow5=row.get('effpow5', 0),
        effturn1=row.get('effturn1', 0),
        effturn2=row.get('effturn2', 0),
        effturn3=row.get('effturn3', 0),
        effturn4=row.get('effturn4', 0),
        effturn5=row.get('effturn5', 0),
        cond_blast1=row.get('cond_blast1', 0),
        cond_lv1=row.get('cond_lv1', 0),
        cond_blast2=row.get('cond_blast2', 0),
        cond_lv2=row.get('cond_lv2', 0),
        help=row.get('help', 0),
    )


def _row_to_combo(row: dict) -> ComboSkill:
    """Convert a raw BDAT row dict into a :class:`ComboSkill`."""
    return ComboSkill(
        title=row.get('title', 0),
        help=row.get('help', 0),
        dmgRate=row.get('dmgRate', 0),
        pc1=row.get('pc1', 0),
        blast1=row.get('blast1', 0),
        pc2=row.get('pc2', 0),
        blast2=row.get('blast2', 0),
        pc3=row.get('pc3', 0),
        blast3=row.get('blast3', 0),
    )


def _row_to_passive(row: dict) -> PassiveSkill:
    """Convert a raw BDAT row dict into a :class:`PassiveSkill`."""
    return PassiveSkill(
        name=row.get('name', 0),
        type=row.get('type', 0),
        value=row.get('value', 0),
        use_ap1=row.get('use_ap1', 0),
        use_ap2=row.get('use_ap2', 0),
        use_ap3=row.get('use_ap3', 0),
        use_ap4=row.get('use_ap4', 0),
        use_ap5=row.get('use_ap5', 0),
        power1=row.get('power1', 0),
        power2=row.get('power2', 0),
        power3=row.get('power3', 0),
        power4=row.get('power4', 0),
        power5=row.get('power5', 0),
        help=row.get('help', 0),
    )


# ──────────────────────────────────────────────────────────────
# Public loader functions
# ──────────────────────────────────────────────────────────────

def load_character_skills(bdat: BdatFile, character: str) -> List[ActiveSkill]:
    """Load all rows from the ``skill_<character>`` table.

    Args:
        bdat:      A parsed :class:`BdatFile` containing skill BDAT data.
        character: One of CHARACTER_NAMES (e.g. ``'goku'``, ``'pikkoro'``).

    Returns:
        Ordered list of :class:`ActiveSkill` — one per skill row.

    Raises:
        ValueError: If the table is not found or character name is invalid.
    """
    if character not in CHARACTER_NAMES:
        raise ValueError(
            f"Invalid character '{character}'. "
            f"Must be one of: {CHARACTER_NAMES}"
        )
    table_name = f'skill_{character}'
    table = bdat.get_table(table_name)
    if table is None:
        raise ValueError(
            f"Table '{table_name}' not found in BDAT file. "
            f"Available tables: {[t.name for t in bdat.tables]}"
        )
    return [_row_to_active(row) for row in table.rows]


def load_combo_skills(bdat: BdatFile) -> List[ComboSkill]:
    """Load all rows from the ``skill_combo`` table.

    Args:
        bdat: A parsed :class:`BdatFile` containing skill BDAT data.

    Returns:
        Ordered list of :class:`ComboSkill` — one per combo row.

    Raises:
        ValueError: If the ``skill_combo`` table is not found.
    """
    table = bdat.get_table('skill_combo')
    if table is None:
        raise ValueError(
            "Table 'skill_combo' not found in BDAT file. "
            f"Available tables: {[t.name for t in bdat.tables]}"
        )
    return [_row_to_combo(row) for row in table.rows]


def load_passive_skills(bdat: BdatFile, character: str) -> List[PassiveSkill]:
    """Load all rows from the ``passive_<character>`` table.

    Args:
        bdat:      A parsed :class:`BdatFile` containing passive BDAT data.
        character: One of CHARACTER_NAMES (e.g. ``'goku'``, ``'yamcha'``).

    Returns:
        Ordered list of :class:`PassiveSkill` — one per passive row.

    Raises:
        ValueError: If the table is not found or character name is invalid.
    """
    if character not in CHARACTER_NAMES:
        raise ValueError(
            f"Invalid character '{character}'. "
            f"Must be one of: {CHARACTER_NAMES}"
        )
    table_name = f'passive_{character}'
    table = bdat.get_table(table_name)
    if table is None:
        raise ValueError(
            f"Table '{table_name}' not found in BDAT file. "
            f"Available tables: {[t.name for t in bdat.tables]}"
        )
    return [_row_to_passive(row) for row in table.rows]
