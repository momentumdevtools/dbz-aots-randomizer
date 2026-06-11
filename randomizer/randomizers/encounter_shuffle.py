#!/usr/bin/env python3
"""
encounter_shuffle.py — True Encounter Randomizer via CHR File Swap
====================================================================
Pokemon-style encounter randomization for DBZ: Attack of the Saiyans.

The NDS battle engine loads enemy sprites (.chr files) based on the
encounter definition in SB scripts. The `file` field in enemy_param
tells the engine which .chr file to load (e.g., "ene005_01" ->
"btl/ene/ene005_01.chr").

We swap the ACTUAL FILE CONTENTS in the NDS ROM filesystem:
  1. ene005_01.chr now contains the graphics from ene015_01.chr
  2. enemy_param's `file` stays unchanged
  3. But we swap name_id, atk1-4, stats, drops in BDAT to match

The game loads the SAME filename it always loaded, but the file now
contains DIFFERENT graphics + animations. The BDAT identity data
(name, attacks, stats) is swapped to match the new visual.

HERO MODE: When include_heroes=True, player battle sprites
(btl/pc/bat_goku_04.chr etc.) are added to the shuffle pool.
Heroes get the stats of whatever enemy they replace (tier-appropriate)
but show the hero name and sprite.

Constraints:
  - Swap within same SIZE CLASS (formation positioning)
  - Swap within same level TIER (difficulty balance)
  - Never swap boss-immune enemies
  - Only swap sprites that have their own .chr file
  - Keep `file`, `size`, `shadow`, `list` unchanged in BDAT
"""

from randomizer.randomizers.base import BaseRandomizer
from randomizer.rom_io.bdat_reader import BdatFile, BdatTable
from randomizer.rom_io.bdat_writer import BdatWriter
from randomizer.utils.rng import GameRNG

TABLE_NAME = "enemy_param"

# Columns that define the enemy's IDENTITY — these travel with the sprite.
# When we swap CHR file A<->B, we also swap these values for all rows
# that reference file A vs B.
IDENTITY_COLS = (
    # Display name — must match the new sprite
    "name_id",
    # Attack patterns — animations are baked into the .chr sprite
    "atk1", "atk2", "atk3", "atk4",
    "atk1_pow", "atk2_pow", "atk3_pow", "atk4_pow",
    # Palette — travels with CHR content (different palettes = color variants)
    "palno",
    # Core stats
    "lv", "hp", "mp",
    "str", "def", "rec", "tec", "agi", "luc",
    # Rewards
    "power", "zeni", "exp", "ap",
    # Drops
    "item1", "item2", "item3", "item4",
    # Resistances
    "sleep", "bind", "poison", "dark",
    "stan", "panic", "freez", "dead", "carrot",
    "physics", "slash", "blast",
    "atr_fire", "atr_thunder", "atr_ice",
)

# NOT swapped in BDAT:
#   file   — stays the same (we swap the .chr file CONTENTS instead)
#   size   — formation positioning (we group by size instead)
#   shadow — tied to formation/size
#   list   — bestiary flag

CHR_PATH_TEMPLATE = "btl/ene/{}.chr"

