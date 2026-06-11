#!/usr/bin/env python3
"""
items.py — Typed data models for Use_Item & Btl_Acc BDAT tables
=================================================================
Column layouts verified via BDAT reader against the NDS ROM:
  Use_Item: 24 bytes/row, 128 rows, 13 columns
  Btl_Acc:  20 bytes/row, 128 rows, 10 columns
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from randomizer.rom_io.bdat_reader import BdatFile


# ──────────────────────────────────────────────────────────────
# Use_Item — consumable items (24 bytes/row)
# ──────────────────────────────────────────────────────────────

@dataclass
class UseItem:
    """A single row from the ``Use_Item`` BDAT table.

    Field semantics:
        name_id — Index into the item-name string table.
        buy     — Shop purchase price (zeni).
        sell    — Shop sell-back price (zeni).
        tpo     — Usage context:  0 = field+battle, 1 = field only, 2 = battle only.
        target  — Targeting mode:
                      0 = single ally, 1 = all allies, 2 = self,
                      3 = single enemy, 5 = all enemies.
        type    — Effect type ID (33 known types — heal HP, cure status, etc.).
        value1  — Primary effect magnitude (s16).
        value2  — Secondary effect magnitude (s16).
        value3  — Tertiary effect magnitude (s16).
        mes     — In-battle message index.
        help_id — Index into the help/description string table.
    """

    name_id: int        # u16
    buy: int            # u32
    sell: int           # u32
    tpo: int            # u8  — 0=both, 1=field, 2=battle
    target: int         # u8  — targeting mode
    type: int           # u8  — effect type (33 types)
    value1: int         # s16
    value2: int         # s16
    value3: int         # s16
    mes: int            # u8  — battle message index
    help_id: int        # u16


# ──────────────────────────────────────────────────────────────
# Btl_Acc — battle accessories / equippable passives (20 bytes/row)
# ──────────────────────────────────────────────────────────────

@dataclass
class BattleAccessory:
    """A single row from the ``Btl_Acc`` BDAT table.

    Field semantics:
        name_id — Index into the item-name string table.
        buy     — Shop purchase price (zeni).
        sell    — Shop sell-back price (zeni).
        who     — Equip restriction:
                      0 = anyone, 1–6 = specific party member only.
        type    — Passive effect type ID (30+ known types).
        value1  — Primary effect magnitude (s16).
        value2  — Secondary effect magnitude (s16).
        help_id — Index into the help/description string table.
    """

    name_id: int        # u16
    buy: int            # u32
    sell: int           # u32
    who: int            # u8  — equip restriction
    type: int           # u8  — effect type
    value1: int         # s16
    value2: int         # s16
    help_id: int        # u16


# ──────────────────────────────────────────────────────────────
# Row → dataclass helpers
# ──────────────────────────────────────────────────────────────

def _row_to_use_item(row: dict) -> UseItem:
    """Convert a raw BDAT row dict into a :class:`UseItem`."""
    return UseItem(
        name_id=row.get('name_id', 0),
        buy=row.get('buy', 0),
        sell=row.get('sell', 0),
        tpo=row.get('tpo', 0),
        target=row.get('target', 0),
        type=row.get('type', 0),
        value1=row.get('value1', 0),
        value2=row.get('value2', 0),
        value3=row.get('value3', 0),
        mes=row.get('mes', 0),
        help_id=row.get('help_id', 0),
    )


def _row_to_accessory(row: dict) -> BattleAccessory:
    """Convert a raw BDAT row dict into a :class:`BattleAccessory`."""
    return BattleAccessory(
        name_id=row.get('name_id', 0),
        buy=row.get('buy', 0),
        sell=row.get('sell', 0),
        who=row.get('who', 0),
        type=row.get('type', 0),
        value1=row.get('value1', 0),
        value2=row.get('value2', 0),
        help_id=row.get('help_id', 0),
    )


# ──────────────────────────────────────────────────────────────
# Public loader functions
# ──────────────────────────────────────────────────────────────

def load_items(bdat: BdatFile) -> List[UseItem]:
    """Load all rows from the ``Use_Item`` table.

    Args:
        bdat: A parsed :class:`BdatFile` containing the relevant BDAT data.

    Returns:
        Ordered list of :class:`UseItem` — one per item row.

    Raises:
        ValueError: If the ``Use_Item`` table is not found.
    """
    table = bdat.get_table('Use_Item')
    if table is None:
        raise ValueError(
            "Table 'Use_Item' not found in BDAT file. "
            f"Available tables: {[t.name for t in bdat.tables]}"
        )
    return [_row_to_use_item(row) for row in table.rows]


def load_accessories(bdat: BdatFile) -> List[BattleAccessory]:
    """Load all rows from the ``Btl_Acc`` table.

    Args:
        bdat: A parsed :class:`BdatFile` containing the relevant BDAT data.

    Returns:
        Ordered list of :class:`BattleAccessory` — one per accessory row.

    Raises:
        ValueError: If the ``Btl_Acc`` table is not found.
    """
    table = bdat.get_table('Btl_Acc')
    if table is None:
        raise ValueError(
            "Table 'Btl_Acc' not found in BDAT file. "
            f"Available tables: {[t.name for t in bdat.tables]}"
        )
    return [_row_to_accessory(row) for row in table.rows]
