#!/usr/bin/env python3
"""
boss_scaler.py — Boss Stat Scaler
====================================
Scales boss combat stats and randomizes rage (angry) thresholds in the
boss_param BDAT table.

Modes:
  'vanilla'   — No changes (pass-through)
  'scale'     — Multiply HP by hp_multiplier, combat stats by stat_multiplier,
                optionally randomize angry threshold (20–50)
  'nightmare' — HP ×2, all combat stats ×1.5, angry lowered to 15–30,
                resistances increased by 10–20 points

Protected columns (NEVER modified):
  Visual:     name_id, file, palno, size, shadow
  AI:         atk1–atk4, atk1_pow–atk4_pow (attack scripts)
  Level:      lv (encounter selection driver)
  Rewards:    exp, zeni, ap (handled by XpRewardRandomizer)

Verified against BDAT dump:
  boss_param — 55 rows, columns include:
    hp(u32), str(u16), def(u16), rec(u16), tec(u16), agi(u16),
    angry(u8), and resistance columns
"""

from randomizer.randomizers.base import BaseRandomizer
from randomizer.utils.rng import GameRNG
from randomizer.rom_io.bdat_reader import BdatFile, BdatTable
from randomizer.rom_io.bdat_writer import BdatWriter


# ──────────────────────────────────────────────────────────────
# Constants (verified from BDAT schema)
# ──────────────────────────────────────────────────────────────

BOSS_TABLE = 'boss_param'
BOSS_ROWS = 55

# Combat stat columns to scale (u16 range)
COMBAT_STAT_COLS = ('str', 'def', 'rec', 'tec', 'agi')

# Resistance columns that can be boosted in nightmare mode (u8 range)
RESIST_COLS = ('res_fire', 'res_ice', 'res_thunder', 'res_wind',
               'res_poison', 'res_paralyze', 'res_sleep', 'res_confuse',
               'res_stone', 'res_death')

# Type upper bounds for clamping
U32_MAX = 0xFFFFFFFF   # 4294967295
U16_MAX = 0xFFFF       # 65535
U8_MAX = 0xFF          # 255

# Angry threshold ranges (verified from vanilla data: ~30–35)
SCALE_ANGRY_MIN = 20
SCALE_ANGRY_MAX = 50
NIGHTMARE_ANGRY_MIN = 15
NIGHTMARE_ANGRY_MAX = 30

# Nightmare mode fixed multipliers
NIGHTMARE_HP_MULT = 2.0
NIGHTMARE_STAT_MULT = 1.5
NIGHTMARE_RESIST_ADD_MIN = 10
NIGHTMARE_RESIST_ADD_MAX = 20


