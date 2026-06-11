#!/usr/bin/env python3
"""
enemy_stats.py — Enemy Stat Randomizer
========================================
Randomizes numeric combat stats in the enemy_param (173 rows) and
boss_param (55 rows) BDAT tables.

Modes:
  'shuffle' — Shuffle stats between enemies of similar level (±5)
  'scale'   — Scale each stat by a random factor (default 0.75–1.25)
  'chaos'   — Completely random stats within level-appropriate bounds

Protected columns (NEVER modified):
  Visual:     name_id, file, palno, size, shadow
  AI:         atk1–atk4, atk1_pow–atk4_pow
  Level:      lv  (drives encounter selection; shuffling this would
              break progression)

Type limits (enforced by BdatWriter._clamp_value):
  u32 → hp, exp, zeni   (0–4294967295)
  u16 → str, def, rec, tec, agi, luc, ap  (0–65535)
  u8  → lv              (0–255, but never touched)
"""

from randomizer.randomizers.base import BaseRandomizer
from randomizer.utils.rng import GameRNG
from randomizer.rom_io.bdat_reader import BdatFile, BdatTable
from randomizer.rom_io.bdat_writer import BdatWriter


# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────

# Stat columns we're allowed to randomize
STAT_COLS = ('hp', 'mp', 'str', 'def', 'rec', 'tec', 'agi', 'luc',
             'exp', 'zeni', 'ap')

# Type upper bounds for clamping (matches BDAT schema)
TYPE_CLAMP: dict[str, int] = {
    'hp':   0xFFFFFFFF,   # u32
    'mp':   0xFFFF,       # u16
    'str':  0xFFFF,       # u16
    'def':  0xFFFF,       # u16
    'rec':  0xFFFF,       # u16
    'tec':  0xFFFF,       # u16
    'agi':  0xFFFF,       # u16
    'luc':  0xFFFF,       # u16
    'exp':  0xFFFFFFFF,   # u32
    'zeni': 0xFFFFFFFF,   # u32
    'ap':   0xFFFF,       # u16
}

# Level-based stat ceilings for chaos mode (rough per-level maximums
# derived from vanilla data analysis — prevents absurd outliers)
# Format: (level_threshold, max_stat_multiplier)
# A lv1 enemy with base ~20 str gets ceiling 20*3 = 60
# A lv50 enemy with base ~400 str gets ceiling 400*3 = 1200
CHAOS_BASE_MULTIPLIER = 3.0
CHAOS_HP_MULTIPLIER = 5.0  # HP scales much higher


