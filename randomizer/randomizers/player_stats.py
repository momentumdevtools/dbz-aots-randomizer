#!/usr/bin/env python3
"""
player_stats.py — Player Character Stat Randomizer
=====================================================
Randomizes base stats, growth curves, and innate resistances for the
6 playable characters (Goku, Gohan, Piccolo, Krillin, Tenshinhan, Yamcha).

NPC guest slots (rows 6-7) are NEVER modified to prevent softlocks.

Modes:
    'vanilla'  — No changes
    'shuffle'  — Shuffle stat distributions between playable characters
                 (Goku might get Yamcha's growth curve, etc.)
    'scale'    — Scale base stats and growth by random factor
    'chaos'    — Randomize stats within reasonable bounds
"""

from randomizer.randomizers.base import BaseRandomizer
from randomizer.rom_io.bdat_reader import BdatFile
from randomizer.rom_io.bdat_writer import BdatWriter
from randomizer.data.players import PLAYABLE_INDICES


# Columns containing base stats that can be randomized
BASE_STAT_COLS = ('hp', 'mp', 'str', 'def', 'rec', 'tec', 'agi', 'luc')

# Growth columns — phase 1 (up to exlv)
GROWTH_P1_COLS = ('hpup', 'mpup', 'strup', 'defup', 'recup',
                  'tecup', 'agiup', 'lucup')

# Growth columns — phase 2 (after exlv)
GROWTH_P2_COLS = ('hpup2', 'mpup2', 'strup2', 'defup2', 'recup2',
                  'tecup2', 'agiup2', 'lucup2')

# Player resistance columns (note: slightly different names from enemy_param)
PLAYER_RESIST_COLS = ('poison', 'sleep', 'dark', 'bind', 'stan',
                      'panic', 'freez', 'dead',
                      'physics', 'slash', 'blast',
                      'atr_fire', 'atr_thunder', 'atr_ice')

TABLE_NAME = 'player_param'


