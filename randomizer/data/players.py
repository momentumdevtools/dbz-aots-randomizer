#!/usr/bin/env python3
"""
players.py — Typed data models for the player_param BDAT table
================================================================
Column layout verified from BDAT dump (8 rows, 48 bytes/row, 45 columns).

The player_param table defines base stats, level-up growth curves, and
innate resistances for all 6 playable characters (+2 NPC guest slots).

Growth system:
    - hpup/strup/etc.   = stat gain per level up to level `exlv`
    - hpup2/strup2/etc. = stat gain per level after `exlv`
    This creates a two-phase growth curve (early game vs late game).

Player IDs (name_id):
    1 = Goku     (starts Lv4, high STR, Fire+10/Ice-10)
    2 = Gohan    (starts Lv1, balanced, all elements -10)
    3 = Piccolo  (starts Lv19, high TEC, Poison+10/Slash-30)
    4 = Krillin  (starts Lv1, balanced, Bind+10)
    5 = Tenshinhan (starts Lv1, high STR/TEC, Blast+10/Thunder+10)
    6 = Yamcha   (starts Lv1, high AGI, Panic-10/Dead-10)
    7 = NPC Guest A (Lv20, STR=60, panic/dead immune - likely Vegeta)
    8 = NPC Guest B (Lv20, all 30, panic/dead immune - likely Chiaotzu)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from randomizer.rom_io.bdat_reader import BdatFile


CHARACTER_NAMES = {
    1: "Goku",
    2: "Gohan",
    3: "Piccolo",
    4: "Krillin",
    5: "Tenshinhan",
    6: "Yamcha",
    7: "Guest A",
    8: "Guest B",
}

# Playable character indices (0-based row index into player_param)
PLAYABLE_INDICES = [0, 1, 2, 3, 4, 5]  # Rows 0-5 = Goku through Yamcha
NPC_INDICES = [6, 7]                     # Rows 6-7 = Guest NPCs


@dataclass
class PlayerParam:
    """A single row from the ``player_param`` BDAT table."""

    # --- identity ---
    name_id: int        # u16 — character_name index
    size: int           # u8 — sprite size class
    shadow: int         # u8 — shadow type

    # --- starting stats ---
    lv: int             # u8  — starting level
    ap: int             # u16 — starting AP
    hp: int             # u16 — starting HP
    mp: int             # u16 — starting MP
    str_: int           # u8  — base STR
    def_: int           # u8  — base DEF
    rec: int            # u8  — base REC
    tec: int            # u8  — base TEC
    agi: int            # u8  — base AGI
    luc: int            # u8  — base LUC

    # --- growth phase 1 (per level, up to exlv) ---
    hpup: int           # u8
    mpup: int           # u8
    strup: int          # u8
    defup: int          # u8
    recup: int          # u8
    tecup: int          # u8
    agiup: int          # u8
    lucup: int          # u8

    # --- growth transition level ---
    exlv: int           # u8 — level at which growth curve switches

    # --- growth phase 2 (per level, after exlv) ---
    hpup2: int          # u8
    mpup2: int          # u8
    strup2: int         # u8
    defup2: int         # u8
    recup2: int         # u8
    tecup2: int         # u8
    agiup2: int         # u8
    lucup2: int         # u8

    # --- status resistances (s8, %) ---
    poison: int
    sleep: int
    dark: int           # NDS uses "dark" instead of "blind"
    bind: int
    stan: int           # NDS uses "stan" instead of "stun"
    panic: int
    freez: int          # NDS uses "freez" instead of "freeze"
    dead: int

    # --- damage-type resistances (s8, %) ---
    physics: int
    slash: int
    blast: int

    # --- elemental resistances (s8, %) ---
    atr_fire: int
    atr_thunder: int
    atr_ice: int

    @property
    def display_name(self) -> str:
        return CHARACTER_NAMES.get(self.name_id, f"Character {self.name_id}")

    @property
    def is_playable(self) -> bool:
        return self.name_id in range(1, 7)

    @property
    def is_npc_guest(self) -> bool:
        return self.name_id in (7, 8)

    @property
    def total_growth_phase1(self) -> int:
        """Sum of all phase-1 stat gains per level."""
        return self.strup + self.defup + self.recup + self.tecup + self.agiup + self.lucup

    @property
    def total_growth_phase2(self) -> int:
        """Sum of all phase-2 stat gains per level."""
        return self.strup2 + self.defup2 + self.recup2 + self.tecup2 + self.agiup2 + self.lucup2


def _row_to_player(row: dict) -> PlayerParam:
    """Convert a raw BDAT row dict into a PlayerParam."""
    return PlayerParam(
        name_id=row.get('name_id', 0),
        size=row.get('size', 0),
        shadow=row.get('shadow', 0),
        lv=row.get('lv', 1),
        ap=row.get('ap', 0),
        hp=row.get('hp', 0),
        mp=row.get('mp', 0),
        str_=row.get('str', 0),
        def_=row.get('def', 0),
        rec=row.get('rec', 0),
        tec=row.get('tec', 0),
        agi=row.get('agi', 0),
        luc=row.get('luc', 0),
        hpup=row.get('hpup', 0),
        mpup=row.get('mpup', 0),
        strup=row.get('strup', 0),
        defup=row.get('defup', 0),
        recup=row.get('recup', 0),
        tecup=row.get('tecup', 0),
        agiup=row.get('agiup', 0),
        lucup=row.get('lucup', 0),
        exlv=row.get('exlv', 0),
        hpup2=row.get('hpup2', 0),
        mpup2=row.get('mpup2', 0),
        strup2=row.get('strup2', 0),
        defup2=row.get('defup2', 0),
        recup2=row.get('recup2', 0),
        tecup2=row.get('tecup2', 0),
        agiup2=row.get('agiup2', 0),
        lucup2=row.get('lucup2', 0),
        poison=row.get('poison', 0),
        sleep=row.get('sleep', 0),
        dark=row.get('dark', 0),
        bind=row.get('bind', 0),
        stan=row.get('stan', 0),
        panic=row.get('panic', 0),
        freez=row.get('freez', 0),
        dead=row.get('dead', 0),
        physics=row.get('physics', 0),
        slash=row.get('slash', 0),
        blast=row.get('blast', 0),
        atr_fire=row.get('atr_fire', 0),
        atr_thunder=row.get('atr_thunder', 0),
        atr_ice=row.get('atr_ice', 0),
    )


def load_players(bdat: BdatFile) -> List[PlayerParam]:
    """Load all rows from the ``player_param`` table.

    Returns:
        Ordered list of PlayerParam — index 0-5 are playable characters,
        6-7 are NPC guests.

    Raises:
        ValueError: If the ``player_param`` table is not found.
    """
    table = bdat.get_table('player_param')
    if table is None:
        raise ValueError(
            "Table 'player_param' not found in BDAT file. "
            f"Available tables: {[t.name for t in bdat.tables]}"
        )
    return [_row_to_player(row) for row in table.rows]
