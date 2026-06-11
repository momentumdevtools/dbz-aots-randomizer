#!/usr/bin/env python3
"""
player_growth.py — Player Growth Curve Randomizer
====================================================
Randomizes per-level stat growth values for the 6 playable characters
(Goku, Gohan, Piccolo, Krillin, Tenshinhan, Yamcha).

Rows 6-7 (Bubbles/Gregory — NPC training-minigame guests) are NEVER
modified to prevent softlocks.

Modes:
    'vanilla'  — No changes
    'shuffle'  — Redistribute growth profiles between playable chars
    'random'   — Scale each growth value by a random factor (1 ± variance)

Config keys:
    mode:            'vanilla' | 'shuffle' | 'random'
    shuffle_base:    bool  (default False) — also shuffle base stat profiles
    growth_variance: float (default 0.5)  — ±50% scaling range for 'random'
"""

from randomizer.randomizers.base import BaseRandomizer
from randomizer.rom_io.bdat_reader import BdatFile
from randomizer.rom_io.bdat_writer import BdatWriter
from randomizer.data.players import PLAYABLE_INDICES, CHARACTER_NAMES


# ──────────────────────────────────────────────────────────────
# Column groups
# ──────────────────────────────────────────────────────────────

# Growth phase 1 (per level, up to exlv)
GROWTH_P1_COLS = ('hpup', 'mpup', 'strup', 'defup', 'recup',
                  'tecup', 'agiup', 'lucup')

# Growth phase 2 (per level, after exlv)
GROWTH_P2_COLS = ('hpup2', 'mpup2', 'strup2', 'defup2', 'recup2',
                  'tecup2', 'agiup2', 'lucup2')

# All growth columns combined (16 total)
ALL_GROWTH_COLS = GROWTH_P1_COLS + GROWTH_P2_COLS

# Base stat columns
BASE_STAT_COLS = ('hp', 'mp', 'str', 'def', 'rec', 'tec', 'agi', 'luc')

# HP/MP growth columns (minimum growth = 1)
HP_MP_GROWTH_COLS = {'hpup', 'mpup', 'hpup2', 'mpup2'}

TABLE_NAME = 'player_param'