# Hero/rival definitions — characters with enemy-format CHR sprites.
# Player battle sprites (btl/pc/) have INCOMPATIBLE animation layouts
# (idle/attack frames are at different indices), so we use boss/rival
# sprites that already exist in btl/ene/ with correct enemy animations.
#
# These are boss characters that normally only appear in scripted fights,
# now injected into random encounters!
#
# boss_idx = index into boss_param / bossEff.bin for animation data
# atk = attack slot weights from boss_param (how often each attack is used)
HERO_SPRITES = {
    # Z-Fighters with enemy-format sprites
    "hero_jackie":   {"ene_file": "ene113_01", "name_id": 183, "size": 0,
                      "boss_idx": 0,  "atk": [8, 8, 2, 22]},   # Jackie Chun
    "hero_piccolo":  {"ene_file": "ene214_01", "name_id": 188, "size": 1,
                      "boss_idx": 5,  "atk": [25, 15, 20, 20]}, # Piccolo
    "hero_chiaotzu": {"ene_file": "ene101_01", "name_id": 187, "size": 0,
                      "boss_idx": 4,  "atk": [100, 0, 0, 0]},   # Chiaotzu
    # Saiyan Saga villains
    "hero_raditz":   {"ene_file": "ene220_01", "name_id": 196, "size": 1,
                      "boss_idx": 12, "atk": [10, 10, 10, 25]}, # Raditz
    "hero_nappa":    {"ene_file": "ene221_01", "name_id": 220, "size": 1,
                      "boss_idx": 37, "atk": [10, 10, 10, 25]}, # Nappa
    "hero_vegeta":   {"ene_file": "ene222_01", "name_id": 222, "size": 0,
                      "boss_idx": 39, "atk": [10, 10, 15, 15]}, # Vegeta
    # Movie villains
    "hero_turles":   {"ene_file": "ene200_01", "name_id": 219, "size": 1,
                      "boss_idx": 36, "atk": [10, 10, 10, 25]}, # Turles
    "hero_broly":    {"ene_file": "ene223_01", "name_id": 225, "size": 2,
                      "boss_idx": 42, "atk": [10, 20, 15, 15]}, # Broly
}


def _get_tier(lv: int) -> int:
    """Map enemy level to difficulty tier."""
    if lv <= 10:
        return 1
    elif lv <= 25:
        return 2
    elif lv <= 40:
        return 3
    elif lv <= 55:
        return 4
    else:
        return 5


def _is_boss_like(row: dict) -> bool:
    """Check if a row represents a boss-like enemy (immune to panic+dead)."""
    return row.get("panic", 0) >= 100 and row.get("dead", 0) >= 100