class BossScaler(BaseRandomizer):
    """
    Scales boss stats and randomizes rage threshold.

    Config keys:
        mode:             'vanilla' | 'scale' | 'nightmare'
        hp_multiplier:    float (default 1.5, used in 'scale' mode)
        stat_multiplier:  float (default 1.0, used in 'scale' mode)
        randomize_angry:  bool  (default True, used in 'scale' mode)
    """

    def __init__(self, rng: GameRNG, config: dict):
        super().__init__(rng, config)
        self.mode: str = config.get('mode', 'vanilla')
        self.hp_multiplier: float = config.get('hp_multiplier', 1.5)
        self.stat_multiplier: float = config.get('stat_multiplier', 1.0)
        self.randomize_angry: bool = config.get('randomize_angry', True)

    # ──────────────────────────────────────────────────────────
    # Main entry point
    # ──────────────────────────────────────────────────────────

    def randomize(self, bdat: BdatFile, writer: BdatWriter) -> None:
        """Apply boss scaling based on the selected mode."""
        self._log(f"=== BossScaler: mode={self.mode} ===")

        if self.mode == 'vanilla':
            self._log("Mode is 'vanilla' — no changes applied.")
            return

        boss_table = bdat.get_table(BOSS_TABLE)
        if boss_table is None:
            self._log(f"WARNING: Table '{BOSS_TABLE}' not found in BDAT")
            return

        self._log(f"Processing {BOSS_TABLE} ({boss_table.num_rows} rows)")

        if self.mode == 'scale':
            self._mode_scale(boss_table, writer)
        elif self.mode == 'nightmare':
            self._mode_nightmare(boss_table, writer)
        else:
            self._log(f"WARNING: Unknown mode '{self.mode}', skipping")
            return

        self._log(f"=== BossScaler complete: "
                  f"{writer.patch_count} cells patched ===")

    # ──────────────────────────────────────────────────────────
    # MODE: scale
    # ──────────────────────────────────────────────────────────

    def _mode_scale(self, table: BdatTable, writer: BdatWriter) -> None:
        """
        Scale boss stats by configurable multipliers.

        - HP × hp_multiplier, clamped to u32
        - str/def/rec/tec/agi × stat_multiplier, clamped to u16
        - If randomize_angry: set angry to random value in [20, 50]
        """
        self._log(f"  hp_multiplier={self.hp_multiplier:.2f}, "
                  f"stat_multiplier={self.stat_multiplier:.2f}, "
                  f"randomize_angry={self.randomize_angry}")

        for row_idx, row in enumerate(table.rows):
            # ── HP scaling ──
            old_hp = row.get('hp', 0)
            if old_hp > 0 and self.hp_multiplier != 1.0:
                new_hp = int(old_hp * self.hp_multiplier)
                new_hp = max(1, min(U32_MAX, new_hp))
                writer.set_value(BOSS_TABLE, row_idx, 'hp', new_hp)
            else:
                new_hp = old_hp

            # ── Combat stat scaling ──
            for stat in COMBAT_STAT_COLS:
                if table.get_column(stat) is None:
                    continue
                old_val = row.get(stat, 0)
                if old_val <= 0 or self.stat_multiplier == 1.0:
                    continue
                new_val = int(old_val * self.stat_multiplier)
                new_val = max(1, min(U16_MAX, new_val))
                writer.set_value(BOSS_TABLE, row_idx, stat, new_val)

            # ── Angry threshold randomization ──
            old_angry = row.get('angry', 0)
            if self.randomize_angry and old_angry > 0:
                new_angry = self.rng.randint(
                    SCALE_ANGRY_MIN, SCALE_ANGRY_MAX
                )
                new_angry = max(1, min(U8_MAX, new_angry))
                writer.set_value(BOSS_TABLE, row_idx, 'angry', new_angry)
            else:
                new_angry = old_angry

            # ── Log this boss ──
            self._log(
                f"  [{BOSS_TABLE}][{row_idx}] "
                f"HP: {old_hp} → {new_hp}, "
                f"angry: {old_angry} → {new_angry}"
            )

    # ──────────────────────────────────────────────────────────
    # MODE: nightmare
    # ──────────────────────────────────────────────────────────

    def _mode_nightmare(self, table: BdatTable, writer: BdatWriter) -> None:
        """
        Nightmare mode — dramatically harder bosses.

        - HP ×2
        - All combat stats ×1.5
        - Angry threshold lowered to 15–30 (bosses rage earlier)
        - Resistances increased by 10–20 points (harder to status)
        """
        self._log("  Nightmare mode: HP ×2, stats ×1.5, "
                  f"angry {NIGHTMARE_ANGRY_MIN}–{NIGHTMARE_ANGRY_MAX}, "
                  "resistances +10–20")

        for row_idx, row in enumerate(table.rows):
            # ── HP ×2 ──
            old_hp = row.get('hp', 0)
            if old_hp > 0:
                new_hp = int(old_hp * NIGHTMARE_HP_MULT)
                new_hp = max(1, min(U32_MAX, new_hp))
                writer.set_value(BOSS_TABLE, row_idx, 'hp', new_hp)
            else:
                new_hp = old_hp

            # ── Combat stats ×1.5 ──
            for stat in COMBAT_STAT_COLS:
                if table.get_column(stat) is None:
                    continue
                old_val = row.get(stat, 0)
                if old_val <= 0:
                    continue
                new_val = int(old_val * NIGHTMARE_STAT_MULT)
                new_val = max(1, min(U16_MAX, new_val))
                writer.set_value(BOSS_TABLE, row_idx, stat, new_val)

            # ── Lower angry threshold ──
            old_angry = row.get('angry', 0)
            if old_angry > 0:
                new_angry = self.rng.randint(
                    NIGHTMARE_ANGRY_MIN, NIGHTMARE_ANGRY_MAX
                )
                new_angry = max(1, min(U8_MAX, new_angry))
                writer.set_value(BOSS_TABLE, row_idx, 'angry', new_angry)
            else:
                new_angry = old_angry

            # ── Boost resistances ──
            for res_col in RESIST_COLS:
                if table.get_column(res_col) is None:
                    continue
                old_res = row.get(res_col, 0)
                boost = self.rng.randint(
                    NIGHTMARE_RESIST_ADD_MIN, NIGHTMARE_RESIST_ADD_MAX
                )
                new_res = old_res + boost
                new_res = max(0, min(U8_MAX, new_res))
                writer.set_value(BOSS_TABLE, row_idx, res_col, new_res)

            # ── Log this boss ──
            self._log(
                f"  [{BOSS_TABLE}][{row_idx}] "
                f"HP: {old_hp} → {new_hp}, "
                f"angry: {old_angry} → {new_angry} "
                f"(nightmare)"
            )
