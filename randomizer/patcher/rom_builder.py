#!/usr/bin/env python3
"""
rom_builder.py — Final ROM Build Pipeline
===========================================
Orchestrates the full randomization process:
  1. Load original ROM via ndspy
  2. Extract BDAT data
  3. Run all enabled randomizer passes
  4. Patch BDAT back into ROM
  5. Save randomized ROM

This is the central coordinator that ties together:
  - NdsRom (ROM I/O)
  - BdatReader/Writer (BDAT manipulation)
  - All Randomizer passes (enemy stats, encounters, etc.)
"""

import os
import time
import json
from typing import List, Optional

from ..rom_io.nds_rom import NdsRom
from ..rom_io.bdat_reader import read_bdat
from ..rom_io.bdat_writer import BdatWriter
from ..config import RandomizerConfig
from ..utils.rng import GameRNG


class RomBuilder:
    """
    Orchestrates the full ROM randomization pipeline.

    Usage:
        config = RandomizerConfig(seed=42, rom_path="path/to/rom.nds")
        builder = RomBuilder(config)
        builder.build()
    """

    def __init__(self, config: RandomizerConfig):
        self.config = config
        self.log: List[str] = []
        self._rom: Optional[NdsRom] = None
        self._rng: Optional[GameRNG] = None

    def build(self) -> str:
        """
        Execute the full randomization pipeline.

        Returns:
            Path to the generated ROM file.
        """
        start_time = time.time()
        self._log("=" * 60)
        self._log("DBZ: Attack of the Saiyans — ROM Randomizer v0.1.0")
        self._log("=" * 60)
        self._log(f"Seed: {self.config.seed}")
        self._log("")

        # Step 1: Load ROM
        self._log("[1/5] Loading ROM...")
        self._rom = NdsRom.from_file(self.config.rom_path)
        self._log(f"  Title: {self._rom.title}")
        self._log(f"  Code:  {self._rom.game_code}")
        self._log(f"  ARM9:  {len(self._rom.arm9)} bytes")

        # Step 2: Extract BDAT
        self._log(f"\n[2/5] Extracting BDAT ({self.config.locale})...")
        bdat_bytes = self._rom.get_bdat(self.config.locale)
        bdat = read_bdat(bdat_bytes)
        self._log(f"  Tables: {bdat.table_count}")
        self._log(f"  Size:   {len(bdat_bytes)} bytes")

        original_size = len(bdat_bytes)

        # Step 3: Merge eneEff + bossEff and patch ARM9
        self._log("\n[3/6] Merging eneEff/bossEff & patching ARM9...")
        try:
            from .arm9_eff_merger import apply_eff_merge
            if apply_eff_merge(self._rom, self._log):
                self._log("  eneEff/bossEff merge complete")
            else:
                self._log("  WARNING: eneEff/bossEff merge failed")
        except Exception as e:
            self._log(f"  WARNING: eneEff/bossEff merge skipped: {e}")

        # Step 4: Initialize RNG and run randomizers
        self._log(f"\n[4/6] Randomizing (seed={self.config.seed})...")
        self._rng = GameRNG(self.config.seed)
        writer = BdatWriter(bdat)

        randomizers_run = self._run_randomizers(bdat, writer)
        self._log(f"  Randomizers executed: {randomizers_run}")
        self._log(f"  Total cells patched: {writer.patch_count}")

        # Step 5: Patch BDAT back into ROM
        self._log("\n[5/6] Patching ROM...")
        patched_bdat = writer.build()

        assert len(patched_bdat) == original_size, (
            f"BDAT size mismatch! {len(patched_bdat)} != {original_size}. "
            f"This is a critical bug — aborting."
        )
        self._log(f"  BDAT size verified: {len(patched_bdat)} bytes (unchanged)")

        self._rom.set_bdat(patched_bdat, self.config.locale)
        self._log(f"  BDAT written to ROM ({self.config.locale})")

        # Also patch ALL other locale BDATs by copying the data rows
        # from the primary locale. Each table has its own file_offset
        # (absolute in the BDAT file) and data_offset (relative to table).
        # The actual data is at: file_offset + data_offset
        all_locales = ["EN", "FR", "GR", "IT", "JP", "SP", "US"]
        for loc in all_locales:
            if loc == self.config.locale:
                continue
            try:
                loc_bdat_bytes = self._rom.get_bdat(loc)
                loc_bdat = read_bdat(loc_bdat_bytes)
                loc_data = bytearray(loc_bdat_bytes)

                tables_copied = 0
                for primary_table in bdat.tables:
                    loc_table = loc_bdat.get_table(primary_table.name)
                    if loc_table is None:
                        continue
                    if (loc_table.row_size != primary_table.row_size or
                            loc_table.num_rows != primary_table.num_rows):
                        self._log(f"    {loc}/{primary_table.name}: structure mismatch, skip")
                        continue

                    # Absolute data positions in each BDAT file
                    src_abs = primary_table.file_offset + primary_table.data_offset
                    dst_abs = loc_table.file_offset + loc_table.data_offset
                    data_len = primary_table.num_rows * primary_table.row_size

                    # Copy data rows from patched primary BDAT to locale BDAT
                    loc_data[dst_abs:dst_abs + data_len] = \
                        patched_bdat[src_abs:src_abs + data_len]
                    tables_copied += 1

                self._rom.set_bdat(bytes(loc_data), loc)
                self._log(f"  BDAT data rows copied to {loc} ({tables_copied} tables)")
            except Exception as e:
                self._log(f"  Warning: Could not patch {loc}: {e}")

        # Step 6: Save
        output_path = self.config.output_path or self.config.default_output_path
        # Ensure output dir exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        self._log(f"\n[6/6] Saving ROM...")
        rom_size = self._rom.save(output_path)

        elapsed = time.time() - start_time
        self._log(f"  Output: {output_path}")
        self._log(f"  Size:   {rom_size:,} bytes")
        self._log(f"  Time:   {elapsed:.2f}s")
        self._log("")
        self._log("=" * 60)
        self._log("Randomization complete!")
        self._log(f"Seed: {self.config.seed}")
        self._log("=" * 60)

        # Save spoiler log
        self._save_spoiler_log(output_path)

        return output_path

    def _run_randomizers(self, bdat, writer: BdatWriter) -> int:
        """Run all enabled randomizer passes. Returns count of passes run."""
        count = 0

        # Encounter Shuffle (Pokemon-style identity swap) — MUST RUN FIRST
        # Swaps whole enemy identities before any stat modifications
        if self.config.encounter_shuffle.enabled:
            self._log("\n  --- Encounter Shuffle ---")
            try:
                from ..randomizers.encounter_shuffle import EncounterShuffleRandomizer

                # Scan ROM for available .chr files
                available_chrs = set()
                if self._rom:
                    for f in self._rom.list_files("btl/ene/"):
                        if f.endswith(".chr") and "ene" in f:
                            # Extract basename: "btl/ene/ene005_01.chr" -> "ene005_01"
                            basename = f.rsplit("/", 1)[-1].replace(".chr", "")
                            available_chrs.add(basename)
                    self._log(f"    Found {len(available_chrs)} .chr files in ROM")

                rng = self._rng.fork("encounter_shuffle")
                randomizer = EncounterShuffleRandomizer(rng, {
                    "mode": self.config.encounter_shuffle.mode,
                    "respect_tiers": self.config.encounter_shuffle.respect_tiers,
                    "skip_bosses": self.config.encounter_shuffle.skip_bosses,
                    "available_chrs": available_chrs,
                    "include_heroes": self.config.encounter_shuffle.include_heroes,
                    "scale_to_area": self.config.encounter_shuffle.scale_to_area,
                    "force_enemy": self.config.encounter_shuffle.force_enemy,
                })
                randomizer.randomize(bdat, writer)
                for line in randomizer.get_log():
                    self._log(f"    {line}")

                # Apply CHR file content swaps in the ROM
                chr_map = randomizer.get_chr_swap_map()
                if chr_map and self._rom:
                    self._log(f"    --- Applying {len(chr_map)} CHR file swaps ---")
                    self._apply_chr_swaps(chr_map)

                    # Also swap eneEff.bin entries to match
                    self._apply_eff_swaps(chr_map, bdat)

                # Apply hero sprite assignments (copy btl/pc/ -> btl/ene/)
                hero_map = randomizer.get_hero_assignments()
                if hero_map and self._rom:
                    self._log(f"    --- Applying {len(hero_map)} hero sprite injections ---")
                    self._apply_hero_chr(hero_map, bdat)

                count += 1
            except ImportError as e:
                self._log(f"  [SKIP] Encounter shuffle not available: {e}")

        # Enemy Stats Randomizer
        if self.config.enemy_stats.enabled:
            self._log("\n  --- Enemy Stats ---")
            try:
                from ..randomizers.enemy_stats import EnemyStatRandomizer
                rng = self._rng.fork("enemy_stats")
                randomizer = EnemyStatRandomizer(rng, {
                    "mode": self.config.enemy_stats.mode,
                    "min_scale": self.config.enemy_stats.min_scale,
                    "max_scale": self.config.enemy_stats.max_scale,
                    "boss_enabled": self.config.enemy_stats.boss_enabled,
                    "boss_min_scale": self.config.enemy_stats.boss_min_scale,
                    "boss_max_scale": self.config.enemy_stats.boss_max_scale,
                    "preserve_level": self.config.enemy_stats.preserve_level,
                })
                randomizer.randomize(bdat, writer)
                for line in randomizer.get_log():
                    self._log(f"    {line}")
                count += 1
            except ImportError as e:
                self._log(f"  [SKIP] Enemy stats randomizer not available: {e}")

        # Encounter Randomizer
        if self.config.encounters.enabled:
            self._log("\n  --- Encounters ---")
            try:
                from ..randomizers.encounters import EncounterRandomizer
                rng = self._rng.fork("encounters")
                randomizer = EncounterRandomizer(rng, {
                    "mode": self.config.encounters.mode,
                    "shuffle_drops": self.config.encounters.shuffle_drops,
                    "random_resists": self.config.encounters.random_resists,
                    "resist_variance": self.config.encounters.resist_variance,
                })
                randomizer.randomize(bdat, writer)
                for line in randomizer.get_log():
                    self._log(f"    {line}")
                count += 1
            except ImportError as e:
                self._log(f"  [SKIP] Encounter randomizer not available: {e}")

        # XP/Reward Scaler
        if self.config.xp_rewards.enabled:
            self._log("\n  --- XP/Rewards ---")
            try:
                from ..randomizers.xp_rewards import XpRewardRandomizer
                rng = self._rng.fork("xp_rewards")
                randomizer = XpRewardRandomizer(rng, {
                    "xp_multiplier": self.config.xp_rewards.xp_multiplier,
                    "zeni_multiplier": self.config.xp_rewards.zeni_multiplier,
                    "ap_multiplier": self.config.xp_rewards.ap_multiplier,
                })
                randomizer.randomize(bdat, writer)
                for line in randomizer.get_log():
                    self._log(f"    {line}")
                count += 1
            except ImportError as e:
                self._log(f"  [SKIP] XP reward randomizer not available: {e}")

        # Shop Item Randomizer
        if self.config.shop_items.enabled:
            self._log("\n  --- Shop Items ---")
            try:
                from ..randomizers.shop_items import ShopItemRandomizer
                rng = self._rng.fork("shop_items")
                randomizer = ShopItemRandomizer(rng, {
                    "mode": self.config.shop_items.mode,
                    "price_variance": self.config.shop_items.price_variance,
                })
                randomizer.randomize(bdat, writer)
                for line in randomizer.get_log():
                    self._log(f"    {line}")
                count += 1
            except ImportError as e:
                self._log(f"  [SKIP] Shop item randomizer not available: {e}")

        # Player Stats Randomizer
        if self.config.player_stats.enabled:
            self._log("\n  --- Player Stats ---")
            try:
                from ..randomizers.player_stats import PlayerStatRandomizer
                rng = self._rng.fork("player_stats")
                randomizer = PlayerStatRandomizer(rng, {
                    "mode": self.config.player_stats.mode,
                    "min_scale": self.config.player_stats.min_scale,
                    "max_scale": self.config.player_stats.max_scale,
                    "shuffle_growth": self.config.player_stats.shuffle_growth,
                    "shuffle_base": self.config.player_stats.shuffle_base,
                    "randomize_resists": self.config.player_stats.randomize_resists,
                })
                randomizer.randomize(bdat, writer)
                for line in randomizer.get_log():
                    self._log(f"    {line}")
                count += 1
            except ImportError as e:
                self._log(f"  [SKIP] Player stats randomizer not available: {e}")

        # Ki Blast Rebalancer
        if self.config.ki_blasts.enabled:
            self._log("\n  --- Ki Blast Rebalancer ---")
            try:
                from ..randomizers.ki_blast_rebalancer import KiBlastRebalancer
                rng = self._rng.fork("ki_blasts")
                randomizer = KiBlastRebalancer(rng, {
                    "mode": self.config.ki_blasts.mode,
                    "power_variance": self.config.ki_blasts.power_variance,
                    "cost_variance": self.config.ki_blasts.cost_variance,
                    "shuffle_unlock": self.config.ki_blasts.shuffle_unlock,
                })
                randomizer.randomize(bdat, writer)
                for line in randomizer.get_log():
                    self._log(f"    {line}")
                count += 1
            except ImportError as e:
                self._log(f"  [SKIP] Ki Blast rebalancer not available: {e}")

        # Drop Shuffle
        if self.config.drop_shuffle.enabled:
            self._log("\n  --- Drop Shuffle ---")
            try:
                from ..randomizers.drop_shuffle import DropShuffleRandomizer
                rng = self._rng.fork("drop_shuffle")
                randomizer = DropShuffleRandomizer(rng, {
                    "mode": self.config.drop_shuffle.mode,
                    "include_bosses": self.config.drop_shuffle.include_bosses,
                })
                randomizer.randomize(bdat, writer)
                for line in randomizer.get_log():
                    self._log(f"    {line}")
                count += 1
            except ImportError as e:
                self._log(f"  [SKIP] Drop shuffle not available: {e}")

        # Boss Scaler
        if self.config.boss_scaler.enabled:
            self._log("\n  --- Boss Scaler ---")
            try:
                from ..randomizers.boss_scaler import BossScaler
                rng = self._rng.fork("boss_scaler")
                randomizer = BossScaler(rng, {
                    "mode": self.config.boss_scaler.mode,
                    "hp_multiplier": self.config.boss_scaler.hp_multiplier,
                    "stat_multiplier": self.config.boss_scaler.stat_multiplier,
                    "randomize_angry": self.config.boss_scaler.randomize_angry,
                })
                randomizer.randomize(bdat, writer)
                for line in randomizer.get_log():
                    self._log(f"    {line}")
                count += 1
            except ImportError as e:
                self._log(f"  [SKIP] Boss scaler not available: {e}")

        # Chaos Resistances
        if self.config.chaos_resists.enabled:
            self._log("\n  --- Chaos Resistances ---")
            try:
                from ..randomizers.chaos_resistances import ChaosResistanceRandomizer
                rng = self._rng.fork("chaos_resists")
                randomizer = ChaosResistanceRandomizer(rng, {
                    "mode": self.config.chaos_resists.mode,
                    "include_bosses": self.config.chaos_resists.include_bosses,
                })
                randomizer.randomize(bdat, writer)
                for line in randomizer.get_log():
                    self._log(f"    {line}")
                count += 1
            except ImportError as e:
                self._log(f"  [SKIP] Chaos resistances not available: {e}")

        # Music Shuffle (operates on ROM filesystem, not BDAT)
        if self.config.music_shuffle.enabled:
            self._log("\n  --- Music Shuffle ---")
            try:
                from randomizer.randomizers.music_shuffle import MusicShuffleRandomizer
                rng = self._rng.fork("music_shuffle")
                randomizer = MusicShuffleRandomizer(rng, {
                    "mode": self.config.music_shuffle.mode,
                })
                randomizer.randomize_music(self._rom)
                for line in randomizer.get_log():
                    self._log(f"    {line}")
                count += 1
            except ImportError as e:
                self._log(f"  [SKIP] Music shuffle not available: {e}")
            except Exception as e:
                self._log(f"  [ERROR] Music shuffle failed: {e}")

        # Palette Randomizer (operates on ROM filesystem, not BDAT)
        if self.config.palette.enabled:
            self._log("\n  --- Palette Randomizer ---")
            try:
                from randomizer.randomizers.palette_randomizer import PaletteRandomizer
                rng = self._rng.fork("palette")
                randomizer = PaletteRandomizer(rng, {
                    "mode": self.config.palette.mode,
                })
                randomizer.randomize_palettes(self._rom)
                for line in randomizer.get_log():
                    self._log(f"    {line}")
                count += 1
            except ImportError as e:
                self._log(f"  [SKIP] Palette randomizer not available: {e}")
            except Exception as e:
                self._log(f"  [ERROR] Palette randomizer failed: {e}")

        return count

    def _apply_eff_swaps(self, chr_map: dict, bdat) -> None:
        """Swap eneEff.bin entries to match CHR sprite swaps.

        eneEff.bin structure (after arm9_eff_merger):
            - 8-byte header
            - 173 enemy entries of 600 bytes each (indexed by enemy_param row)
            - 82 boss entries of 600 bytes each (indexed by boss_param row)

        When enemy at row X now shows sprite from row Y (via CHR swap),
        row X's effect entry must also contain row Y's effects.

        When a BOSS CHR is placed into an enemy slot, the boss's effect
        entry (from the merged boss region at index 173+) is copied into
        the enemy's eneEff slot.
        """
        import struct

        ENE_EFF_PATH = "btl/ene/eneEff.bin"
        HEADER_SIZE = 8
        ENTRY_SIZE = 600
        ENE_COUNT = 173  # entries 0-172 are enemy_param, 173+ are boss_param

        try:
            eff_data = self._rom.get_file(ENE_EFF_PATH)
        except (KeyError, Exception) as e:
            self._log(f"    WARNING: Could not read eneEff.bin: {e}")
            return

        num_entries = (len(eff_data) - HEADER_SIZE) // ENTRY_SIZE
        self._log(f"    --- eneEff.bin: {num_entries} entries, {len(eff_data)} bytes ---")

        # Build file -> [row_indices] mapping from enemy_param
        table = bdat.get_table("enemy_param")
        if table is None:
            return

        file_to_rows: dict[str, list[int]] = {}
        for idx, row in enumerate(table.rows):
            file_name = row.get("file", "")
            if file_name:
                if file_name not in file_to_rows:
                    file_to_rows[file_name] = []
                file_to_rows[file_name].append(idx)

        # Build boss file -> first boss_param row index mapping
        boss_table = bdat.get_table("boss_param")
        boss_file_to_row: dict[str, int] = {}
        if boss_table is not None:
            for idx, row in enumerate(boss_table.rows):
                file_name = row.get("file", "")
                if file_name and file_name not in boss_file_to_row:
                    boss_file_to_row[file_name] = idx

        # Build row-level swap plan
        # row_swap_plan: list of (dest_row, source_merged_index)
        row_swap_plan = []
        for dest_file, source_file in chr_map.items():
            if dest_file == source_file:
                continue
            dest_rows = file_to_rows.get(dest_file, [])
            if not dest_rows:
                continue

            # Check if source is a regular enemy or a boss
            source_rows = file_to_rows.get(source_file, [])
            if source_rows:
                # Enemy → Enemy: use enemy eneEff index directly
                for i, dest_row in enumerate(dest_rows):
                    source_row = source_rows[min(i, len(source_rows) - 1)]
                    if dest_row < num_entries and source_row < num_entries:
                        row_swap_plan.append((dest_row, source_row))
            elif source_file in boss_file_to_row:
                # Boss → Enemy: SKIP eneEff swap!
                # Boss effect entries use different combat system semantics.
                # The enemy keeps its original eneEff (matching its own attacks)
                # and just gets the boss's sprite (CHR swap only = skin only).
                self._log(f"      Boss→Enemy: {source_file} → SKIP eneEff "
                          f"(skin only, {len(dest_rows)} enemy slots)")

        if not row_swap_plan:
            self._log("    No eneEff entries to swap.")
            return

        # Snapshot all source entries BEFORE writing (handle chain swaps)
        eff_buf = bytearray(eff_data)
        original_entries: dict[int, bytes] = {}
        for _, source_row in row_swap_plan:
            if source_row not in original_entries:
                start = HEADER_SIZE + source_row * ENTRY_SIZE
                end = start + ENTRY_SIZE
                original_entries[source_row] = bytes(eff_data[start:end])

        # Write swapped entries
        swaps_done = 0
        for dest_row, source_row in row_swap_plan:
            dest_start = HEADER_SIZE + dest_row * ENTRY_SIZE
            source_entry = original_entries[source_row]
            eff_buf[dest_start:dest_start + ENTRY_SIZE] = source_entry
            swaps_done += 1

        try:
            self._rom.set_file(ENE_EFF_PATH, bytes(eff_buf))
            self._log(f"    eneEff.bin: {swaps_done} entries swapped")
        except Exception as e:
            self._log(f"    ERROR writing eneEff.bin: {e}")

    def _apply_chr_swaps(self, chr_map: dict) -> None:
        """Swap .chr sprite file contents in the ROM.

        Args:
            chr_map: Dict of {old_filename: new_filename} where each entry
                     means: the file old_filename should receive the CONTENTS
                     of new_filename.

        This reads all affected files first, then writes them to their
        new locations. This handles both mutual swaps and chain swaps.
        """
        CHR_PATH = "btl/ene/{}.chr"

        # Read all original file contents first
        original_contents: dict[str, bytes] = {}
        all_files = set(chr_map.keys()) | set(chr_map.values())

        for file_name in all_files:
            path = CHR_PATH.format(file_name)
            try:
                data = self._rom.get_file(path)
                original_contents[file_name] = data
                self._log(f"      Read {path} ({len(data)} bytes)")
            except KeyError:
                self._log(f"      WARNING: {path} not found in ROM, skipping")

        # Now write new contents
        swaps_done = 0
        for dest_name, source_name in chr_map.items():
            if dest_name == source_name:
                continue
            if source_name not in original_contents:
                self._log(f"      SKIP {dest_name} <- {source_name} (source missing)")
                continue

            dest_path = CHR_PATH.format(dest_name)
            new_data = original_contents[source_name]

            try:
                self._rom.set_file(dest_path, new_data)
                swaps_done += 1
                self._log(
                    f"      {dest_name}.chr <- {source_name}.chr "
                    f"({len(new_data)} bytes)"
                )
            except Exception as e:
                self._log(f"      ERROR writing {dest_path}: {e}")

        self._log(f"    CHR files swapped: {swaps_done}")

    def _apply_hero_chr(self, hero_map: dict, bdat) -> None:
        """Copy boss CHR sprites and battle effects into enemy slots.

        Args:
            hero_map: Dict of {enemy_file_basename: hero_key}
                      e.g., {"ene005_01": "hero_raditz"}
            bdat: The parsed BDAT file (for file->row mapping)

        Three things happen for each hero assignment:
        1. The boss's CHR file content is copied into the enemy's CHR slot
        2. The boss's bossEff animation entry is copied into eneEff.bin
           at the rows that reference the destination enemy file
        3. All OTHER boss effect entries in merged eneEff are also overwritten
           so story boss fights use the forced boss's effects
        """
        import struct
        from ..randomizers.encounter_shuffle import HERO_SPRITES

        CHR_PATH = "btl/ene/{}.chr"
        ENE_EFF_PATH = "btl/ene/eneEff.bin"
        BOSS_EFF_PATH = "btl/ene/bossEff.bin"
        HEADER_SIZE = 8
        ENTRY_SIZE = 600

        # Load effect files
        try:
            ene_eff = bytearray(self._rom.get_file(ENE_EFF_PATH))
            boss_eff = self._rom.get_file(BOSS_EFF_PATH)
        except Exception as e:
            self._log(f"      WARNING: Could not load effect files: {e}")
            ene_eff = None
            boss_eff = None

        # Read all source CHR files first (snapshot before writing)
        original_chr: dict[str, bytes] = {}
        for hero_key in set(hero_map.values()):
            hero_info = HERO_SPRITES.get(hero_key)
            if hero_info is None:
                continue
            src_path = CHR_PATH.format(hero_info["ene_file"])
            try:
                original_chr[hero_key] = self._rom.get_file(src_path)
            except KeyError:
                self._log(f"      WARNING: {src_path} not found")

        # Build file->rows mapping for eneEff patching (enemy_param only)
        table = bdat.get_table("enemy_param")
        file_to_rows: dict[str, list[int]] = {}
        if table:
            for idx, row in enumerate(table.rows):
                f = row.get("file", "")
                if f:
                    if f not in file_to_rows:
                        file_to_rows[f] = []
                    file_to_rows[f].append(idx)

        # Build boss file->rows mapping for bossEff patching
        boss_table = bdat.get_table("boss_param")
        boss_file_to_rows: dict[str, list[int]] = {}
        if boss_table:
            for idx, row in enumerate(boss_table.rows):
                f = row.get("file", "")
                if f:
                    if f not in boss_file_to_rows:
                        boss_file_to_rows[f] = []
                    boss_file_to_rows[f].append(idx)

        chr_injected = 0
        eff_injected = 0
        boss_eff_injected = 0

        # Determine the source boss's merged eneEff entry (used as template)
        # All hero assignments point to the same boss in force mode
        source_boss_entry = None
        source_boss_idx = None

        for dest_ene_file, hero_key in hero_map.items():
            hero_info = HERO_SPRITES.get(hero_key)
            if hero_info is None:
                self._log(f"      WARNING: Unknown hero key {hero_key}")
                continue

            # 1. Copy boss CHR into enemy slot
            if hero_key in original_chr:
                dest_path = CHR_PATH.format(dest_ene_file)
                chr_data = original_chr[hero_key]
                try:
                    self._rom.set_file(dest_path, chr_data)
                    chr_injected += 1
                except Exception as e:
                    self._log(f"      ERROR writing CHR: {e}")

            # 2. Get boss effect entry for boss slot patching (step 3).
            # We do NOT patch enemy_param eneEff slots here because regular
            # enemies keep their own attacks, which need their original eneEff.
            boss_idx = hero_info.get("boss_idx")
            if (ene_eff is not None and boss_idx is not None):
                ENE_COUNT = 173
                merged_idx = ENE_COUNT + boss_idx
                src_start = HEADER_SIZE + merged_idx * ENTRY_SIZE
                src_entry = ene_eff[src_start:src_start + ENTRY_SIZE]

                if len(src_entry) == ENTRY_SIZE:
                    if source_boss_entry is None:
                        source_boss_entry = bytes(src_entry)
                        source_boss_idx = boss_idx

        # NOTE: We do NOT overwrite bossEff entries in the merged eneEff.
        # Boss scripts are tightly coupled to their own bossEff animations.
        # Swapping them causes crashes and visual glitches (wrong positions,
        # buff/debuff instead of attacks). Bosses get cosmetic-only swaps.

        self._log(f"    Hero sprites injected: {chr_injected}")

    def _save_spoiler_log(self, rom_path: str) -> None:
        """Save the full randomization log as a spoiler file."""
        log_path = rom_path.replace(".nds", "_spoiler.txt")
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(self.log))
            self._log(f"  Spoiler log: {log_path}")
        except Exception as e:
            self._log(f"  Warning: Could not save spoiler log: {e}")

        # Also save config
        config_path = rom_path.replace(".nds", "_config.json")
        try:
            self.config.save_json(config_path)
        except Exception:
            pass

    def _log(self, msg: str) -> None:
        """Add a message to the build log and print it."""
        self.log.append(msg)
        try:
            print(msg)
        except UnicodeEncodeError:
            print(msg.encode('ascii', errors='replace').decode('ascii'))
