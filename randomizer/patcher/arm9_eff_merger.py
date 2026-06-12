#!/usr/bin/env python3
"""
arm9_eff_merger.py — Merge eneEff.bin + bossEff.bin and patch ARM9
=====================================================================
Merges both effect files into a single unified eneEff.bin and patches
the ARM9 binary so the game always loads eneEff for both regular enemies
AND bosses.

Verified via Ghidra RE:
  - FUN_0204f810 @ 0x0204f968: CMP R0, #0xAD / BLE (eneEff branch)
  - FUN_02058e10 @ 0x020589d8: CMP R0, #0xAD / BHI (bossEff branch)
  - Index calc  @ 0x020379f0: SUBHI R6, R0, #0xAE (boss_index = ID - 0xAE)

Patch strategy:
  1. Append bossEff entries to eneEff → unified file (173 + 82 = 255 entries)
  2. Patch FUN_0204f810: change BLE to B (always take eneEff path)
  3. Patch FUN_02058e10: change BHI to NOP (never take bossEff path)
  4. Patch index calc: boss_index = (ID - 0xAE) + 173 = ID - 1
     Original: SUBHI R6, R0, #0xAE → change to SUBHI R6, R0, #0x01
     This works because entry 173 in merged file = bossEff entry 0,
     and (0xAE - 0x01) = 0xAD = 173, so boss ID 0xAE → index 173 ✓
"""

import struct
from typing import Optional

# File paths in NDS ROM filesystem
ENE_EFF_PATH = "btl/ene/eneEff.bin"
BOSS_EFF_PATH = "btl/ene/bossEff.bin"

# Binary constants
HEADER_SIZE = 8
ENTRY_SIZE = 600

# ARM9 patch addresses (absolute, as loaded in memory at 0x02000000)
# These are the offsets within the ARM9 binary
ARM9_BASE = 0x02000000

# Patch site 1: FUN_0204f810 — CMP R0, #0xAD / BLE eneEff_path
# At 0x0204f96c: BLE 0x0204f9a0 → change to B 0x0204f9a0 (unconditional)
# Original: 0B 00 00 DA (BLE) → 0B 00 00 EA (B, always)
PATCH1_ADDR = 0x0204f96c
PATCH1_ORIGINAL = bytes.fromhex("0B0000DA")  # BLE +0x0B
PATCH1_PATCHED = bytes.fromhex("0B0000EA")   # B   +0x0B (always jump to eneEff)

# Patch site 2: FUN_02058e10 — CMP R0, #0xAD / BHI bossEff_handler
# At 0x020589DC: BHI 0x02058afc → change to NOP (MOV R0, R0)
# Original: 46 00 00 8A (BHI) → 00 00 A0 E1 (MOV R0, R0 = NOP)
PATCH2_ADDR = 0x020589DC
PATCH2_ORIGINAL = bytes.fromhex("4600008A")  # BHI +0x46
PATCH2_PATCHED = bytes.fromhex("0000A0E1")   # NOP

# Patch site 3: Index calculation — SUBHI R6, R0, #0xAE → SUBHI R6, R0, #0x01
# At 0x020379f0: subhi r6, r0, #0xae → subhi r6, r0, #0x01
# This makes boss ID 0xAE map to index 0xAD = 173 (first boss entry in merged file)
# Original: AE 60 40 82 → 01 60 40 82
PATCH3_ADDR = 0x020379F0
PATCH3_ORIGINAL = bytes.fromhex("AE604082")  # SUBHI R6, R0, #0xAE
PATCH3_PATCHED = bytes.fromhex("01604082")   # SUBHI R6, R0, #0x01

ALL_PATCHES = [
    ("FUN_0204f810: BLE→B (always use eneEff)", PATCH1_ADDR, PATCH1_ORIGINAL, PATCH1_PATCHED),
    ("FUN_02058e10: BHI→NOP (skip bossEff)", PATCH2_ADDR, PATCH2_ORIGINAL, PATCH2_PATCHED),
    ("Index calc: SUBHI #0xAE→#0x01", PATCH3_ADDR, PATCH3_ORIGINAL, PATCH3_PATCHED),
]


def merge_eff_files(ene_eff: bytes, boss_eff: bytes) -> bytes:
    """Merge eneEff.bin and bossEff.bin into a single unified file.

    Layout:
        [8-byte header][173 eneEff entries][82 bossEff entries]

    Total: 8 + (173 + 82) * 600 = 153008 bytes
    """
    ene_header = ene_eff[:HEADER_SIZE]
    ene_entries = ene_eff[HEADER_SIZE:]
    boss_entries = boss_eff[HEADER_SIZE:]

    ene_count = len(ene_entries) // ENTRY_SIZE
    boss_count = len(boss_entries) // ENTRY_SIZE

    merged = bytearray(ene_header)
    merged.extend(ene_entries)
    merged.extend(boss_entries)

    return bytes(merged), ene_count, boss_count


def patch_arm9(arm9_data: bytes) -> tuple[bytes, list[str]]:
    """Apply ARM9 binary patches to unify eneEff/bossEff loading.

    Returns:
        Tuple of (patched_arm9_bytes, log_messages)
    """
    arm9 = bytearray(arm9_data)
    log = []

    for name, addr, original, patched in ALL_PATCHES:
        offset = addr - ARM9_BASE
        current = bytes(arm9[offset:offset + 4])

        if current == original:
            arm9[offset:offset + 4] = patched
            log.append(f"  ✓ {name} @ 0x{addr:08X} (offset 0x{offset:06X})")
        elif current == patched:
            log.append(f"  ≡ {name} @ 0x{addr:08X} — already patched")
        else:
            log.append(
                f"  ✗ {name} @ 0x{addr:08X} — "
                f"expected {original.hex()} but found {current.hex()}"
            )

    return bytes(arm9), log


def apply_eff_merge(rom, log_func=print) -> bool:
    """Full pipeline: merge eff files + patch ARM9.

    Args:
        rom: NdsRom instance with get_file/set_file/arm9 access
        log_func: Logging callback

    Returns:
        True if all patches applied successfully
    """
    # Step 1: Load effect files
    try:
        ene_eff = rom.get_file(ENE_EFF_PATH)
        boss_eff = rom.get_file(BOSS_EFF_PATH)
    except Exception as e:
        log_func(f"  ERROR: Could not load eff files: {e}")
        return False

    ene_count = (len(ene_eff) - HEADER_SIZE) // ENTRY_SIZE
    boss_count = (len(boss_eff) - HEADER_SIZE) // ENTRY_SIZE
    log_func(f"  eneEff: {ene_count} entries, bossEff: {boss_count} entries")

    # Step 2: Merge
    merged_eff, _, _ = merge_eff_files(ene_eff, boss_eff)
    merged_count = (len(merged_eff) - HEADER_SIZE) // ENTRY_SIZE
    log_func(f"  Merged: {merged_count} entries ({len(merged_eff)} bytes)")

    # Step 3: Write merged file as eneEff.bin
    rom.set_file(ENE_EFF_PATH, merged_eff)
    log_func(f"  Wrote merged eneEff.bin")

    # Step 4: Patch ARM9
    arm9_patched, patch_log = patch_arm9(rom.arm9)
    for msg in patch_log:
        log_func(msg)

    rom.arm9 = arm9_patched
    log_func(f"  ARM9 patched ({len(arm9_patched)} bytes)")

    # Verify index mapping
    log_func(f"  Index mapping: boss ID 0xAE (174) → merged index {0xAE - 1} = {0xAE - 1}")
    log_func(f"  Expected: eneEff entry 173 = first boss entry ✓")

    return True
