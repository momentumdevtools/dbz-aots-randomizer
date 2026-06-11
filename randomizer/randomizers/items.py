#!/usr/bin/env python3
"""
items.py — Item / Capsule / Equipment Randomizer
===================================================
Randomizes the Use_Item, Btl_Acc and Pt_Eqp BDAT tables.

Modes:
  'vanilla'         — No changes (pass-through)
  'shuffle_effects' — Shuffle value1/value2/value3 between items of
                      the same 'type', keeping item archetypes consistent
  'random_prices'   — Randomize buy/sell prices with configurable variance
  'full'            — Both shuffle_effects and random_prices

Safety constraints (never mutated):
  - name_id, help_id, mes       — text/description references
  - tpo, target                 — usage context & targeting logic
  - who (Btl_Acc)               — equip restrictions

Verified against BDAT dumps:
  02_Use_Item.json  — 128 rows, 24 bytes/row, columns: name_id buy sell
                      tpo target type value1(s16) value2(s16) value3(s16)
                      mes help_id
  03_Btl_Acc.json   — 128 rows, 20 bytes/row, columns: name_id buy sell
                      who type value1(s16) value2(s16) help_id
  04_Pt_Eqp.json    — 48 rows  (training equipment, same shape as Btl_Acc)
"""

from collections import defaultdict
from typing import Dict, List, Tuple

from randomizer.randomizers.base import BaseRandomizer
from randomizer.utils.rng import GameRNG
from randomizer.rom_io.bdat_reader import BdatFile, BdatTable
from randomizer.rom_io.bdat_writer import BdatWriter


# ──────────────────────────────────────────────────────────────
# Table / column constants (verified from BDAT dumps)
# ──────────────────────────────────────────────────────────────

USE_ITEM_TABLE = 'Use_Item'
BTL_ACC_TABLE = 'Btl_Acc'
PT_EQP_TABLE = 'Pt_Eqp'

# Effect value columns per table
USE_ITEM_VALUE_COLS = ('value1', 'value2', 'value3')
ACC_VALUE_COLS = ('value1', 'value2')

# Price columns (shared across all three tables)
PRICE_COLS = ('buy', 'sell')

# s16 value range (effect magnitudes)
S16_MIN = -32768
S16_MAX = 32767

# u32 price limits
PRICE_MIN = 0
PRICE_MAX = 0xFFFFFFFF  # u32 max — practical prices are much lower


