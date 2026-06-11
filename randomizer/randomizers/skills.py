#!/usr/bin/env python3
"""
skills.py — Skill Randomizer
==============================
Randomizes active skill (Ki blasts / melee specials) and passive skill
numeric values across all six playable characters.

Modes:
  'shuffle' — Pool together power/cost values from ALL characters,
              Fisher-Yates shuffle them, then redistribute. This means
              Goku might end up with Piccolo's Ki costs and Yamcha's damage.

  'scale'   — Scale use_mp, power, effpow, and hit values by a random
              factor per skill (preserves relative progression across
              skill levels 1–5).

Protected columns (NEVER modified by either mode):
  Identity:     name, blast_type, help
  Targeting:    range, width, height
  Animations:   (implicit — no animation column in BDAT)
  Skill-tree:   cond_blast1, cond_lv1, cond_blast2, cond_lv2
  Combo roster: title, help, pc1–pc3, blast1–blast3

BDAT tables processed:
  skill_goku, skill_gohan, skill_pikkoro, skill_kuririn,
  skill_tenshin, skill_yamcha                              (7 rows × 6)
  passive_goku … passive_yamcha                            (8 rows × 6)
"""

from randomizer.randomizers.base import BaseRandomizer
from randomizer.utils.rng import GameRNG
from randomizer.rom_io.bdat_reader import BdatFile, BdatTable
from randomizer.rom_io.bdat_writer import BdatWriter
from randomizer.data.skills import (
    CHARACTER_NAMES, AP_LOCKED,
    load_character_skills, load_passive_skills,
)


# ──────────────────────────────────────────────────────────────
# Column groups eligible for randomization
# ──────────────────────────────────────────────────────────────

# Active skill columns that are safe to shuffle / scale.
# Grouped by concept so we shuffle "all mp costs together", etc.
ACTIVE_MP_COLS = ('use_mp1', 'use_mp2', 'use_mp3', 'use_mp4', 'use_mp5')
ACTIVE_POWER_COLS = ('power1', 'power2', 'power3', 'power4', 'power5')
ACTIVE_HIT_COLS = ('hit1', 'hit2', 'hit3', 'hit4', 'hit5')
ACTIVE_EFFPOW_COLS = ('effpow1', 'effpow2', 'effpow3', 'effpow4', 'effpow5')

# All active columns we may touch (for scale mode per-cell iteration)
ACTIVE_SCALE_COLS = ACTIVE_MP_COLS + ACTIVE_POWER_COLS + ACTIVE_HIT_COLS + ACTIVE_EFFPOW_COLS

# Passive skill columns safe to scale/shuffle
PASSIVE_POWER_COLS = ('power1', 'power2', 'power3', 'power4', 'power5')

# Type upper-bounds (matches BDAT schema from JSON dumps)
TYPE_CLAMP: dict[str, int] = {
    'use_mp1': 0xFFFF, 'use_mp2': 0xFFFF, 'use_mp3': 0xFFFF,
    'use_mp4': 0xFFFF, 'use_mp5': 0xFFFF,
    'power1': 0xFFFF, 'power2': 0xFFFF, 'power3': 0xFFFF,
    'power4': 0xFFFF, 'power5': 0xFFFF,
    'hit1': 0xFF, 'hit2': 0xFF, 'hit3': 0xFF,
    'hit4': 0xFF, 'hit5': 0xFF,
    'effpow1': 0xFF, 'effpow2': 0xFF, 'effpow3': 0xFF,
    'effpow4': 0xFF, 'effpow5': 0xFF,
}