class EncounterShuffleRandomizer(BaseRandomizer):
    """
    Swaps enemy identities by exchanging .chr file contents in the ROM.

    Config keys:
        mode:            'vanilla' | 'shuffle_tiered' | 'shuffle_wild'
        respect_tiers:   bool (default True) — swap within level tiers
        skip_bosses:     bool (default True) — never swap boss-immune enemies
        available_chrs:  set[str] — set of file names that have .chr files
        include_heroes:  bool (default False) — add player sprites to pool
    """

    def __init__(self, rng: GameRNG, config: dict):
        super().__init__(rng, config)
        self.mode: str = config.get("mode", "shuffle_tiered")
        self.respect_tiers: bool = config.get("respect_tiers", True)
        self.skip_bosses: bool = config.get("skip_bosses", True)
        self.include_heroes: bool = config.get("include_heroes", False)
        # Set of sprite filenames that have actual .chr files in the ROM
        self._available_chrs: set = config.get("available_chrs", set())
        # Result: sprite file content swap mapping
        self._chr_swap_map: dict[str, str] = {}
        # Hero sprites that were assigned (for cross-dir CHR loading)
        self._hero_assignments: dict[str, str] = {}  # dest_ene_file -> hero_key

    def randomize(self, bdat: BdatFile, writer: BdatWriter) -> None:
        self._log(f"=== EncounterShuffleRandomizer: mode={self.mode} ===")

        table = bdat.get_table(TABLE_NAME)
        if table is None:
            self._log(f"WARNING: Table '{TABLE_NAME}' not found")
            return

        if self.mode == "vanilla":
            self._log("Mode is 'vanilla' — no changes.")
            return

        if self.mode in ("shuffle_tiered", "shuffle_wild"):
            self._shuffle_identities(table, writer)

        self._log(f"=== EncounterShuffleRandomizer complete ===")

    def _shuffle_identities(self, table: BdatTable,
                            writer: BdatWriter) -> None:
        """Shuffle enemy identities by sprite file."""
        rows = table.rows

        # Build TWO groups:
        # 1. shuffle_groups — for building the shuffle pool (boss-like excluded)
        # 2. all_file_rows  — for BDAT identity patching (ALL rows included)
        #
        # When a CHR file is swapped, ALL rows referencing that file must
        # get their identity updated — even boss-immune color variants.
        shuffle_groups: dict[str, list[int]] = {}  # file -> [non-boss row_indices]
        all_file_rows: dict[str, list[int]] = {}   # file -> [ALL row_indices]

        skipped_no_chr = 0
        for idx, row in enumerate(rows):
            file_name = row.get("file", "")
            if not file_name:
                continue
            # Skip sprites that don't have their own .chr file
            if self._available_chrs and file_name not in self._available_chrs:
                skipped_no_chr += 1
                continue

            # Always add to all_file_rows (for identity patching)
            if file_name not in all_file_rows:
                all_file_rows[file_name] = []
            all_file_rows[file_name].append(idx)

            # Only add to shuffle_groups if not boss-like (for pool building)
            if self.skip_bosses and _is_boss_like(row):
                continue
            if file_name not in shuffle_groups:
                shuffle_groups[file_name] = []
            shuffle_groups[file_name].append(idx)

        if skipped_no_chr:
            self._log(f"  {skipped_no_chr} rows skipped (no .chr file)")

        # Build pools of unique sprites, keyed by (tier, size)
        # For tier/size, use the FIRST row of each sprite group
        sprite_pool: dict[tuple[int, int], list[str]] = {}

        for file_name, row_indices in shuffle_groups.items():
            first_row = rows[row_indices[0]]
            lv = first_row.get("lv", 1)
            size = first_row.get("size", 0)

            if self.mode == "shuffle_wild":
                tier = 0
            else:
                tier = _get_tier(lv) if self.respect_tiers else 0

            key = (tier, size)
            if key not in sprite_pool:
                sprite_pool[key] = []
            sprite_pool[key].append(file_name)

        # Add hero sprites to pools if enabled
        if self.include_heroes:
            heroes_added = 0
            for hero_key, hero_info in HERO_SPRITES.items():
                hero_size = hero_info["size"]

                if self.mode == "shuffle_wild":
                    # Add heroes to ALL tiers (wild mode = no tier restriction)
                    key = (0, hero_size)
                    if key not in sprite_pool:
                        sprite_pool[key] = []
                    sprite_pool[key].append(hero_key)
                    heroes_added += 1
                else:
                    # Add heroes to EVERY tier for their size class
                    # This way they can appear at any point in the game
                    for tier in range(1, 6):
                        key = (tier, hero_size)
                        if key in sprite_pool and len(sprite_pool[key]) >= 2:
                            sprite_pool[key].append(hero_key)
                            heroes_added += 1

            self._log(f"  🦸 {heroes_added} hero sprite entries added to pools")

        # Log pool sizes
        boss_count = sum(1 for r in rows if _is_boss_like(r))
        self._log(f"  {boss_count} boss-immune enemies skipped")
        size_names = {0: "small", 1: "medium", 2: "large"}
        for key in sorted(sprite_pool.keys()):
            tier, size = key
            sname = size_names.get(size, f"size={size}")
            sprites = sprite_pool[key]
            hero_count = sum(1 for s in sprites if s.startswith("hero_"))
            hero_note = f" (+{hero_count} heroes)" if hero_count else ""
            if self.mode == "shuffle_wild":
                self._log(f"  Wild / {sname}: {len(sprites)} sprites{hero_note}")
            else:
                self._log(f"  Tier {tier} / {sname}: {len(sprites)} sprites{hero_note}")

        # Build the sprite shuffle mapping
        total_swaps = 0
        sprite_mapping: dict[str, str] = {}  # old_file -> new_file

        for key in sorted(sprite_pool.keys()):
            sprites = sprite_pool[key]
            if len(sprites) < 2:
                continue

            # Fisher-Yates shuffle
            shuffled = list(sprites)
            self.rng.shuffle(shuffled)

            for i, original in enumerate(sprites):
                new_sprite = shuffled[i]
                if original != new_sprite:
                    sprite_mapping[original] = new_sprite
                    total_swaps += 1

        self._log(f"  Sprite-level swaps: {total_swaps}")

        if not sprite_mapping:
            self._log("  No swaps to perform.")
            return

        # Separate hero->ene assignments from ene->ene swaps
        chr_swap_map = {}
        hero_assignments = {}

        for dest_file, source_file in sprite_mapping.items():
            if dest_file.startswith("hero_"):
                # A hero slot was assigned to an enemy → hero becomes an enemy
                # But heroes don't have enemy CHR files, this means the hero
                # entry in the pool got some other sprite. We skip this direction.
                # The hero's CHR only matters when SOURCE is a hero (below).
                continue

            if source_file.startswith("hero_"):
                # An enemy slot is getting a HERO sprite
                hero_assignments[dest_file] = source_file
                self._log(
                    f"  🦸 {dest_file} gets {source_file} sprite!"
                )
            else:
                chr_swap_map[dest_file] = source_file

        self._chr_swap_map = chr_swap_map
        self._hero_assignments = hero_assignments

        # Now swap BDAT identity columns for all affected rows.
        # CRITICAL: BdatWriter.set_value() updates table.rows[] in-memory!
        # This means we MUST snapshot ALL source profiles BEFORE writing
        # ANY values, otherwise chain swaps (A→B→C→A) would read
        # already-modified data from earlier iterations.

        # Phase 1: READ all source profiles (before any writes)
        swap_plan = []  # list of (dest_idx, profile_dict, old_file, new_file)
        for old_file, new_file in sprite_mapping.items():
            if old_file == new_file:
                continue
            if old_file.startswith("hero_"):
                # Heroes don't have enemy_param rows — skip reverse direction
                continue

            old_rows = all_file_rows.get(old_file, [])
            if not old_rows:
                continue

            if new_file.startswith("hero_"):
                # Hero source: patch name, attack weights & palette
                # Stats stay from original enemy (tier-appropriate)
                hero_info = HERO_SPRITES[new_file]
                atk_weights = hero_info.get("atk", [30, 30, 30, 0])
                for idx in old_rows:
                    profile = {
                        "name_id": hero_info["name_id"],
                        "palno": 0,  # Boss sprites use palette 0
                        # Attack weights must match bossEff slots
                        "atk1": atk_weights[0],
                        "atk2": atk_weights[1],
                        "atk3": atk_weights[2],
                        "atk4": atk_weights[3],
                        # Reset power bonuses (bosses use 0)
                        "atk1_pow": 0,
                        "atk2_pow": 0,
                        "atk3_pow": 0,
                        "atk4_pow": 0,
                    }
                    swap_plan.append((idx, profile, old_file, new_file))
            else:
                # Normal ene->ene swap: full identity copy
                new_rows = all_file_rows.get(new_file, [])
                if not new_rows:
                    continue

                # Snapshot profiles from the SOURCE sprite's rows
                new_profiles = []
                for nr_idx in new_rows:
                    profile = {}
                    for col in IDENTITY_COLS:
                        if table.get_column(col) is not None:
                            profile[col] = rows[nr_idx].get(col, 0)
                    new_profiles.append(profile)

                for i, idx in enumerate(old_rows):
                    profile = new_profiles[min(i, len(new_profiles) - 1)]
                    swap_plan.append((idx, profile, old_file, new_file))

        # Phase 2: WRITE all profiles (safe — no reads from rows[] after this)
        bdat_swaps = 0
        for idx, profile, old_file, new_file in swap_plan:
            old_name_id = rows[idx].get("name_id", 0)
            new_name_id = profile.get("name_id", 0)

            for col, new_val in profile.items():
                writer.set_value(TABLE_NAME, idx, col, new_val)

            if old_name_id != new_name_id:
                bdat_swaps += 1
                if new_file.startswith("hero_"):
                    self._log(
                        f"    [{idx}] {old_file}(nid={old_name_id}) -> "
                        f"🦸 {new_file}(nid={new_name_id})"
                    )
                else:
                    self._log(
                        f"    [{idx}] {old_file}(nid={old_name_id}) -> "
                        f"{new_file}(nid={new_name_id}) "
                        f"lv={profile.get('lv', 0)}"
                    )

        self._log(f"  BDAT identity swaps: {bdat_swaps}")

    def get_chr_swap_map(self) -> dict:
        """Return the sprite file content swap mapping.
        Keys/values are sprite file basenames (e.g., "ene005_01").
        Semantics: file `key`.chr should receive the CONTENTS of `value`.chr
        """
        return self._chr_swap_map

    def get_hero_assignments(self) -> dict:
        """Return hero sprite assignments.
        Keys are enemy file basenames, values are hero keys (e.g., "hero_goku").
        The ROM builder uses this to copy btl/pc/ CHR files into btl/ene/ slots.
        """
        return self._hero_assignments