class ItemRandomizer(BaseRandomizer):
    """
    Randomizes item effect values and prices across the three item tables.

    Config keys:
        mode:            'vanilla' | 'shuffle_effects' | 'random_prices' | 'full'
        price_variance:  float (default 0.5, meaning ±50% — price is scaled
                         between 0.5× and 1.5× of original)
    """

    def __init__(self, rng: GameRNG, config: dict):
        super().__init__(rng, config)
        self.mode: str = config.get('mode', 'vanilla')
        self.price_variance: float = config.get('price_variance', 0.5)

    # ──────────────────────────────────────────────────────────
    # Main entry point
    # ──────────────────────────────────────────────────────────

    def randomize(self, bdat: BdatFile, writer: BdatWriter) -> None:
        """Apply item randomization based on the selected mode."""
        self._log(f"=== ItemRandomizer: mode={self.mode} ===")

        if self.mode == 'vanilla':
            self._log("Mode is 'vanilla' — no changes applied.")
            return

        do_effects = self.mode in ('shuffle_effects', 'full')
        do_prices = self.mode in ('random_prices', 'full')

        # ── Use_Item ──
        use_item_table = bdat.get_table(USE_ITEM_TABLE)
        if use_item_table is not None:
            self._log(f"Processing {USE_ITEM_TABLE} "
                      f"({use_item_table.num_rows} rows)")
            if do_effects:
                self._shuffle_effects(
                    use_item_table, writer, USE_ITEM_TABLE,
                    USE_ITEM_VALUE_COLS,
                )
            if do_prices:
                self._randomize_prices(
                    use_item_table, writer, USE_ITEM_TABLE,
                )
        else:
            self._log(f"WARNING: Table '{USE_ITEM_TABLE}' not found in BDAT")

        # ── Btl_Acc ──
        btl_acc_table = bdat.get_table(BTL_ACC_TABLE)
        if btl_acc_table is not None:
            self._log(f"Processing {BTL_ACC_TABLE} "
                      f"({btl_acc_table.num_rows} rows)")
            if do_effects:
                self._shuffle_effects(
                    btl_acc_table, writer, BTL_ACC_TABLE,
                    ACC_VALUE_COLS,
                )
            if do_prices:
                self._randomize_prices(
                    btl_acc_table, writer, BTL_ACC_TABLE,
                )
        else:
            self._log(f"WARNING: Table '{BTL_ACC_TABLE}' not found in BDAT")

        # ── Pt_Eqp ──
        pt_eqp_table = bdat.get_table(PT_EQP_TABLE)
        if pt_eqp_table is not None:
            self._log(f"Processing {PT_EQP_TABLE} "
                      f"({pt_eqp_table.num_rows} rows)")
            if do_effects:
                self._shuffle_effects(
                    pt_eqp_table, writer, PT_EQP_TABLE,
                    ACC_VALUE_COLS,
                )
            if do_prices:
                self._randomize_prices(
                    pt_eqp_table, writer, PT_EQP_TABLE,
                )
        else:
            self._log(f"WARNING: Table '{PT_EQP_TABLE}' not found in BDAT")

        self._log(f"=== ItemRandomizer complete ===")

    # ──────────────────────────────────────────────────────────
    # Effect value shuffling (within same 'type' group)
    # ──────────────────────────────────────────────────────────

    def _shuffle_effects(
        self,
        table: BdatTable,
        writer: BdatWriter,
        table_name: str,
        value_cols: Tuple[str, ...],
    ) -> None:
        """
        Shuffle effect values between items sharing the same 'type'.

        This keeps each item archetype consistent (a healing item stays
        healing) but redistributes the magnitudes across the group.
        For example, all type-1 (HP heal) items swap their value1/value2/value3
        with each other — so a Senzu Bean might now heal 150 HP while a
        small herb heals 1500.

        Each value column is shuffled independently so items can receive
        a mix of values from different donors within the type group.
        """
        rows = table.rows
        if not rows:
            return

        # Group row indices by their 'type' value
        type_groups: Dict[int, List[int]] = defaultdict(list)
        for idx, row in enumerate(rows):
            item_type = row.get('type', 0)
            type_groups[item_type].append(idx)

        for item_type, indices in sorted(type_groups.items()):
            if len(indices) < 2:
                continue  # nothing to shuffle with one item

            for col in value_cols:
                if table.get_column(col) is None:
                    continue

                # Extract current values for this column in this type group
                values = [rows[i].get(col, 0) for i in indices]
                self.rng.shuffle(values)

                # Write back shuffled values
                for row_idx, new_val in zip(indices, values):
                    old_val = rows[row_idx].get(col, 0)
                    writer.set_value(table_name, row_idx, col, new_val)
                    if old_val != new_val:
                        self._log(
                            f"  [{table_name}][{row_idx}] {col}: "
                            f"{old_val} → {new_val} "
                            f"(type {item_type} shuffle)"
                        )

    # ──────────────────────────────────────────────────────────
    # Price randomization
    # ──────────────────────────────────────────────────────────

    def _randomize_prices(
        self,
        table: BdatTable,
        writer: BdatWriter,
        table_name: str,
    ) -> None:
        """
        Randomize buy/sell prices within a configurable variance.

        Each price is scaled by a random factor in
        [1 - variance, 1 + variance]. For the default variance of 0.5
        this means 50%–150% of the original price.

        Special cases:
          - Zero prices stay zero (non-purchasable / quest-only items).
          - Sell price is clamped to never exceed buy price (prevents
            infinite zeni exploits).
          - Minimum non-zero price is 1.
        """
        rows = table.rows
        if not rows:
            return

        variance = self.price_variance
        min_scale = max(0.01, 1.0 - variance)  # at least 1% to avoid zeroing
        max_scale = 1.0 + variance

        for row_idx, row in enumerate(rows):
            old_buy = row.get('buy', 0)
            old_sell = row.get('sell', 0)

            # Skip non-purchasable items (buy==0 means not in shops)
            if old_buy == 0 and old_sell == 0:
                continue

            # Randomize buy price
            if old_buy > 0:
                new_buy = self.rng.scale_value(
                    old_buy,
                    min_scale, max_scale,
                    clamp_min=1, clamp_max=999999,
                )
            else:
                new_buy = 0

            # Randomize sell price
            if old_sell > 0:
                new_sell = self.rng.scale_value(
                    old_sell,
                    min_scale, max_scale,
                    clamp_min=1, clamp_max=999999,
                )
            else:
                new_sell = 0

            # Clamp sell ≤ buy (prevent infinite zeni exploits)
            if new_buy > 0 and new_sell > new_buy:
                new_sell = new_buy

            # Write back
            if old_buy != new_buy:
                writer.set_value(table_name, row_idx, 'buy', new_buy)
                self._log(
                    f"  [{table_name}][{row_idx}] buy: "
                    f"{old_buy} → {new_buy}"
                )

            if old_sell != new_sell:
                writer.set_value(table_name, row_idx, 'sell', new_sell)
                self._log(
                    f"  [{table_name}][{row_idx}] sell: "
                    f"{old_sell} → {new_sell}"
                )
