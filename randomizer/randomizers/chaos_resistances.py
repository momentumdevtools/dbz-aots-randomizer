#!/usr/bin/env python3
"""
chaos_resistances.py — Enemy/Boss Resistance Randomizer
=========================================================
Shuffles, randomizes, or inverts status-ailment and elemental resistance
profiles for enemies and bosses.

Tables:
    enemy_param: 173 rows (regular encounter enemies)
    boss_param:   55 rows (story/boss fights)

Resistance columns (15 total):
    Status:   sleep, bind, poison, dark, stan, panic, freez, dead, carrot
    Element:  physics, slash, blast, atr_fire, atr_thunder, atr_ice

Modes:
    'vanilla'  — No changes
    'shuffle'  — Redistribute resistance profiles between enemies
    'random'   — Fully randomize resistance values within sane bounds
    'inverse'  — Flip high/low: new = max - old (resistant ↔ weak)

Config keys:
    mode:           'vanilla' | 'shuffle' | 'random' | 'inverse'
    include_bosses: bool (default False) — also process boss_param
"""

from randomizer.randomizers.base import BaseRandomizer
from randomizer.rom_io.bdat_reader import BdatFile, BdatTable
from randomizer.rom_io.bdat_writer import BdatWriter


# ──────────────────────────────────────────────────────────────
# Column groups
# ──────────────────────────────────────────────────────────────

# Status ailment resistances (percentage, 0–100 typically)
STATUS_RESIST_COLS = ('sleep', 'bind', 'poison', 'dark', 'stan',
                      'panic', 'freez', 'dead', 'carrot')

# Elemental / damage-type resistances (can exceed 100 for absorption)
ELEMENT_RESIST_COLS = ('physics', 'slash', 'blast',
                       'atr_fire', 'atr_thunder', 'atr_ice')

# All resistance columns (15 total)
ALL_RESIST_COLS = STATUS_RESIST_COLS + ELEMENT_RESIST_COLS

# Set for O(1) membership checks
_STATUS_SET = set(STATUS_RESIST_COLS)
_ELEMENT_SET = set(ELEMENT_RESIST_COLS)

# Bounds
STATUS_MIN = 0
STATUS_MAX = 100
ELEMENT_MIN = 0
ELEMENT_MAX = 200

ENEMY_TABLE = 'enemy_param'
BOSS_TABLE = 'boss_param'