class PlayerStatRandomizer(BaseRandomizer):
    """
    Randomizes playable character stats and growth curves.

    Config keys:
        mode:          'vanilla' | 'shuffle' | 'scale' | 'chaos'
        min_scale:     float (default 0.8) — minimum scale factor
        max_scale:     float (default 1.2) — maximum scale factor
        shuffle_growth: bool (default True) — also shuffle growth curves
        randomize_resists: bool (default False) — randomize innate resistances
    """

    def __init__(self, rng, config: dict):
        super().__init__(rng, config)
        self.mode = config.get('mode', 'vanilla')
        self.min_scale = config.get('min_scale', 0.8)
        self.max_scale = config.get('max_scale', 1.2)
        self.shuffle_growth = config.get('shuffle_growth', True)
        self.shuffle_base = config.get('shuffle_base', True)
        self.randomize_resists = config.get('randomize_resists', False)

    def randomize(self, bdat: BdatFile, writer: BdatWriter) -> None:
        self._log(f"=== PlayerStatRandomizer: mode={self.mode} ===")

        table = bdat.get_table(TABLE_NAME)
        if table is None:
            self._log(f"WARNING: Table '{TABLE_NAME}' not found")
            return

        if self.mode == 'vanilla':
            self._log("Mode is 'vanilla' — no changes.")
            return

        if self.mode == 'shuffle':
            self._shuffle_stats(table, writer)
        elif self.mode == 'scale':
            self._scale_stats(table, writer)
        elif self.mode == 'chaos':
            self._chaos_stats(table, writer)

        if self.randomize_resists:
            self._randomize_resistances(table, writer)

        self._log(f"=== PlayerStatRandomizer complete ===")

    def _shuffle_stats(self, table, writer):
        """Shuffle stat profiles between playable characters."""
        rows = table.rows

        # Collect stat profiles from playable characters
        base_profiles = []
        growth_p1_profiles = []
        growth_p2_profiles = []

        for idx in PLAYABLE_INDICES:
            row = rows[idx]
            base_profiles.append({c: row.get(c, 0) for c in BASE_STAT_COLS})
            growth_p1_profiles.append({c: row.get(c, 0) for c in GROWTH_P1_COLS})
            growth_p2_profiles.append({c: row.get(c, 0) for c in GROWTH_P2_COLS})

        # Shuffle the profiles independently
        if self.shuffle_base:
            self.rng.shuffle(base_profiles)
        if self.shuffle_growth:
            self.rng.shuffle(growth_p1_profiles)
            self.rng.shuffle(growth_p2_profiles)

        # Write back shuffled profiles
        for i, idx in enumerate(PLAYABLE_INDICES):
            row = rows[idx]
            name_id = row.get('name_id', idx + 1)

            # Base stats
            if self.shuffle_base:
                for col, new_val in base_profiles[i].items():
                    old_val = row.get(col, 0)
                    if old_val != new_val:
                        writer.set_value(TABLE_NAME, idx, col, new_val)
                        self._log(f"  [{name_id}] {col}: {old_val} -> {new_val}")

            # Growth phase 1
            if self.shuffle_growth:
                for col, new_val in growth_p1_profiles[i].items():
                    old_val = row.get(col, 0)
                    if old_val != new_val:
                        writer.set_value(TABLE_NAME, idx, col, new_val)
                        self._log(f"  [{name_id}] {col}: {old_val} -> {new_val}")

                # Growth phase 2
                for col, new_val in growth_p2_profiles[i].items():
                    old_val = row.get(col, 0)
                    if old_val != new_val:
                        writer.set_value(TABLE_NAME, idx, col, new_val)
                        self._log(f"  [{name_id}] {col}: {old_val} -> {new_val}")

        self._log(f"  Shuffled {len(PLAYABLE_INDICES)} character stat profiles")

    def _scale_stats(self, table, writer):
        """Scale each stat by a random factor."""
        for idx in PLAYABLE_INDICES:
            row = table.rows[idx]
            name_id = row.get('name_id', idx + 1)

            # Base stats (u8 for most, u16 for hp/mp/ap)
            if self.shuffle_base:
                for col in BASE_STAT_COLS:
                    old_val = row.get(col, 0)
                    if old_val == 0:
                        continue
                    new_val = self.rng.scale_value(old_val, self.min_scale,
                                                    self.max_scale, clamp_min=1)
                    if col in ('hp', 'mp'):
                        new_val = min(65535, new_val)
                    else:
                        new_val = min(255, new_val)
                    if old_val != new_val:
                        writer.set_value(TABLE_NAME, idx, col, new_val)
                        self._log(f"  [{name_id}] {col}: {old_val} -> {new_val}")

            # Growth curves — scale both phases
            for col in list(GROWTH_P1_COLS) + list(GROWTH_P2_COLS):
                old_val = row.get(col, 0)
                if old_val == 0:
                    continue
                new_val = self.rng.scale_value(old_val, self.min_scale,
                                                self.max_scale, clamp_min=0,
                                                clamp_max=255)
                if old_val != new_val:
                    writer.set_value(TABLE_NAME, idx, col, new_val)
                    self._log(f"  [{name_id}] {col}: {old_val} -> {new_val}")

    def _chaos_stats(self, table, writer):
        """Fully randomize stats within reasonable bounds."""
        for idx in PLAYABLE_INDICES:
            row = table.rows[idx]
            name_id = row.get('name_id', idx + 1)

            # Base HP: 200-600, MP: 80-250
            new_hp = self.rng.randint(200, 600)
            new_mp = self.rng.randint(80, 250)
            writer.set_value(TABLE_NAME, idx, 'hp', new_hp)
            writer.set_value(TABLE_NAME, idx, 'mp', new_mp)
            self._log(f"  [{name_id}] hp: {row.get('hp',0)} -> {new_hp}")
            self._log(f"  [{name_id}] mp: {row.get('mp',0)} -> {new_mp}")

            # Core stats: 5-20 each
            for col in ('str', 'def', 'rec', 'tec', 'agi', 'luc'):
                old_val = row.get(col, 0)
                new_val = self.rng.randint(5, 20)
                writer.set_value(TABLE_NAME, idx, col, new_val)
                self._log(f"  [{name_id}] {col}: {old_val} -> {new_val}")

            # Growth phase 1: 0-3 per stat, HP 15-30, MP 4-10
            writer.set_value(TABLE_NAME, idx, 'hpup',
                             self.rng.randint(15, 30))
            writer.set_value(TABLE_NAME, idx, 'mpup',
                             self.rng.randint(4, 10))
            for col in ('strup', 'defup', 'recup', 'tecup', 'agiup', 'lucup'):
                writer.set_value(TABLE_NAME, idx, col, self.rng.randint(0, 3))

            # Growth phase 2: similar but slightly higher
            writer.set_value(TABLE_NAME, idx, 'hpup2',
                             self.rng.randint(25, 40))
            writer.set_value(TABLE_NAME, idx, 'mpup2',
                             self.rng.randint(6, 12))
            for col in ('strup2', 'defup2', 'recup2', 'tecup2', 'agiup2', 'lucup2'):
                writer.set_value(TABLE_NAME, idx, col, self.rng.randint(1, 3))

            # Transition level: 15-40
            writer.set_value(TABLE_NAME, idx, 'exlv',
                             self.rng.randint(15, 40))

    def _randomize_resistances(self, table, writer):
        """Randomize innate resistances for playable characters."""
        for idx in PLAYABLE_INDICES:
            row = table.rows[idx]
            name_id = row.get('name_id', idx + 1)

            for col in PLAYER_RESIST_COLS:
                old_val = row.get(col, 0)
                # Random resistance in [-20, 20] range
                new_val = self.rng.randint(-20, 20)
                new_val = max(-128, min(127, new_val))
                if old_val != new_val:
                    writer.set_value(TABLE_NAME, idx, col, new_val)
                    self._log(f"  [{name_id}] {col}: {old_val} -> {new_val}")

    def _log(self, msg: str):
        self.log.append(msg)