class SkillRandomizer(BaseRandomizer):
    """
    Randomizes active and passive skill values across all characters.

    Config keys:
        mode:            'shuffle' | 'scale'
        min_scale:       float  (default 0.75, used in 'scale' mode)
        max_scale:       float  (default 1.25, used in 'scale' mode)
        randomize_passives: bool (default True — include passive_* tables)
    """

    def __init__(self, rng: GameRNG, config: dict):
        super().__init__(rng, config)
        self.mode: str = config.get('mode', 'scale')
        self.min_scale: float = config.get('min_scale', 0.75)
        self.max_scale: float = config.get('max_scale', 1.25)
        self.randomize_passives: bool = config.get('randomize_passives', True)

    # ──────────────────────────────────────────────────────────
    # Main entry point
    # ──────────────────────────────────────────────────────────

    def randomize(self, bdat: BdatFile, writer: BdatWriter) -> None:
        """Apply skill randomization to all character skill tables."""
        self._log(f"=== SkillRandomizer: mode={self.mode} ===")

        if self.mode == 'shuffle':
            self._mode_shuffle_active(bdat, writer)
            if self.randomize_passives:
                self._mode_shuffle_passive(bdat, writer)
        elif self.mode == 'scale':
            self._mode_scale_active(bdat, writer)
            if self.randomize_passives:
                self._mode_scale_passive(bdat, writer)
        else:
            self._log(f"WARNING: Unknown mode '{self.mode}', skipping")
            return

        self._log(f"=== SkillRandomizer complete: "
                  f"{writer.patch_count} cells patched ===")

    # ──────────────────────────────────────────────────────────
    # MODE: shuffle — Active Skills
    # ──────────────────────────────────────────────────────────

    def _mode_shuffle_active(self, bdat: BdatFile,
                             writer: BdatWriter) -> None:
        """
        Shuffle active skill numeric values across all characters.

        For each column group (mp costs, power, hit, effpow) independently:
          1. Pool values from all 6 characters' skill_* tables
          2. Fisher-Yates shuffle the pooled values
          3. Write them back, redistributing across characters

        This preserves overall balance (same total values exist in the game)
        but scrambles who has what.
        """
        # Collect (table_name, row_idx) for every active skill across all chars
        all_entries: list[tuple[str, int]] = []
        for char in CHARACTER_NAMES:
            table_name = f'skill_{char}'
            table = bdat.get_table(table_name)
            if table is None:
                self._log(f"WARNING: Table '{table_name}' not found, skipping")
                continue
            self._log(f"Processing {table_name} ({table.num_rows} rows)")
            for row_idx in range(table.num_rows):
                all_entries.append((table_name, row_idx))

        if not all_entries:
            self._log("WARNING: No active skill tables found")
            return

        # Shuffle each column group independently
        for col_group_name, col_group in [
            ('MP costs', ACTIVE_MP_COLS),
            ('Power',    ACTIVE_POWER_COLS),
            ('Hit',      ACTIVE_HIT_COLS),
            ('EffPow',   ACTIVE_EFFPOW_COLS),
        ]:
            self._shuffle_column_group(
                bdat, writer, all_entries, col_group, col_group_name
            )

    def _shuffle_column_group(
        self,
        bdat: BdatFile,
        writer: BdatWriter,
        entries: list[tuple[str, int]],
        col_names: tuple[str, ...],
        group_label: str,
    ) -> None:
        """Shuffle a group of related columns across all entries."""
        # Each "entry" is a row; we shuffle entire tuples of the column group
        # so that level 1–5 values stay internally consistent per row.
        tuples: list[tuple[int, ...]] = []
        for table_name, row_idx in entries:
            table = bdat.get_table(table_name)
            row = table.rows[row_idx]
            tuples.append(tuple(row.get(c, 0) for c in col_names))

        # Shuffle the tuples
        self.rng.shuffle(tuples)

        # Write back
        for (table_name, row_idx), new_vals in zip(entries, tuples):
            table = bdat.get_table(table_name)
            row = table.rows[row_idx]
            for col_name, new_val in zip(col_names, new_vals):
                old_val = row.get(col_name, 0)
                writer.set_value(table_name, row_idx, col_name, new_val)
                if old_val != new_val:
                    self._log(
                        f"  [{table_name}][{row_idx}] {col_name}: "
                        f"{old_val} → {new_val} (shuffle {group_label})"
                    )

    # ──────────────────────────────────────────────────────────
    # MODE: shuffle — Passive Skills
    # ──────────────────────────────────────────────────────────

    def _mode_shuffle_passive(self, bdat: BdatFile,
                              writer: BdatWriter) -> None:
        """Shuffle passive skill power values across all characters."""
        all_entries: list[tuple[str, int]] = []
        for char in CHARACTER_NAMES:
            table_name = f'passive_{char}'
            table = bdat.get_table(table_name)
            if table is None:
                self._log(f"WARNING: Table '{table_name}' not found, skipping")
                continue
            self._log(f"Processing {table_name} ({table.num_rows} rows)")
            for row_idx in range(table.num_rows):
                all_entries.append((table_name, row_idx))

        if not all_entries:
            self._log("WARNING: No passive skill tables found")
            return

        self._shuffle_column_group(
            bdat, writer, all_entries, PASSIVE_POWER_COLS, 'Passive Power'
        )

    # ──────────────────────────────────────────────────────────
    # MODE: scale — Active Skills
    # ──────────────────────────────────────────────────────────

    def _mode_scale_active(self, bdat: BdatFile,
                           writer: BdatWriter) -> None:
        """
        Scale active skill values by a per-skill random factor.

        Each skill row gets ONE random scale factor applied uniformly
        to all its level 1–5 values within each column group.  This
        preserves the internal progression curve (level 5 always ≥ level 1)
        while varying the overall magnitude.
        """
        for char in CHARACTER_NAMES:
            table_name = f'skill_{char}'
            table = bdat.get_table(table_name)
            if table is None:
                self._log(f"WARNING: Table '{table_name}' not found, skipping")
                continue
            self._log(f"Scaling {table_name} ({table.num_rows} rows)")

            for row_idx, row in enumerate(table.rows):
                # Scale MP costs with one factor per skill
                self._scale_row_group(
                    writer, table, table_name, row_idx, row,
                    ACTIVE_MP_COLS, 'MP'
                )
                # Scale power with a separate factor
                self._scale_row_group(
                    writer, table, table_name, row_idx, row,
                    ACTIVE_POWER_COLS, 'Power'
                )
                # Scale hit % (clamped to u8 max = 255, but practically 0–100)
                self._scale_row_group(
                    writer, table, table_name, row_idx, row,
                    ACTIVE_HIT_COLS, 'Hit'
                )
                # Scale effect power
                self._scale_row_group(
                    writer, table, table_name, row_idx, row,
                    ACTIVE_EFFPOW_COLS, 'EffPow'
                )

    def _scale_row_group(
        self,
        writer: BdatWriter,
        table: BdatTable,
        table_name: str,
        row_idx: int,
        row: dict,
        col_names: tuple[str, ...],
        group_label: str,
    ) -> None:
        """Scale a group of columns for a single row with one shared factor."""
        # Check if ALL values in the group are zero → skip
        values = [row.get(c, 0) for c in col_names]
        if all(v == 0 for v in values):
            return

        # One random factor for the entire group (preserves level curve)
        scale_1000 = self.rng.randint(
            int(self.min_scale * 1000),
            int(self.max_scale * 1000),
        )

        for col_name in col_names:
            if table.get_column(col_name) is None:
                continue
            old_val = row.get(col_name, 0)
            if old_val == 0:
                continue

            clamp_max = TYPE_CLAMP.get(col_name, 0xFFFF)
            new_val = (old_val * scale_1000) // 1000
            new_val = max(1, min(clamp_max, new_val))

            writer.set_value(table_name, row_idx, col_name, new_val)
            if old_val != new_val:
                ratio = new_val / old_val if old_val else 0
                self._log(
                    f"  [{table_name}][{row_idx}] {col_name}: "
                    f"{old_val} → {new_val} (×{ratio:.2f}, {group_label})"
                )

    # ──────────────────────────────────────────────────────────
    # MODE: scale — Passive Skills
    # ──────────────────────────────────────────────────────────

    def _mode_scale_passive(self, bdat: BdatFile,
                            writer: BdatWriter) -> None:
        """Scale passive skill power values by a per-skill random factor."""
        for char in CHARACTER_NAMES:
            table_name = f'passive_{char}'
            table = bdat.get_table(table_name)
            if table is None:
                self._log(f"WARNING: Table '{table_name}' not found, skipping")
                continue
            self._log(f"Scaling {table_name} ({table.num_rows} rows)")

            for row_idx, row in enumerate(table.rows):
                self._scale_row_group(
                    writer, table, table_name, row_idx, row,
                    PASSIVE_POWER_COLS, 'Passive Power'
                )
