#!/usr/bin/env python3
"""
encounters.py — Encounter Randomizer
======================================
Randomizes encounter-related properties in the enemy_param BDAT table.

Since DBZ AotS drives encounters via area scripts (loaded at runtime,
not stored in BDAT), this randomizer focuses on the enemy *properties*
that affect encounter feel:

  1. Drop tables   — item1–item4 columns (what loot enemies give)
  2. Resistances   — status ailments (sleep, poison, etc.) and
                     elemental (physics, slash, blast, fire, thunder, ice)

Modes:
  'vanilla'         — No changes (pass-through)
  'shuffle_drops'   — Shuffle item drops between enemies of similar level (±5)
  'random_resists'  — Randomize all resistance values
  'full'            — All of the above combined
"""

from randomizer.randomizers.base import BaseRandomizer
from randomizer.utils.rng import GameRNG
from randomizer.rom_io.bdat_reader import BdatFile, BdatTable
from randomizer.rom_io.bdat_writer import BdatWriter


# ──────────────────────────────────────────────────────────────
# Column definitions
# ──────────────────────────────────────────────────────────────

# Drop item columns: item ID references into item_param
DROP_COLS = ('item1', 'item2', 'item3', 'item4')

# Status resistance columns (s8, -128 to 127, percent-based: 100 = immune)
STATUS_RESIST_COLS = ('sleep', 'poison', 'blind', 'bind', 'stun',
                      'panic', 'freeze', 'dead')

# Elemental/physical resistance columns (s8, -128 to 127)
# Negative = weakness, 0 = neutral, positive = resistance
ELEM_RESIST_COLS = ('physics', 'slash', 'blast',
                    'atr_fire', 'atr_thunder', 'atr_ice')

# All resistance columns combined
ALL_RESIST_COLS = STATUS_RESIST_COLS + ELEM_RESIST_COLS

# Table to operate on
ENEMY_TABLE = 'enemy_param'


class EncounterRandomizer(BaseRandomizer):
    """
    Randomizes encounter-adjacent data in the enemy_param table.

    Config keys:
        mode:             'vanilla' | 'shuffle_drops' | 'random_resists' | 'full'
        resist_variance:  int (default 30, max random deviation from original)
        preserve_immunes: bool (default True, if a vanilla resist is 100
                          (immune), keep it immune)
        include_bosses:   bool (default False, also process boss_param)
    """

    def __init__(self, rng: GameRNG, config: dict):
        super().__init__(rng, config)
        self.mode: str = config.get('mode', 'vanilla')
        self.resist_variance: int = config.get('resist_variance', 30)
        self.preserve_immunes: bool = config.get('preserve_immunes', True)
        self.include_bosses: bool = config.get('include_bosses', False)

    # ──────────────────────────────────────────────────────────
    # Main entry point
    # ──────────────────────────────────────────────────────────

    def randomize(self, bdat: BdatFile, writer: BdatWriter) -> None:
        """Apply encounter randomization based on the selected mode."""
        self._log(f"=== EncounterRandomizer: mode={self.mode} ===")

        if self.mode == 'vanilla':
            self._log("Mode is 'vanilla' — no changes applied.")
            return

        tables_to_process = [ENEMY_TABLE]
        if self.include_bosses:
            tables_to_process.append('boss_param')

        for table_name in tables_to_process:
            table = bdat.get_table(table_name)
            if table is None:
                self._log(f"WARNING: Table '{table_name}' not found in BDAT")
                continue

            self._log(f"Processing {table_name} ({table.num_rows} rows)")

            if self.mode in ('shuffle_drops', 'full'):
                self._shuffle_drops(table, writer, table_name)

            if self.mode in ('random_resists', 'full'):
                self._randomize_resistances(table, writer, table_name)

        self._log(f"=== EncounterRandomizer complete: "
                  f"{writer.patch_count} cells patched ===")

    # ──────────────────────────────────────────────────────────
    # Drop table shuffling
    # ──────────────────────────────────────────────────────────

    def _shuffle_drops(self, table: BdatTable, writer: BdatWriter,
                       table_name: str) -> None:
        """
        Shuffle item drops between enemies of similar level (±5).

        Each drop slot (item1–item4) is shuffled independently within
        level-similar groups. This preserves the overall drop economy
        while making individual enemies unpredictable.

        Item ID 0 typically means "no drop" — these are shuffled too,
        which means some enemies may gain drops and others may lose them.
        """
        rows = table.rows
        if not rows:
            return

        levels = [row.get('lv', 1) for row in rows]

        for drop_col in DROP_COLS:
            if table.get_column(drop_col) is None:
                continue

            processed = [False] * len(rows)
            idx = 0
            while idx < len(rows):
                if processed[idx]:
                    idx += 1
                    continue

                center_lv = levels[idx]
                group_indices = [
                    i for i in range(len(rows))
                    if not processed[i]
                    and abs(levels[i] - center_lv) <= 5
                ]

                if len(group_indices) < 2:
                    for gi in group_indices:
                        processed[gi] = True
                    idx += 1
                    continue

                # Extract drop values, shuffle, write back
                values = [rows[i].get(drop_col, 0) for i in group_indices]
                self.rng.shuffle(values)

                for gi, new_val in zip(group_indices, values):
                    old_val = rows[gi].get(drop_col, 0)
                    writer.set_value(table_name, gi, drop_col, new_val)
                    if old_val != new_val:
                        self._log(f"  [{table_name}][{gi}] {drop_col}: "
                                  f"{old_val} → {new_val} (drop shuffle)")
                    processed[gi] = True

                idx += 1

    # ──────────────────────────────────────────────────────────
    # Resistance randomization
    # ──────────────────────────────────────────────────────────

    def _randomize_resistances(self, table: BdatTable, writer: BdatWriter,
                               table_name: str) -> None:
        """
        Randomize resistance values using variance-based adjustment.

        Each resistance is adjusted by a random delta in [-variance, +variance].
        Values are clamped to s8 range (-128 to 127).
        If preserve_immunes is True, any vanilla value of 100 (immune) is kept.
        """
        variance = self.resist_variance
        for row_idx, row in enumerate(table.rows):
            for resist_col in ALL_RESIST_COLS:
                if table.get_column(resist_col) is None:
                    continue

                old_val = row.get(resist_col, 0)

                # Preserve intentional immunities (100 = immune in this game)
                if self.preserve_immunes and old_val == 100:
                    continue

                # Variance-based: original ± random delta
                delta = self.rng.randint(-variance, variance)
                new_val = old_val + delta

                # Clamp to s8 range (-128 to 127)
                new_val = max(-128, min(127, new_val))

                writer.set_value(table_name, row_idx, resist_col, new_val)
                if old_val != new_val:
                    self._log(f"  [{table_name}][{row_idx}] {resist_col}: "
                              f"{old_val} -> {new_val} (resist rng)")

