#!/usr/bin/env python3
"""
drop_shuffle.py — Enemy Drop Shuffle Randomizer
===================================================
Shuffles/randomizes which items enemies drop.

Tables: enemy_param (173 rows, item1-4), boss_param (55 rows, item1-3)
"""

from randomizer.randomizers.base import BaseRandomizer
from randomizer.rom_io.bdat_reader import BdatFile
from randomizer.rom_io.bdat_writer import BdatWriter

ENEMY_TABLE = "enemy_param"
BOSS_TABLE = "boss_param"

ENEMY_DROP_COLS = ["item1", "item2", "item3", "item4"]
BOSS_DROP_COLS = ["item1", "item2", "item3"]


class DropShuffleRandomizer(BaseRandomizer):
    """
    Shuffles or randomizes enemy item drops.

    Config keys:
        mode:            'vanilla' | 'shuffle' | 'random' | 'generous'
        include_bosses:  bool (default False)
    """

    def __init__(self, rng, config: dict):
        super().__init__(rng, config)
        self.mode = config.get("mode", "shuffle")
        self.include_bosses = config.get("include_bosses", False)

    def randomize(self, bdat: BdatFile, writer: BdatWriter) -> None:
        self._log(f"=== DropShuffleRandomizer: mode={self.mode} ===")

        if self.mode == "vanilla":
            self._log("Mode is 'vanilla' — no changes.")
            return

        # Process enemy_param
        enemy_table = bdat.get_table(ENEMY_TABLE)
        if enemy_table:
            self._process_table(enemy_table, writer, ENEMY_TABLE,
                                ENEMY_DROP_COLS)

        # Process boss_param if enabled
        if self.include_bosses:
            boss_table = bdat.get_table(BOSS_TABLE)
            if boss_table:
                self._process_table(boss_table, writer, BOSS_TABLE,
                                    BOSS_DROP_COLS)

        self._log(f"=== DropShuffleRandomizer complete ===")

    def _process_table(self, table, writer: BdatWriter,
                       table_name: str, drop_cols: list) -> None:
        """Process one table's drops."""
        rows = table.rows

        # Collect all non-zero item IDs and their positions
        item_pool = []
        filled_slots = []   # (row_idx, col_name) for non-zero slots
        empty_slots = []    # (row_idx, col_name) for zero slots

        for row_idx, row in enumerate(rows):
            for col in drop_cols:
                item_id = row.get(col, 0)
                if item_id > 0:
                    item_pool.append(item_id)
                    filled_slots.append((row_idx, col))
                else:
                    empty_slots.append((row_idx, col))

        if not item_pool:
            self._log(f"  {table_name}: No drops found")
            return

        unique_items = len(set(item_pool))
        self._log(f"  {table_name}: {len(item_pool)} drop slots, "
                  f"{unique_items} unique items")

        if self.mode == "shuffle":
            self._shuffle_drops(writer, table_name, item_pool, filled_slots)

        elif self.mode == "random":
            self._random_drops(writer, table_name, item_pool, filled_slots)

        elif self.mode == "generous":
            self._generous_drops(writer, table_name, item_pool,
                                 filled_slots, empty_slots)

    def _shuffle_drops(self, writer, table_name, item_pool, filled_slots):
        """Shuffle the item pool and redistribute to same slots."""
        shuffled = list(item_pool)
        self.rng.shuffle(shuffled)

        changes = 0
        for i, (row_idx, col) in enumerate(filled_slots):
            if shuffled[i] != item_pool[i]:
                changes += 1
            writer.set_value(table_name, row_idx, col, shuffled[i])

        self._log(f"    Shuffled {len(filled_slots)} slots "
                  f"({changes} changed)")

    def _random_drops(self, writer, table_name, item_pool, filled_slots):
        """Assign random items from pool to each filled slot."""
        unique_pool = list(set(item_pool))

        for row_idx, col in filled_slots:
            new_item = self.rng.choose(unique_pool)
            writer.set_value(table_name, row_idx, col, new_item)

        self._log(f"    Randomized {len(filled_slots)} slots from "
                  f"{len(unique_pool)} unique items")

    def _generous_drops(self, writer, table_name, item_pool,
                        filled_slots, empty_slots):
        """Fill ALL slots (including empty) with random items."""
        unique_pool = list(set(item_pool))

        # Fill existing slots with random items
        for row_idx, col in filled_slots:
            new_item = self.rng.choose(unique_pool)
            writer.set_value(table_name, row_idx, col, new_item)

        # Also fill empty slots
        filled_empty = 0
        for row_idx, col in empty_slots:
            new_item = self.rng.choose(unique_pool)
            writer.set_value(table_name, row_idx, col, new_item)
            filled_empty += 1

        self._log(f"    Filled {len(filled_slots)} existing + "
                  f"{filled_empty} empty slots")
