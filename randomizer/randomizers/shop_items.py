#!/usr/bin/env python3
"""
shop_items.py — Shop & Item Randomizer
========================================
Randomizes item prices and equipment stats across the three shop-related
BDAT tables: Use_Item, Btl_Acc, and Pt_Eqp.

Modes:
  'vanilla'         — No changes (pass-through)
  'shuffle_prices'  — Collect all non-zero buy prices per table, shuffle
                       them across rows, set sell = buy // 2
  'random_prices'   — Scale each non-zero buy price by a random factor
                       within (1 ± price_variance), set sell = buy // 2
  'chaos'           — Random prices PLUS:
                         • Btl_Acc: shuffle value2 (stat bonus) within
                           items of same 'type'
                         • Use_Item: scale value1 (heal amount etc.) by ±50%
                         • Pt_Eqp: shuffle value1/value2 within table

Safety constraints (never mutated):
  - name_id, help_id, mes — text/description references
  - tpo, target           — usage context & targeting logic
  - who (Btl_Acc)         — equip restrictions

Verified against BDAT dumps:
  02_Use_Item.json — 128 rows, columns: name_id buy sell tpo target
                     type value1(s16) value2(s16) value3(s16) mes help_id
  03_Btl_Acc.json  — 128 rows, columns: name_id buy sell who type
                     value1(s16) value2(s16) help_id
  04_Pt_Eqp.json   — 48 rows  (training equipment)
"""

from collections import defaultdict
from typing import List, Tuple

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

# Value range limits
U16_MAX = 65535
S16_MIN = -32768
S16_MAX = 32767

# Maximum rows per table (from BDAT schema)
USE_ITEM_ROWS = 128
BTL_ACC_ROWS = 128
PT_EQP_ROWS = 48

# Number of sample log entries to emit per table (avoid log spam)
LOG_SAMPLE_COUNT = 8


