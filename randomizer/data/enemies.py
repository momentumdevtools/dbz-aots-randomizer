#!/usr/bin/env python3
"""
enemies.py — Typed data models for enemy_param & boss_param BDAT tables
=========================================================================
Column layouts verified via BDAT reader against the NDS ROM:
  enemy_param: 80 bytes/row, 173 rows, 32 columns
  boss_param:  88 bytes/row,  55 rows, 38 columns

boss_param shares the enemy_param schema and adds:
  atk5/atk6 (extra AI action slots), atk5_pow/atk6_pow,
  angry (rage threshold), script (NitroFS AI script file ID).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from randomizer.rom_io.bdat_reader import BdatFile


# ──────────────────────────────────────────────────────────────
# enemy_param — regular encounter enemies (80 bytes/row)
# ──────────────────────────────────────────────────────────────

@dataclass
class EnemyParam:
    """A single row from the ``enemy_param`` BDAT table.

    Field semantics (ARM9-verified):
        name_id   — Index into the ``character_name`` string table.
        file      — Sprite archive filename (NitroFS).
        palno     — Palette slot number.
        size      — Sprite size class.
        shadow    — Shadow type drawn under the sprite.
        power     — Overall "power level" scalar (UI display).
        zeni      — Gold dropped on defeat.
        exp       — Experience rewarded.
        ap        — Ability Points rewarded.
        item1‑4   — Drop table item IDs (0 = none).
        atk1‑4    — AI action-slot weights (u8; higher = more likely).
        atk1_pow‑atk4_pow — Skill power per action (s16).
        lv        — Enemy level.
        hp / mp   — Hit Points / Magic Points.
        str‑luc   — Core stats (STR DEF REC TEC AGI LUC).
        sleep‑dead — Status-ailment resistance modifiers (s8, %).
        physics / slash / blast — Physical-damage-type resistances (s8, %).
        atr_fire / atr_thunder / atr_ice — Elemental resistances (s8, %).
        list      — Enemy-list category flag.
    """

    # --- identity ---
    name_id: int        # u16 — character_name table index
    file: str           # str — sprite file reference
    palno: int          # u8
    size: int           # u8
    shadow: int         # u8

    # --- rewards ---
    power: int          # u32
    zeni: int           # u32
    exp: int            # u32
    ap: int             # u16

    # --- drops ---
    item1: int          # u16
    item2: int          # u16
    item3: int          # u16
    item4: int          # u16

    # --- AI action weights ---
    atk1: int           # u8
    atk2: int           # u8
    atk3: int           # u8
    atk4: int           # u8

    # --- skill power per action ---
    atk1_pow: int       # s16
    atk2_pow: int       # s16
    atk3_pow: int       # s16
    atk4_pow: int       # s16

    # --- level / resources ---
    lv: int             # u8
    hp: int             # u32
    mp: int             # u32

    # --- core stats ---
    str_: int           # u16  (renamed to avoid builtin collision)
    def_: int           # u16  (renamed to avoid keyword collision)
    rec: int            # u16
    tec: int            # u16
    agi: int            # u16
    luc: int            # u16

    # --- status resistances (s8, %) ---
    sleep: int
    poison: int
    blind: int
    bind: int
    stun: int
    panic: int
    freeze: int
    dead: int

    # --- damage-type resistances (s8, %) ---
    physics: int
    slash: int
    blast: int

    # --- elemental resistances (s8, %) ---
    atr_fire: int
    atr_thunder: int
    atr_ice: int

    # --- misc ---
    list: int           # u8


# ──────────────────────────────────────────────────────────────
# boss_param — boss / story-fight enemies (88 bytes/row)
# ──────────────────────────────────────────────────────────────

@dataclass
class BossParam:
    """A single row from the ``boss_param`` BDAT table.

    Identical to :class:`EnemyParam` with the following additions:
        atk5 / atk6         — Two extra AI action-slot weights.
        atk5_pow / atk6_pow — Skill power for the extra slots.
        angry               — HP% threshold that triggers rage mode.
        script              — NitroFS file ID of the boss AI script.
    """

    # --- identity ---
    name_id: int
    file: str
    palno: int
    size: int
    shadow: int

    # --- rewards ---
    power: int
    zeni: int
    exp: int
    ap: int

    # --- drops ---
    item1: int
    item2: int
    item3: int
    item4: int

    # --- AI action weights (6 slots for bosses) ---
    atk1: int
    atk2: int
    atk3: int
    atk4: int
    atk5: int
    atk6: int

    # --- skill power per action (6 slots) ---
    atk1_pow: int
    atk2_pow: int
    atk3_pow: int
    atk4_pow: int
    atk5_pow: int
    atk6_pow: int

    # --- level / resources ---
    lv: int
    hp: int
    mp: int

    # --- core stats ---
    str_: int
    def_: int
    rec: int
    tec: int
    agi: int
    luc: int

    # --- status resistances (s8, %) ---
    sleep: int
    poison: int
    blind: int
    bind: int
    stun: int
    panic: int
    freeze: int
    dead: int

    # --- damage-type resistances (s8, %) ---
    physics: int
    slash: int
    blast: int

    # --- elemental resistances (s8, %) ---
    atr_fire: int
    atr_thunder: int
    atr_ice: int

    # --- boss-specific ---
    angry: int          # u8 — HP% rage threshold
    script: int         # u16 — NitroFS AI script file ID
    list: int           # u8


# ──────────────────────────────────────────────────────────────
# Row → dataclass helpers
# ──────────────────────────────────────────────────────────────

# BDAT column names that collide with Python builtins/keywords.
# The dataclass uses a trailing underscore; the BDAT row dict does not.
_RENAME_MAP = {'str': 'str_', 'def': 'def_'}


def _row_to_enemy(row: dict) -> EnemyParam:
    """Convert a raw BDAT row dict into an :class:`EnemyParam`."""
    def g(key: str, default=0):
        py_key = _RENAME_MAP.get(key, key)
        # Return renamed key for dataclass, but read from original BDAT key
        return row.get(key, default)

    return EnemyParam(
        name_id=row.get('name_id', 0),
        file=row.get('file', ''),
        palno=row.get('palno', 0),
        size=row.get('size', 0),
        shadow=row.get('shadow', 0),
        power=row.get('power', 0),
        zeni=row.get('zeni', 0),
        exp=row.get('exp', 0),
        ap=row.get('ap', 0),
        item1=row.get('item1', 0),
        item2=row.get('item2', 0),
        item3=row.get('item3', 0),
        item4=row.get('item4', 0),
        atk1=row.get('atk1', 0),
        atk2=row.get('atk2', 0),
        atk3=row.get('atk3', 0),
        atk4=row.get('atk4', 0),
        atk1_pow=row.get('atk1_pow', 0),
        atk2_pow=row.get('atk2_pow', 0),
        atk3_pow=row.get('atk3_pow', 0),
        atk4_pow=row.get('atk4_pow', 0),
        lv=row.get('lv', 0),
        hp=row.get('hp', 0),
        mp=row.get('mp', 0),
        str_=row.get('str', 0),
        def_=row.get('def', 0),
        rec=row.get('rec', 0),
        tec=row.get('tec', 0),
        agi=row.get('agi', 0),
        luc=row.get('luc', 0),
        sleep=row.get('sleep', 0),
        poison=row.get('poison', 0),
        blind=row.get('blind', 0),
        bind=row.get('bind', 0),
        stun=row.get('stun', 0),
        panic=row.get('panic', 0),
        freeze=row.get('freeze', 0),
        dead=row.get('dead', 0),
        physics=row.get('physics', 0),
        slash=row.get('slash', 0),
        blast=row.get('blast', 0),
        atr_fire=row.get('atr_fire', 0),
        atr_thunder=row.get('atr_thunder', 0),
        atr_ice=row.get('atr_ice', 0),
        list=row.get('list', 0),
    )


def _row_to_boss(row: dict) -> BossParam:
    """Convert a raw BDAT row dict into a :class:`BossParam`."""
    return BossParam(
        name_id=row.get('name_id', 0),
        file=row.get('file', ''),
        palno=row.get('palno', 0),
        size=row.get('size', 0),
        shadow=row.get('shadow', 0),
        power=row.get('power', 0),
        zeni=row.get('zeni', 0),
        exp=row.get('exp', 0),
        ap=row.get('ap', 0),
        item1=row.get('item1', 0),
        item2=row.get('item2', 0),
        item3=row.get('item3', 0),
        item4=row.get('item4', 0),
        atk1=row.get('atk1', 0),
        atk2=row.get('atk2', 0),
        atk3=row.get('atk3', 0),
        atk4=row.get('atk4', 0),
        atk5=row.get('atk5', 0),
        atk6=row.get('atk6', 0),
        atk1_pow=row.get('atk1_pow', 0),
        atk2_pow=row.get('atk2_pow', 0),
        atk3_pow=row.get('atk3_pow', 0),
        atk4_pow=row.get('atk4_pow', 0),
        atk5_pow=row.get('atk5_pow', 0),
        atk6_pow=row.get('atk6_pow', 0),
        lv=row.get('lv', 0),
        hp=row.get('hp', 0),
        mp=row.get('mp', 0),
        str_=row.get('str', 0),
        def_=row.get('def', 0),
        rec=row.get('rec', 0),
        tec=row.get('tec', 0),
        agi=row.get('agi', 0),
        luc=row.get('luc', 0),
        sleep=row.get('sleep', 0),
        poison=row.get('poison', 0),
        blind=row.get('blind', 0),
        bind=row.get('bind', 0),
        stun=row.get('stun', 0),
        panic=row.get('panic', 0),
        freeze=row.get('freeze', 0),
        dead=row.get('dead', 0),
        physics=row.get('physics', 0),
        slash=row.get('slash', 0),
        blast=row.get('blast', 0),
        atr_fire=row.get('atr_fire', 0),
        atr_thunder=row.get('atr_thunder', 0),
        atr_ice=row.get('atr_ice', 0),
        angry=row.get('angry', 0),
        script=row.get('script', 0),
        list=row.get('list', 0),
    )


# ──────────────────────────────────────────────────────────────
# Public loader functions
# ──────────────────────────────────────────────────────────────

def load_enemies(bdat: BdatFile) -> List[EnemyParam]:
    """Load all rows from the ``enemy_param`` table.

    Args:
        bdat: A parsed :class:`BdatFile` containing the battle BDAT data.

    Returns:
        Ordered list of :class:`EnemyParam` — one per enemy row.

    Raises:
        ValueError: If the ``enemy_param`` table is not found.
    """
    table = bdat.get_table('enemy_param')
    if table is None:
        raise ValueError(
            "Table 'enemy_param' not found in BDAT file. "
            f"Available tables: {[t.name for t in bdat.tables]}"
        )
    return [_row_to_enemy(row) for row in table.rows]


def load_bosses(bdat: BdatFile) -> List[BossParam]:
    """Load all rows from the ``boss_param`` table.

    Args:
        bdat: A parsed :class:`BdatFile` containing the battle BDAT data.

    Returns:
        Ordered list of :class:`BossParam` — one per boss row.

    Raises:
        ValueError: If the ``boss_param`` table is not found.
    """
    table = bdat.get_table('boss_param')
    if table is None:
        raise ValueError(
            "Table 'boss_param' not found in BDAT file. "
            f"Available tables: {[t.name for t in bdat.tables]}"
        )
    return [_row_to_boss(row) for row in table.rows]
