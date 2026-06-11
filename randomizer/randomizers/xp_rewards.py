#!/usr/bin/env python3
"""
xp_rewards.py — XP, Zeni, and AP Reward Scaler
=================================================
Scales enemy reward values (exp, zeni, ap) by configurable multipliers.
This is the simplest randomizer — pure multiplication with clamping.
"""

from .base import BaseRandomizer
from ..rom_io.bdat_reader import BdatFile
from ..rom_io.bdat_writer import BdatWriter


class XpRewardRandomizer(BaseRandomizer):
    """
    Scales XP, Zeni, and AP rewards for all enemies and bosses.

    Config options:
        xp_multiplier:   float (default 1.0) — global XP multiplier
        zeni_multiplier: float (default 1.0) — global Zeni multiplier
        ap_multiplier:   float (default 1.0) — global AP multiplier
    """

    def randomize(self, bdat: BdatFile, writer: BdatWriter) -> None:
        xp_mult = self.config.get("xp_multiplier", 1.0)
        zeni_mult = self.config.get("zeni_multiplier", 1.0)
        ap_mult = self.config.get("ap_multiplier", 1.0)

        self.log.append(
            f"Reward scaling: XP x{xp_mult:.1f}, "
            f"Zeni x{zeni_mult:.1f}, AP x{ap_mult:.1f}"
        )

        # Scale enemy_param rewards
        enemy_table = bdat.get_table("enemy_param")
        if enemy_table:
            count = self._scale_table(
                writer, "enemy_param", enemy_table.num_rows,
                xp_mult, zeni_mult, ap_mult
            )
            self.log.append(f"  enemy_param: {count} values scaled")

        # Scale boss_param rewards
        boss_table = bdat.get_table("boss_param")
        if boss_table:
            count = self._scale_table(
                writer, "boss_param", boss_table.num_rows,
                xp_mult, zeni_mult, ap_mult
            )
            self.log.append(f"  boss_param: {count} values scaled")

    def _scale_table(self, writer: BdatWriter, table_name: str,
                     num_rows: int, xp_mult: float, zeni_mult: float,
                     ap_mult: float) -> int:
        """Scale rewards for all rows in a table. Returns patch count."""
        count = 0
        bdat = writer._bdat  # access the underlying bdat for reading

        table = bdat.get_table(table_name)
        if not table:
            return 0

        for row_idx in range(num_rows):
            row = table.get_row(row_idx)
            if not row:
                continue

            # XP (u32, max 4294967295)
            if "exp" in row and xp_mult != 1.0:
                old_xp = row["exp"]
                new_xp = max(1, min(4294967295, int(old_xp * xp_mult)))
                if new_xp != old_xp:
                    writer.set_value(table_name, row_idx, "exp", new_xp)
                    count += 1

            # Zeni (u32)
            if "zeni" in row and zeni_mult != 1.0:
                old_zeni = row["zeni"]
                new_zeni = max(0, min(4294967295, int(old_zeni * zeni_mult)))
                if new_zeni != old_zeni:
                    writer.set_value(table_name, row_idx, "zeni", new_zeni)
                    count += 1

            # AP (u16, max 65535)
            if "ap" in row and ap_mult != 1.0:
                old_ap = row["ap"]
                new_ap = max(0, min(65535, int(old_ap * ap_mult)))
                if new_ap != old_ap:
                    writer.set_value(table_name, row_idx, "ap", new_ap)
                    count += 1

        return count
