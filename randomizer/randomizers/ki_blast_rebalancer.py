#!/usr/bin/env python3
"""
ki_blast_rebalancer.py — Ki Blast Skill Rebalancer
=====================================================
Randomizes Ki Blast power/MP costs/unlock order WITHOUT cross-character
shuffle (animations are sprite-bound to each character).

Tables: skill_goku/gohan/pikkoro/kuririn/tenshin/yamcha (7 rows each)
Also:   passive_goku/gohan/pikkoro/kuririn/tenshin/yamcha (8 rows each)
"""

from randomizer.randomizers.base import BaseRandomizer
from randomizer.rom_io.bdat_reader import BdatFile
from randomizer.rom_io.bdat_writer import BdatWriter

SKILL_TABLES = [
    "skill_goku", "skill_gohan", "skill_pikkoro",
    "skill_kuririn", "skill_tenshin", "skill_yamcha",
]
PASSIVE_TABLES = [
    "passive_goku", "passive_gohan", "passive_pikkoro",
    "passive_kuririn", "passive_tenshin", "passive_yamcha",
]
CHAR_NAMES = ["Goku", "Gohan", "Piccolo", "Krillin", "Tien", "Yamcha"]

POWER_COLS = [f"power{i}" for i in range(1, 6)]
MP_COLS = [f"use_mp{i}" for i in range(1, 6)]
AP_COLS = [f"use_ap{i}" for i in range(1, 6)]
EFFPOW_COLS = [f"effpow{i}" for i in range(1, 6)]
HIT_COLS = [f"hit{i}" for i in range(1, 6)]

# Columns we NEVER touch (tied to animations/sprites)
FROZEN_COLS = {"blast_type", "range", "width", "height", "name", "help",
               "cond_blast1", "cond_lv1", "cond_blast2", "cond_lv2"}

U16_MAX = 65535
U8_MAX = 255


class KiBlastRebalancer(BaseRandomizer):
    """
    Rebalances Ki Blast skills within each character.

    Config keys:
        mode:           'vanilla' | 'rebalance' | 'chaos'
        power_variance: float (default 0.3 = ±30%)
        cost_variance:  float (default 0.3)
        shuffle_unlock: bool (default True) — shuffle AP unlock order
    """

    def __init__(self, rng, config: dict):
        super().__init__(rng, config)
        self.mode = config.get("mode", "rebalance")
        self.power_variance = config.get("power_variance", 0.3)
        self.cost_variance = config.get("cost_variance", 0.3)
        self.shuffle_unlock = config.get("shuffle_unlock", True)

    def randomize(self, bdat: BdatFile, writer: BdatWriter) -> None:
        self._log(f"=== KiBlastRebalancer: mode={self.mode} ===")

        if self.mode == "vanilla":
            self._log("Mode is 'vanilla' — no changes.")
            return

        variance = self.power_variance
        cost_var = self.cost_variance
        if self.mode == "chaos":
            variance = 0.6
            cost_var = 0.6

        total_skills = 0
        total_passives = 0

        # Process skill tables
        for i, table_name in enumerate(SKILL_TABLES):
            table = bdat.get_table(table_name)
            if table is None:
                continue

            char = CHAR_NAMES[i]
            self._log(f"  {char}: {table.num_rows} skills")

            for row_idx in range(table.num_rows):
                row = table.rows[row_idx]

                # Scale power
                for col in POWER_COLS:
                    old = row.get(col, 0)
                    if old > 0:
                        factor = 1.0 + (self.rng.random_float() * 2 - 1) * variance
                        new = max(1, min(U16_MAX, int(old * factor)))
                        writer.set_value(table_name, row_idx, col, new)

                # Scale MP costs
                for col in MP_COLS:
                    old = row.get(col, 0)
                    if old > 0:
                        factor = 1.0 + (self.rng.random_float() * 2 - 1) * cost_var
                        new = max(1, min(U16_MAX, int(old * factor)))
                        writer.set_value(table_name, row_idx, col, new)

                # Scale hit rates
                for col in HIT_COLS:
                    old = row.get(col, 0)
                    if old > 0:
                        factor = 1.0 + (self.rng.random_float() * 2 - 1) * (variance * 0.5)
                        new = max(1, min(U16_MAX, int(old * factor)))
                        writer.set_value(table_name, row_idx, col, new)

                # Scale effect power
                for col in EFFPOW_COLS:
                    old = row.get(col, 0)
                    if old > 0:
                        factor = 1.0 + (self.rng.random_float() * 2 - 1) * variance
                        new = max(1, min(U8_MAX, int(old * factor)))
                        writer.set_value(table_name, row_idx, col, new)

                total_skills += 1

            # Chaos mode: shuffle effect types between skills of same char
            if self.mode == "chaos":
                efftypes = [table.rows[r].get("efftype", 0)
                            for r in range(table.num_rows)]
                self.rng.shuffle(efftypes)
                for r, eff in enumerate(efftypes):
                    writer.set_value(table_name, r, "efftype", eff)
                self._log(f"    Shuffled effect types for {char}")

        # Process passive tables
        for i, table_name in enumerate(PASSIVE_TABLES):
            table = bdat.get_table(table_name)
            if table is None:
                continue

            char = CHAR_NAMES[i]

            for row_idx in range(table.num_rows):
                row = table.rows[row_idx]

                # Scale passive power values
                for col in POWER_COLS:
                    old = row.get(col, 0)
                    if old > 0:
                        factor = 1.0 + (self.rng.random_float() * 2 - 1) * variance
                        new = max(1, min(U16_MAX, int(old * factor)))
                        writer.set_value(table_name, row_idx, col, new)

                # Shuffle AP unlock costs within this character
                if self.shuffle_unlock:
                    ap_vals = []
                    for col in AP_COLS:
                        v = row.get(col, 0)
                        # Filter out sentinel values (0xFFFFFFFF = not unlockable)
                        if v < 0xFFFFFFF0:
                            ap_vals.append(v)

                    if len(ap_vals) >= 2:
                        self.rng.shuffle(ap_vals)
                        ap_idx = 0
                        for col in AP_COLS:
                            old = row.get(col, 0)
                            if old < 0xFFFFFFF0:
                                writer.set_value(table_name, row_idx, col,
                                                 ap_vals[ap_idx])
                                ap_idx += 1

                total_passives += 1

            self._log(f"    {char}: {table.num_rows} passives rebalanced")

        self._log(f"  Total: {total_skills} skills, {total_passives} passives")
        self._log(f"=== KiBlastRebalancer complete ===")