class ShopItemRandomizer(BaseRandomizer):
    """
    Randomizes shop prices and equipment stats.

    Config keys:
        mode:            'vanilla' | 'shuffle_prices' | 'random_prices' | 'chaos'
        price_variance:  float (default 0.5, meaning ±50%)
    """

    def __init__(self, rng: GameRNG, config: dict):
        super().__init__(rng, config)
        self.mode: str = config.get('mode', 'vanilla')
        self.price_variance: float = config.get('price_variance', 0.5)

    # ──────────────────────────────────────────────────────────
    # Main entry point
    # ──────────────────────────────────────────────────────────

    def randomize(self, bdat: BdatFile, writer: BdatWriter) -> None:
        """Apply shop/item randomization based on the selected mode."""
        self._log(f"=== ShopItemRandomizer: mode={self.mode} ===")

        if self.mode == 'vanilla':
            self._log("Mode is 'vanilla' — no changes applied.")
            return

        # ── Use_Item ──
        use_item_table = bdat.get_table(USE_ITEM_TABLE)
        if use_item_table is not None:
            self._log(f"Processing {USE_ITEM_TABLE} "
                      f"({use_item_table.num_rows} rows)")
            self._process_table(use_item_table, writer, USE_ITEM_TABLE)
        else:
            self._log(f"WARNING: Table '{USE_ITEM_TABLE}' not found in BDAT")

        # ── Btl_Acc ──
        btl_acc_table = bdat.get_table(BTL_ACC_TABLE)
        if btl_acc_table is not None:
            self._log(f"Processing {BTL_ACC_TABLE} "
                      f"({btl_acc_table.num_rows} rows)")
            self._process_table(btl_acc_table, writer, BTL_ACC_TABLE)
        else:
            self._log(f"WARNING: Table '{BTL_ACC_TABLE}' not found in BDAT")

        # ── Pt_Eqp ──
        pt_eqp_table = bdat.get_table(PT_EQP_TABLE)
        if pt_eqp_table is not None:
            self._log(f"Processing {PT_EQP_TABLE} "
                      f"({pt_eqp_table.num_rows} rows)")
            self._process_table(pt_eqp_table, writer, PT_EQP_TABLE)
        else:
            self._log(f"WARNING: Table '{PT_EQP_TABLE}' not found in BDAT")

        self._log(f"=== ShopItemRandomizer complete: "
                  f"{writer.patch_count} cells patched ===")

    # ──────────────────────────────────────────────────────────
    # Per-table dispatcher
    # ──────────────────────────────────────────────────────────

    def _process_table(self, table: BdatTable, writer: BdatWriter,
                       table_name: str) -> None:
        """Dispatch to the correct mode handler for a given table."""
        if self.mode == 'shuffle_prices':
            self._mode_shuffle_prices(table, writer, table_name)
        elif self.mode == 'random_prices':
            self._mode_random_prices(table, writer, table_name)
        elif self.mode == 'chaos':
            self._mode_chaos(table, writer, table_name)
        else:
            self._log(f"WARNING: Unknown mode '{self.mode}', skipping")

    # ──────────────────────────────────────────────────────────
    # MODE: shuffle_prices
    # ──────────────────────────────────────────────────────────

    def _mode_shuffle_prices(self, table: BdatTable, writer: BdatWriter,
                             table_name: str) -> None:
        """
        Collect all non-zero buy prices, Fisher-Yates shuffle them,
        redistribute across the same rows.  Sell = buy // 2.
        """
        rows = table.rows
        if not rows:
            return

        # Collect indices and buy values for non-zero-price items
        price_indices: List[int] = []
        buy_values: List[int] = []

        for idx, row in enumerate(rows):
            buy = row.get('buy', 0)
            if buy > 0:
                price_indices.append(idx)
                buy_values.append(buy)

        if len(price_indices) < 2:
            self._log(f"  {table_name}: fewer than 2 priced items, skipping shuffle")
            return

        # Shuffle the buy values
        self.rng.shuffle(buy_values)

        changes_logged = 0
        for row_idx, new_buy in zip(price_indices, buy_values):
            old_buy = rows[row_idx].get('buy', 0)
            old_sell = rows[row_idx].get('sell', 0)

            # Clamp buy to u16
            new_buy = max(1, min(U16_MAX, new_buy))
            new_sell = new_buy // 2

            writer.set_value(table_name, row_idx, 'buy', new_buy)
            writer.set_value(table_name, row_idx, 'sell', new_sell)

            if changes_logged < LOG_SAMPLE_COUNT and old_buy != new_buy:
                self._log(
                    f"  [{table_name}][{row_idx}] buy: {old_buy} → {new_buy}, "
                    f"sell: {old_sell} → {new_sell} (shuffle)"
                )
                changes_logged += 1

        total_changed = sum(
            1 for ri, nb in zip(price_indices, buy_values)
            if rows[ri].get('buy', 0) != nb
        )
        self._log(f"  {table_name}: shuffled {len(price_indices)} prices "
                  f"({total_changed} changed)")

    # ──────────────────────────────────────────────────────────
    # MODE: random_prices
    # ──────────────────────────────────────────────────────────

    def _mode_random_prices(self, table: BdatTable, writer: BdatWriter,
                            table_name: str) -> None:
        """
        Scale each non-zero buy price by random factor (1 ± price_variance).
        Sell = buy // 2.  Clamp buy to 1–65535.
        """
        rows = table.rows
        if not rows:
            return

        variance = self.price_variance
        min_scale = max(0.01, 1.0 - variance)
        max_scale = 1.0 + variance

        changes_logged = 0
        for row_idx, row in enumerate(rows):
            old_buy = row.get('buy', 0)

            if old_buy <= 0:
                continue

            # Scale buy price using GameRNG
            new_buy = self.rng.scale_value(
                old_buy, min_scale, max_scale,
                clamp_min=1, clamp_max=U16_MAX,
            )
            new_sell = new_buy // 2
            old_sell = row.get('sell', 0)

            writer.set_value(table_name, row_idx, 'buy', new_buy)
            writer.set_value(table_name, row_idx, 'sell', new_sell)

            if changes_logged < LOG_SAMPLE_COUNT and old_buy != new_buy:
                ratio = new_buy / old_buy if old_buy else 0
                self._log(
                    f"  [{table_name}][{row_idx}] buy: {old_buy} → {new_buy} "
                    f"(×{ratio:.2f}), sell: {old_sell} → {new_sell}"
                )
                changes_logged += 1

    # ──────────────────────────────────────────────────────────
    # MODE: chaos
    # ──────────────────────────────────────────────────────────

    def _mode_chaos(self, table: BdatTable, writer: BdatWriter,
                    table_name: str) -> None:
        """
        Random prices AND shuffled/scaled equipment effect values.

        Price handling:
          Same as random_prices mode.

        Effect handling (table-specific):
          • Btl_Acc: shuffle value2 (stat bonus) among items of same 'type'
          • Use_Item: scale value1 (heal/effect amount) by ±50%
          • Pt_Eqp: shuffle value1 and value2 across all rows
        """
        # --- Step 1: Randomize prices (same as random_prices) ---
        self._mode_random_prices(table, writer, table_name)

        # --- Step 2: Table-specific effect mutations ---
        if table_name == BTL_ACC_TABLE:
            self._chaos_shuffle_acc_value2(table, writer, table_name)
        elif table_name == USE_ITEM_TABLE:
            self._chaos_scale_use_item_value1(table, writer, table_name)
        elif table_name == PT_EQP_TABLE:
            self._chaos_shuffle_eqp_values(table, writer, table_name)

    def _chaos_shuffle_acc_value2(self, table: BdatTable,
                                  writer: BdatWriter,
                                  table_name: str) -> None:
        """
        Shuffle 'value2' (stat bonus amount) between Btl_Acc items
        that share the same 'type'.

        E.g., all type-3 (STR bonus) accessories swap their bonus values,
        so a +5 STR ring might become +20 and vice versa.
        """
        rows = table.rows
        if not rows:
            return

        if table.get_column('value2') is None:
            self._log(f"  {table_name}: column 'value2' not found, skipping")
            return

        # Group row indices by type
        type_groups: dict[int, List[int]] = defaultdict(list)
        for idx, row in enumerate(rows):
            item_type = row.get('type', 0)
            type_groups[item_type].append(idx)

        for item_type, indices in sorted(type_groups.items()):
            if len(indices) < 2:
                continue

            values = [rows[i].get('value2', 0) for i in indices]
            self.rng.shuffle(values)

            for row_idx, new_val in zip(indices, values):
                old_val = rows[row_idx].get('value2', 0)
                # Clamp to s16 range
                new_val = max(S16_MIN, min(S16_MAX, new_val))
                writer.set_value(table_name, row_idx, 'value2', new_val)
                if old_val != new_val:
                    self._log(
                        f"  [{table_name}][{row_idx}] value2: "
                        f"{old_val} → {new_val} (type {item_type} shuffle)"
                    )

    def _chaos_scale_use_item_value1(self, table: BdatTable,
                                     writer: BdatWriter,
                                     table_name: str) -> None:
        """
        Scale Use_Item 'value1' (heal amount, buff magnitude, etc.) by ±50%.
        Zero values stay zero (dummy/empty items).
        """
        rows = table.rows
        if not rows:
            return

        if table.get_column('value1') is None:
            self._log(f"  {table_name}: column 'value1' not found, skipping")
            return

        changes_logged = 0
        for row_idx, row in enumerate(rows):
            old_val = row.get('value1', 0)
            if old_val == 0:
                continue

            # Scale by ±50% (0.5x–1.5x), clamp to s16
            new_val = self.rng.scale_value(
                old_val, 0.5, 1.5,
                clamp_min=S16_MIN, clamp_max=S16_MAX,
            )

            writer.set_value(table_name, row_idx, 'value1', new_val)
            if changes_logged < LOG_SAMPLE_COUNT and old_val != new_val:
                self._log(
                    f"  [{table_name}][{row_idx}] value1: "
                    f"{old_val} → {new_val} (chaos scale)"
                )
                changes_logged += 1

    def _chaos_shuffle_eqp_values(self, table: BdatTable,
                                  writer: BdatWriter,
                                  table_name: str) -> None:
        """
        Shuffle value1 and value2 independently across all Pt_Eqp rows.
        Training equipment is a small table (48 rows) so we shuffle globally.
        """
        rows = table.rows
        if not rows:
            return

        for col_name in ('value1', 'value2'):
            if table.get_column(col_name) is None:
                continue

            # Collect non-zero indices and values
            indices: List[int] = []
            values: List[int] = []
            for idx, row in enumerate(rows):
                val = row.get(col_name, 0)
                if val != 0:
                    indices.append(idx)
                    values.append(val)

            if len(indices) < 2:
                continue

            self.rng.shuffle(values)

            for row_idx, new_val in zip(indices, values):
                old_val = rows[row_idx].get(col_name, 0)
                new_val = max(S16_MIN, min(S16_MAX, new_val))
                writer.set_value(table_name, row_idx, col_name, new_val)
                if old_val != new_val:
                    self._log(
                        f"  [{table_name}][{row_idx}] {col_name}: "
                        f"{old_val} → {new_val} (chaos shuffle)"
                    )