class ChaosResistanceRandomizer(BaseRandomizer):
    """
    Randomizes resistance profiles for enemy_param and boss_param.

    Config keys:
        mode:           'vanilla' | 'shuffle' | 'random' | 'inverse'
        include_bosses: bool (default False)
    """

    def __init__(self, rng, config: dict):
        super().__init__(rng, config)
        self.mode: str = config.get('mode', 'vanilla')
        self.include_bosses: bool = config.get('include_bosses', False)

    # ──────────────────────────────────────────────────────────
    # Main entry point
    # ──────────────────────────────────────────────────────────

    def randomize(self, bdat: BdatFile, writer: BdatWriter) -> None:
        """Apply resistance randomization to enemy and/or boss tables."""
        self._log(f"=== ChaosResistanceRandomizer: mode={self.mode} ===")

        if self.mode == 'vanilla':
            self._log("Mode is 'vanilla' — no changes.")
            return

        # --- Process regular enemies ---
        enemy_table = bdat.get_table(ENEMY_TABLE)
        if enemy_table is not None:
            self._process_table(enemy_table, writer, ENEMY_TABLE)
        else:
            self._log(f"WARNING: Table '{ENEMY_TABLE}' not found in BDAT")

        # --- Process bosses (if enabled) ---
        if self.include_bosses:
            boss_table = bdat.get_table(BOSS_TABLE)
            if boss_table is not None:
                self._process_table(boss_table, writer, BOSS_TABLE)
            else:
                self._log(f"WARNING: Table '{BOSS_TABLE}' not found in BDAT")

        self._log(f"=== ChaosResistanceRandomizer complete ===")

    # ──────────────────────────────────────────────────────────
    # Dispatcher
    # ──────────────────────────────────────────────────────────

    def _process_table(self, table: BdatTable, writer: BdatWriter,
                       table_name: str) -> None:
        """Dispatch to the correct mode handler for a given table."""
        self._log(f"Processing {table_name} ({table.num_rows} rows)")

        if self.mode == 'shuffle':
            self._mode_shuffle(table, writer, table_name)
        elif self.mode == 'random':
            self._mode_random(table, writer, table_name)
        elif self.mode == 'inverse':
            self._mode_inverse(table, writer, table_name)
        else:
            self._log(f"WARNING: Unknown mode '{self.mode}', skipping")

    # ──────────────────────────────────────────────────────────
    # MODE: shuffle
    # ──────────────────────────────────────────────────────────

    def _mode_shuffle(self, table: BdatTable, writer: BdatWriter,
                      table_name: str) -> None:
        """
        Collect all resistance profiles and shuffle which enemy gets which.

        Each enemy's complete 15-column resistance profile is treated as a
        single unit. Profiles are shuffled within the same table only
        (enemies stay with enemies, bosses stay with bosses).
        """
        rows = table.rows
        num_rows = len(rows)
        if num_rows < 2:
            self._log(f"  Skipping shuffle — only {num_rows} row(s)")
            return

        # Collect all resistance profiles
        profiles = []
        for row in rows:
            profile = {col: row.get(col, 0) for col in ALL_RESIST_COLS}
            profiles.append(profile)

        # Fisher-Yates shuffle via deterministic RNG
        self.rng.shuffle(profiles)

        # Write back shuffled profiles
        changed = 0
        for row_idx in range(num_rows):
            new_profile = profiles[row_idx]
            for col in ALL_RESIST_COLS:
                new_val = new_profile[col]
                writer.set_value(table_name, row_idx, col, new_val)
            changed += 1

        self._log(f"  {changed} {table_name} resistance profiles shuffled")

    # ──────────────────────────────────────────────────────────
    # MODE: random
    # ──────────────────────────────────────────────────────────

    def _mode_random(self, table: BdatTable, writer: BdatWriter,
                     table_name: str) -> None:
        """
        Randomize each resistance value independently.

        Status resists (sleep–carrot): random 0–100 (percentage)
        Element resists (physics–atr_ice): random 0–200 (can absorb)

        Sanity guard: at most 60% of status columns can be fully immune
        (value >= 95) for any single enemy, preventing "immune to everything"
        enemies that would be unfun.
        """
        rows = table.rows
        changed = 0
        max_immune_status = int(len(STATUS_RESIST_COLS) * 0.6)

        for row_idx, row in enumerate(rows):
            # --- Randomize status resistances ---
            status_values = {}
            for col in STATUS_RESIST_COLS:
                status_values[col] = self.rng.randint(STATUS_MIN, STATUS_MAX)

            # Sanity check: cap the number of near-immune status resists
            immune_count = sum(1 for v in status_values.values() if v >= 95)
            if immune_count > max_immune_status:
                # Reduce excess immunities by re-rolling to non-immune values
                immune_cols = [c for c, v in status_values.items() if v >= 95]
                self.rng.shuffle(immune_cols)
                for excess_col in immune_cols[max_immune_status:]:
                    status_values[excess_col] = self.rng.randint(
                        STATUS_MIN, 80
                    )

            for col in STATUS_RESIST_COLS:
                writer.set_value(table_name, row_idx, col, status_values[col])

            # --- Randomize element resistances ---
            elem_values = {}
            for col in ELEMENT_RESIST_COLS:
                elem_values[col] = self.rng.randint(ELEMENT_MIN, ELEMENT_MAX)

            # Sanity guard: at most ONE primary damage type (physics,
            # slash, blast) may absorb (>100).  If multiple absorb,
            # keep only one random absorber and clamp the rest to 100.
            PRIMARY_DMG = ('physics', 'slash', 'blast')
            absorbers = [c for c in PRIMARY_DMG if elem_values.get(c, 0) > 100]
            if len(absorbers) > 1:
                # Pick one lucky absorber to keep
                keep = absorbers[self.rng.randint(0, len(absorbers) - 1)]
                for c in absorbers:
                    if c != keep:
                        elem_values[c] = self.rng.randint(
                            ELEMENT_MIN, 100)

            for col in ELEMENT_RESIST_COLS:
                writer.set_value(table_name, row_idx, col, elem_values[col])

            changed += 1

        self._log(f"  {changed} {table_name} resistance profiles randomized")

    # ──────────────────────────────────────────────────────────
    # MODE: inverse
    # ──────────────────────────────────────────────────────────

    def _mode_inverse(self, table: BdatTable, writer: BdatWriter,
                      table_name: str) -> None:
        """
        Invert resistances: previously resistant enemies become weak,
        and previously weak enemies become resistant.

        Status:  new_val = 100 - old_val, clamped [0, 100]
        Element: new_val = 200 - old_val, clamped [0, 200]

        Sanity guard: at most one of physics/slash/blast may absorb.
        """
        rows = table.rows
        changed = 0

        PRIMARY_DMG = ('physics', 'slash', 'blast')

        for row_idx, row in enumerate(rows):
            any_change = False
            elem_values = {}

            for col in ALL_RESIST_COLS:
                old_val = row.get(col, 0)

                if col in _STATUS_SET:
                    new_val = 100 - old_val
                    new_val = max(STATUS_MIN, min(STATUS_MAX, new_val))
                else:  # element
                    new_val = 200 - old_val
                    new_val = max(ELEMENT_MIN, min(ELEMENT_MAX, new_val))
                    elem_values[col] = new_val

                if old_val != new_val:
                    any_change = True

            # Sanity guard: at most ONE primary damage type may absorb
            absorbers = [c for c in PRIMARY_DMG
                         if elem_values.get(c, 0) > 100]
            if len(absorbers) > 1:
                keep = absorbers[self.rng.randint(0, len(absorbers) - 1)]
                for c in absorbers:
                    if c != keep:
                        elem_values[c] = 100

            # Write all values
            for col in STATUS_RESIST_COLS:
                old_val = row.get(col, 0)
                new_val = 100 - old_val
                new_val = max(STATUS_MIN, min(STATUS_MAX, new_val))
                writer.set_value(table_name, row_idx, col, new_val)

            for col in ELEMENT_RESIST_COLS:
                writer.set_value(table_name, row_idx, col, elem_values[col])

            if any_change:
                changed += 1

        self._log(f"  {changed} {table_name} resistance profiles inverted")