class EnemyStatRandomizer(BaseRandomizer):
    """
    Randomizes combat stats for enemy_param and boss_param tables.

    Config keys:
        mode:              'shuffle' | 'scale' | 'chaos'
        min_scale:         float  (default 0.75, used in 'scale' mode)
        max_scale:         float  (default 1.25, used in 'scale' mode)
        boss_scale_factor: float  (default 1.0, multiplied onto boss stats
                           AFTER randomization — lets users make bosses
                           harder/easier independently)
        randomize_bosses:  bool   (default True)
    """

    # Tables to process
    ENEMY_TABLE = 'enemy_param'
    BOSS_TABLE = 'boss_param'

    def __init__(self, rng: GameRNG, config: dict):
        super().__init__(rng, config)
        self.mode: str = config.get('mode', 'scale')
        self.min_scale: float = config.get('min_scale', 0.75)
        self.max_scale: float = config.get('max_scale', 1.25)
        self.boss_scale_factor: float = config.get('boss_scale_factor', 1.0)
        self.randomize_bosses: bool = config.get('randomize_bosses', True)

    # ──────────────────────────────────────────────────────────
    # Main entry point
    # ──────────────────────────────────────────────────────────

    def randomize(self, bdat: BdatFile, writer: BdatWriter) -> None:
        """Apply stat randomization to enemy and boss tables."""
        self._log(f"=== EnemyStatRandomizer: mode={self.mode} ===")

        # --- Process regular enemies ---
        enemy_table = bdat.get_table(self.ENEMY_TABLE)
        if enemy_table is not None:
            self._log(f"Processing {self.ENEMY_TABLE} ({enemy_table.num_rows} rows)")
            self._randomize_table(enemy_table, writer, self.ENEMY_TABLE,
                                  is_boss=False)
        else:
            self._log(f"WARNING: Table '{self.ENEMY_TABLE}' not found in BDAT")

        # --- Process bosses ---
        if self.randomize_bosses:
            boss_table = bdat.get_table(self.BOSS_TABLE)
            if boss_table is not None:
                self._log(f"Processing {self.BOSS_TABLE} ({boss_table.num_rows} rows)")
                self._randomize_table(boss_table, writer, self.BOSS_TABLE,
                                      is_boss=True)
            else:
                self._log(f"WARNING: Table '{self.BOSS_TABLE}' not found in BDAT")

        self._log(f"=== EnemyStatRandomizer complete: "
                  f"{writer.patch_count} cells patched ===")

    # ──────────────────────────────────────────────────────────
    # Mode dispatchers
    # ──────────────────────────────────────────────────────────

    def _randomize_table(self, table: BdatTable, writer: BdatWriter,
                         table_name: str, is_boss: bool) -> None:
        """Dispatch to the correct mode handler."""
        if self.mode == 'shuffle':
            self._mode_shuffle(table, writer, table_name, is_boss)
        elif self.mode == 'scale':
            self._mode_scale(table, writer, table_name, is_boss)
        elif self.mode == 'chaos':
            self._mode_chaos(table, writer, table_name, is_boss)
        else:
            self._log(f"WARNING: Unknown mode '{self.mode}', skipping")

    # ──────────────────────────────────────────────────────────
    # MODE: shuffle
    # ──────────────────────────────────────────────────────────

    def _mode_shuffle(self, table: BdatTable, writer: BdatWriter,
                      table_name: str, is_boss: bool) -> None:
        """
        Shuffle stats between enemies within ±5 levels of each other.

        For each stat column independently:
          1. Group enemies by level into overlapping windows (lv ± 5)
          2. Collect all values in the window
          3. Fisher-Yates shuffle the values
          4. Write them back in shuffled order
        """
        rows = table.rows
        if not rows:
            return

        # Build level list (safe default to 1 if 'lv' column is missing)
        levels = [row.get('lv', 1) for row in rows]

        for stat in STAT_COLS:
            # Verify column exists in this table
            if table.get_column(stat) is None:
                continue

            # Build level-similar groups (overlapping windows)
            # Process all enemies — each one picks its shuffled value from
            # the pool of enemies within ±5 levels
            processed = [False] * len(rows)
            idx = 0
            while idx < len(rows):
                if processed[idx]:
                    idx += 1
                    continue

                # Collect the level-similar group starting from this enemy
                center_lv = levels[idx]
                group_indices = [
                    i for i in range(len(rows))
                    if not processed[i]
                    and abs(levels[i] - center_lv) <= 5
                ]

                if len(group_indices) < 2:
                    # Nothing to shuffle with
                    for gi in group_indices:
                        processed[gi] = True
                    idx += 1
                    continue

                # Extract values, shuffle, write back
                values = [rows[i][stat] for i in group_indices]
                self.rng.shuffle(values)

                for gi, new_val in zip(group_indices, values):
                    old_val = rows[gi][stat]
                    new_val = self._apply_boss_scale(new_val, stat, is_boss)
                    writer.set_value(table_name, gi, stat, new_val)
                    if old_val != new_val:
                        self._log(f"  [{table_name}][{gi}] {stat}: "
                                  f"{old_val} → {new_val} (shuffle)")
                    processed[gi] = True

                idx += 1

    # ──────────────────────────────────────────────────────────
    # MODE: scale
    # ──────────────────────────────────────────────────────────

    def _mode_scale(self, table: BdatTable, writer: BdatWriter,
                    table_name: str, is_boss: bool) -> None:
        """Scale each stat by a random factor in [min_scale, max_scale]."""
        for row_idx, row in enumerate(table.rows):
            for stat in STAT_COLS:
                if table.get_column(stat) is None:
                    continue

                old_val = row.get(stat, 0)
                if old_val == 0:
                    continue  # don't scale zero stats

                clamp_max = TYPE_CLAMP.get(stat, 0xFFFF)
                new_val = self.rng.scale_value(
                    old_val, self.min_scale, self.max_scale,
                    clamp_min=1, clamp_max=clamp_max
                )
                new_val = self._apply_boss_scale(new_val, stat, is_boss)

                writer.set_value(table_name, row_idx, stat, new_val)
                if old_val != new_val:
                    ratio = new_val / old_val if old_val else 0
                    self._log(f"  [{table_name}][{row_idx}] {stat}: "
                              f"{old_val} → {new_val} (×{ratio:.2f})")

    # ──────────────────────────────────────────────────────────
    # MODE: chaos
    # ──────────────────────────────────────────────────────────

    def _mode_chaos(self, table: BdatTable, writer: BdatWriter,
                    table_name: str, is_boss: bool) -> None:
        """
        Completely random stats within level-appropriate bounds.

        Uses the enemy's level to derive reasonable min/max ranges:
          - Base ceiling = vanilla_value * CHAOS_BASE_MULTIPLIER
          - Floor = 1 (nothing goes to zero)
          - HP uses a higher multiplier since HP naturally varies more
        """
        for row_idx, row in enumerate(table.rows):
            lv = row.get('lv', 1)

            for stat in STAT_COLS:
                if table.get_column(stat) is None:
                    continue

                old_val = row.get(stat, 0)
                clamp_max = TYPE_CLAMP.get(stat, 0xFFFF)

                # Derive chaos bounds from level and vanilla value
                if stat == 'hp':
                    multiplier = CHAOS_HP_MULTIPLIER
                else:
                    multiplier = CHAOS_BASE_MULTIPLIER

                # Use max of (vanilla-derived, level-derived) as ceiling
                vanilla_ceiling = max(int(old_val * multiplier), 1)
                level_floor = max(1, lv // 2)

                # For reward stats (exp, zeni, ap), ensure minimum viability
                if stat in ('exp', 'zeni', 'ap'):
                    level_floor = max(1, old_val // 4)

                chaos_max = min(vanilla_ceiling, clamp_max)
                chaos_min = max(1, level_floor)

                if chaos_min > chaos_max:
                    chaos_min = 1

                new_val = self.rng.randint(chaos_min, chaos_max)
                new_val = self._apply_boss_scale(new_val, stat, is_boss)

                writer.set_value(table_name, row_idx, stat, new_val)
                self._log(f"  [{table_name}][{row_idx}] {stat}: "
                          f"{old_val} → {new_val} (chaos, lv={lv})")

    # ──────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────

    def _apply_boss_scale(self, value: int, stat: str,
                          is_boss: bool) -> int:
        """
        Apply the boss_scale_factor if processing a boss table.

        This lets users make bosses globally harder/easier without
        affecting regular enemy balance.
        """
        if not is_boss or self.boss_scale_factor == 1.0:
            return value

        clamp_max = TYPE_CLAMP.get(stat, 0xFFFF)
        scaled = int(value * self.boss_scale_factor)
        return max(1, min(clamp_max, scaled))