class PlayerGrowthRandomizer(BaseRandomizer):
    """
    Randomizes level-up stat growth curves for playable characters.

    Config keys:
        mode:            'vanilla' | 'shuffle' | 'random'
        shuffle_base:    bool  (default False)
        growth_variance: float (default 0.5 = ±50%)
    """

    def __init__(self, rng, config: dict):
        super().__init__(rng, config)
        self.mode: str = config.get('mode', 'vanilla')
        self.shuffle_base: bool = config.get('shuffle_base', False)
        self.growth_variance: float = config.get('growth_variance', 0.5)

    # ──────────────────────────────────────────────────────────
    # Main entry point
    # ──────────────────────────────────────────────────────────

    def randomize(self, bdat: BdatFile, writer: BdatWriter) -> None:
        """Apply growth-curve randomization to the player_param table."""
        self._log(f"=== PlayerGrowthRandomizer: mode={self.mode} ===")

        table = bdat.get_table(TABLE_NAME)
        if table is None:
            self._log(f"WARNING: Table '{TABLE_NAME}' not found")
            return

        if self.mode == 'vanilla':
            self._log("Mode is 'vanilla' — no changes.")
            return
        elif self.mode == 'shuffle':
            self._mode_shuffle(table, writer)
        elif self.mode == 'random':
            self._mode_random(table, writer)
        else:
            self._log(f"WARNING: Unknown mode '{self.mode}', skipping")
            return

        self._log(f"=== PlayerGrowthRandomizer complete ===")

    # ──────────────────────────────────────────────────────────
    # MODE: shuffle
    # ──────────────────────────────────────────────────────────

    def _mode_shuffle(self, table, writer) -> None:
        """
        Shuffle growth profiles between the 6 playable characters.

        Each character's complete growth profile (all 16 growth columns)
        is treated as a single unit and redistributed. If shuffle_base is
        enabled, base stat profiles (8 columns) are shuffled independently.
        """
        rows = table.rows

        # --- Collect growth profiles from playable chars ---
        growth_profiles = []
        for idx in PLAYABLE_INDICES:
            row = rows[idx]
            profile = {col: row.get(col, 0) for col in ALL_GROWTH_COLS}
            growth_profiles.append(profile)

        # Shuffle growth profiles
        self.rng.shuffle(growth_profiles)

        # --- Optionally collect and shuffle base stat profiles ---
        base_profiles = None
        if self.shuffle_base:
            base_profiles = []
            for idx in PLAYABLE_INDICES:
                row = rows[idx]
                profile = {col: row.get(col, 0) for col in BASE_STAT_COLS}
                base_profiles.append(profile)
            self.rng.shuffle(base_profiles)

        # --- Write back shuffled profiles ---
        for i, idx in enumerate(PLAYABLE_INDICES):
            row = rows[idx]
            char_name = CHARACTER_NAMES.get(row.get('name_id', idx + 1),
                                            f"Char {idx}")

            # Growth columns
            new_growth = growth_profiles[i]
            old_growth_str = self._format_growth(row, ALL_GROWTH_COLS)
            new_growth_str = self._format_growth_dict(new_growth, ALL_GROWTH_COLS)

            for col in ALL_GROWTH_COLS:
                new_val = new_growth[col]
                writer.set_value(TABLE_NAME, idx, col, new_val)

            self._log(f"  [{char_name}] growth: {old_growth_str} → {new_growth_str}")

            # Base stats (if shuffling)
            if base_profiles is not None:
                new_base = base_profiles[i]
                old_base_str = self._format_growth(row, BASE_STAT_COLS)
                new_base_str = self._format_growth_dict(new_base, BASE_STAT_COLS)

                for col in BASE_STAT_COLS:
                    new_val = new_base[col]
                    writer.set_value(TABLE_NAME, idx, col, new_val)

                self._log(f"  [{char_name}] base:   {old_base_str} → {new_base_str}")

        self._log(f"  Shuffled growth profiles for {len(PLAYABLE_INDICES)} "
                  f"playable characters"
                  + (" (with base stats)" if self.shuffle_base else ""))

    # ──────────────────────────────────────────────────────────
    # MODE: random
    # ──────────────────────────────────────────────────────────

    def _mode_random(self, table, writer) -> None:
        """
        Scale each growth value by a random factor in [1 - variance, 1 + variance].

        - HP/MP growths have a minimum of 1 (can't have 0 HP gain per level)
        - Other stat growths have a minimum of 0
        - All values clamped to u8 (0–255)
        """
        rows = table.rows
        variance = self.growth_variance
        min_scale = 1.0 - variance
        max_scale = 1.0 + variance

        for idx in PLAYABLE_INDICES:
            row = rows[idx]
            char_name = CHARACTER_NAMES.get(row.get('name_id', idx + 1),
                                            f"Char {idx}")

            old_growth_str = self._format_growth(row, ALL_GROWTH_COLS)

            for col in ALL_GROWTH_COLS:
                old_val = row.get(col, 0)

                # Determine minimum: HP/MP growth must be at least 1
                if col in HP_MP_GROWTH_COLS:
                    clamp_min = 1
                else:
                    clamp_min = 0

                # Scale the value
                new_val = self.rng.scale_value(
                    old_val, min_scale, max_scale,
                    clamp_min=clamp_min, clamp_max=255
                )

                writer.set_value(TABLE_NAME, idx, col, new_val)

            # Log after all columns are processed for this character
            new_vals = {}
            for col in ALL_GROWTH_COLS:
                old_v = row.get(col, 0)
                if col in HP_MP_GROWTH_COLS:
                    c_min = 1
                else:
                    c_min = 0
                # Re-derive the value from the writer would be complex,
                # so we read the original and note the variance range
                new_vals[col] = old_v  # placeholder for log
            # Instead, log per-column detail
            self._log(f"  [{char_name}] growth randomized (±{int(variance*100)}%):")
            for col in ALL_GROWTH_COLS:
                old_val = row.get(col, 0)
                # The actual new value was already written; reconstruct from
                # the writer's perspective by re-reading isn't possible here,
                # so log the old value and variance range
                lo = max(1 if col in HP_MP_GROWTH_COLS else 0,
                         int(old_val * min_scale))
                hi = min(255, int(old_val * max_scale))
                self._log(f"    {col}: {old_val} → scaled [{lo}–{hi}]")

        self._log(f"  Randomized growth for {len(PLAYABLE_INDICES)} "
                  f"playable characters (variance=±{int(variance*100)}%)")

    # ──────────────────────────────────────────────────────────
    # Formatting helpers
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _format_growth(row, cols) -> str:
        """Format a row's growth columns into a compact string."""
        return '/'.join(str(row.get(c, 0)) for c in cols)

    @staticmethod
    def _format_growth_dict(profile: dict, cols) -> str:
        """Format a profile dict's growth columns into a compact string."""
        return '/'.join(str(profile.get(c, 0)) for c in cols)
