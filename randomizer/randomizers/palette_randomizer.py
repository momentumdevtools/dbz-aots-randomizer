#!/usr/bin/env python3
"""
palette_randomizer.py — Enemy Palette Randomizer
==================================================
Randomizes the embedded palettes inside enemy dCHR sprite files
(btl/ene/*.chr) to produce recolored enemies.

NDS palette format:
  16-bit values, ``0bBBBBBGGGGGRRRRR`` (5 bits per channel, bit 15 unused).
  Color 0 in each 16-color or 256-color palette is transparent and must
  NOT be modified.

dCHR file layout:
  Bytes 0–3:   Magic ``dCHR`` (0x64434852 little-endian)
  Bytes 4–7:   Metadata / header
  Bytes 8+:    Pixel data and palette data

The palette offset is located by scanning for a block of valid RGB555
values (bit 15 == 0) following the pixel data.

Modes:
  'vanilla' — No changes
  'shift'   — Apply one random hue rotation per enemy (consistent look)
  'random'  — Randomize each palette color independently (wild colors)
  'chaos'   — Swap entire palettes between different enemies
"""

import colorsys
import struct

from randomizer.randomizers.base import BaseRandomizer
from randomizer.utils.rng import GameRNG


# ── dCHR constants ───────────────────────────────────────────

DCHR_MAGIC = b"dCHR"          # 0x64 0x43 0x48 0x52
DCHR_HEADER_SIZE = 8          # Minimum header before data
PALETTE_16_BYTES = 32         # 16 colors × 2 bytes
PALETTE_256_BYTES = 512       # 256 colors × 2 bytes

# Where to look for enemy sprites in the ROM filesystem
ENEMY_CHR_DIR = "btl/ene/"


class PaletteRandomizer(BaseRandomizer):
    """
    Randomizes palettes inside enemy dCHR sprite files.

    This randomizer does NOT use BDAT tables — it operates directly on
    the NDS ROM filesystem.  The ``randomize()`` stub exists only to
    satisfy the ABC contract; the real entry point is
    ``randomize_palettes(rom)``.

    Config keys:
        mode:  'vanilla' | 'shift' | 'random' | 'chaos'
    """

    def __init__(self, rng: GameRNG, config: dict):
        super().__init__(rng, config)
        self.mode: str = config.get("mode", "vanilla")

    # ── ABC compliance ───────────────────────────────────────

    def randomize(self, bdat, writer) -> None:
        """
        Not used — this randomizer works on the ROM filesystem, not BDAT.
        Call ``randomize_palettes(rom)`` instead.
        """
        pass

    # ── Main entry point ─────────────────────────────────────

    def randomize_palettes(self, rom) -> None:
        """
        Apply palette randomization to all enemy dCHR files.

        Args:
            rom: NdsRom wrapper (randomizer.rom_io.nds_rom.NdsRom)
        """
        if self.mode == "vanilla":
            self._log("PaletteRandomizer: mode=vanilla — skipping")
            return

        self._log(f"=== PaletteRandomizer: mode={self.mode} ===")

        # Collect all .chr files under btl/ene/
        chr_files = self._find_chr_files(rom)
        if not chr_files:
            self._log("WARNING: No .chr files found in btl/ene/")
            return

        self._log(f"Found {len(chr_files)} enemy CHR files")

        if self.mode in ("shift", "random"):
            self._process_individual(rom, chr_files)
        elif self.mode == "chaos":
            self._process_chaos_swap(rom, chr_files)
        else:
            self._log(f"WARNING: Unknown mode '{self.mode}', skipping")
            return

        self._log("=== PaletteRandomizer complete ===")

    # ── Mode handlers ────────────────────────────────────────

    def _process_individual(self, rom, chr_files: list[str]) -> None:
        """Apply per-file palette modification (shift or random mode)."""
        for fpath in chr_files:
            data = bytearray(rom.get_file(fpath))

            if not self._is_dchr(data):
                self._log(f"  SKIP {fpath}: not a valid dCHR file")
                continue

            pal_offset, pal_count = self._find_palette(data)
            if pal_offset < 0:
                self._log(f"  SKIP {fpath}: palette not found")
                continue

            palette = self._read_palette(data, pal_offset, pal_count)
            fname = fpath.rsplit("/", 1)[-1]

            if self.mode == "shift":
                hue_degrees = self.rng.randint(30, 330)
                new_palette = self._hue_shift_palette(palette, hue_degrees)
                self._log(f"  {fname}: hue shift +{hue_degrees}° "
                          f"({pal_count} colors)")
            else:  # random
                new_palette = self._randomize_palette(palette)
                self._log(f"  {fname}: randomized {pal_count} colors")

            self._write_palette(data, pal_offset, new_palette)
            rom.set_file(fpath, bytes(data))

    def _process_chaos_swap(self, rom, chr_files: list[str]) -> None:
        """Swap entire palettes between different enemies."""
        # First pass: extract all palettes
        entries: list[dict] = []
        for fpath in chr_files:
            data = bytearray(rom.get_file(fpath))
            if not self._is_dchr(data):
                continue

            pal_offset, pal_count = self._find_palette(data)
            if pal_offset < 0:
                continue

            palette = self._read_palette(data, pal_offset, pal_count)
            entries.append({
                "path": fpath,
                "data": data,
                "pal_offset": pal_offset,
                "pal_count": pal_count,
                "palette": palette,
            })

        if len(entries) < 2:
            self._log("  Fewer than 2 valid CHR files — nothing to swap")
            return

        # Build a shuffled index mapping
        order = list(range(len(entries)))
        self.rng.shuffle(order)

        # Write each enemy's palette from the shuffled source
        for dest_pos, src_pos in enumerate(order):
            dest = entries[dest_pos]
            src = entries[src_pos]

            # If palette sizes differ, take as many colors as the destination
            # can hold and fill the rest with the original
            src_palette = src["palette"]
            dest_count = dest["pal_count"]
            if len(src_palette) >= dest_count:
                new_palette = src_palette[:dest_count]
            else:
                new_palette = src_palette + dest["palette"][len(src_palette):]

            # Always preserve color 0 (transparent) from the original
            new_palette[0] = dest["palette"][0]

            self._write_palette(dest["data"], dest["pal_offset"], new_palette)
            rom.set_file(dest["path"], bytes(dest["data"]))

            if dest_pos != src_pos:
                dest_name = dest["path"].rsplit("/", 1)[-1]
                src_name = src["path"].rsplit("/", 1)[-1]
                self._log(f"  {dest_name} ← palette from {src_name}")

        self._log(f"  Swapped palettes across {len(entries)} enemies")

    # ── dCHR parsing ─────────────────────────────────────────

    def _find_chr_files(self, rom) -> list[str]:
        """Return all .chr files under the enemy directory."""
        all_files = rom.list_files(ENEMY_CHR_DIR)
        return [f for f in all_files if f.lower().endswith(".chr")]

    @staticmethod
    def _is_dchr(data: bytes) -> bool:
        """Check if data starts with the dCHR magic."""
        return len(data) >= DCHR_HEADER_SIZE and data[:4] == DCHR_MAGIC

    def _find_palette(self, data: bytes) -> tuple[int, int]:
        """
        Locate the palette within a dCHR file.

        Strategy: scan backwards from the end of the file for a
        contiguous block of 16-bit values where bit 15 is always 0
        (valid RGB555).  The longest such block that is exactly
        16 or 256 colors is the palette.

        Returns:
            (offset, color_count) or (-1, 0) if not found.
        """
        file_len = len(data)

        # Try 256-color palette first (more common for enemy sprites),
        # then fall back to 16-color
        for expected_count, expected_bytes in [
            (256, PALETTE_256_BYTES),
            (16, PALETTE_16_BYTES),
        ]:
            # Scan from the end of the file backwards
            # The palette is often at the very end, or near it
            for candidate_start in range(
                file_len - expected_bytes,
                max(DCHR_HEADER_SIZE - 1, file_len - expected_bytes * 4),
                -2,  # step by 2 (16-bit aligned)
            ):
                if candidate_start < DCHR_HEADER_SIZE:
                    break

                if self._validate_palette_block(
                    data, candidate_start, expected_count
                ):
                    return candidate_start, expected_count

        return -1, 0

    @staticmethod
    def _validate_palette_block(
        data: bytes, offset: int, color_count: int
    ) -> bool:
        """
        Check that a block of 16-bit values looks like a valid NDS palette.

        Criteria:
          - All values have bit 15 == 0  (valid RGB555)
          - At least 3 distinct non-zero colors (not blank/garbage)
          - Fits within the file
        """
        byte_len = color_count * 2
        if offset + byte_len > len(data):
            return False

        distinct_nonzero = set()
        for i in range(color_count):
            val = struct.unpack_from("<H", data, offset + i * 2)[0]
            if val & 0x8000:  # bit 15 set → not RGB555
                return False
            if val != 0:
                distinct_nonzero.add(val)

        return len(distinct_nonzero) >= 3

    # ── Palette I/O ──────────────────────────────────────────

    @staticmethod
    def _read_palette(
        data: bytes, offset: int, color_count: int
    ) -> list[int]:
        """Read *color_count* 16-bit RGB555 values starting at *offset*."""
        return [
            struct.unpack_from("<H", data, offset + i * 2)[0]
            for i in range(color_count)
        ]

    @staticmethod
    def _write_palette(
        data: bytearray, offset: int, palette: list[int]
    ) -> None:
        """Write 16-bit RGB555 values back into *data* at *offset*."""
        for i, color in enumerate(palette):
            struct.pack_into("<H", data, offset + i * 2, color & 0x7FFF)

    # ── Color math (RGB555 ↔ HSV) ────────────────────────────

    @staticmethod
    def _rgb555_to_rgb(color: int) -> tuple[int, int, int]:
        """Convert a 16-bit RGB555 value to (R8, G8, B8)."""
        r5 = color & 0x1F
        g5 = (color >> 5) & 0x1F
        b5 = (color >> 10) & 0x1F
        # Expand 5-bit to 8-bit: (val << 3) | (val >> 2)
        r8 = (r5 << 3) | (r5 >> 2)
        g8 = (g5 << 3) | (g5 >> 2)
        b8 = (b5 << 3) | (b5 >> 2)
        return r8, g8, b8

    @staticmethod
    def _rgb_to_rgb555(r8: int, g8: int, b8: int) -> int:
        """Convert (R8, G8, B8) to a 16-bit RGB555 value."""
        r5 = (r8 >> 3) & 0x1F
        g5 = (g8 >> 3) & 0x1F
        b5 = (b8 >> 3) & 0x1F
        return r5 | (g5 << 5) | (b5 << 10)

    @classmethod
    def _rgb555_to_hsv(cls, color: int) -> tuple[float, float, float]:
        """Convert RGB555 to HSV (h in [0,1], s in [0,1], v in [0,1])."""
        r8, g8, b8 = cls._rgb555_to_rgb(color)
        return colorsys.rgb_to_hsv(r8 / 255.0, g8 / 255.0, b8 / 255.0)

    @classmethod
    def _hsv_to_rgb555(cls, h: float, s: float, v: float) -> int:
        """Convert HSV back to RGB555."""
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        r8 = max(0, min(255, int(r * 255.0)))
        g8 = max(0, min(255, int(g * 255.0)))
        b8 = max(0, min(255, int(b * 255.0)))
        return cls._rgb_to_rgb555(r8, g8, b8)

    # ── Palette transforms ───────────────────────────────────

    def _hue_shift_palette(
        self, palette: list[int], degrees: int
    ) -> list[int]:
        """
        Rotate the hue of every color in the palette by *degrees*.
        Color 0 (transparent) is preserved.
        """
        shift = degrees / 360.0
        result = list(palette)

        for i in range(1, len(result)):  # skip index 0
            color = result[i]
            if color == 0:
                continue

            h, s, v = self._rgb555_to_hsv(color)
            h = (h + shift) % 1.0
            result[i] = self._hsv_to_rgb555(h, s, v)

        return result

    def _randomize_palette(self, palette: list[int]) -> list[int]:
        """
        Independently randomize each color's hue and slightly vary
        saturation / value.  Color 0 (transparent) is preserved.
        """
        result = list(palette)

        for i in range(1, len(result)):  # skip index 0
            color = result[i]
            if color == 0:
                continue

            _h, s, v = self._rgb555_to_hsv(color)
            # Random hue
            new_h = self.rng.randint(0, 359) / 360.0
            # Slightly vary saturation (±20%)
            s_shift = (self.rng.randint(0, 40) - 20) / 100.0
            new_s = max(0.0, min(1.0, s + s_shift))
            # Slightly vary value (±10%)
            v_shift = (self.rng.randint(0, 20) - 10) / 100.0
            new_v = max(0.05, min(1.0, v + v_shift))

            result[i] = self._hsv_to_rgb555(new_h, new_s, new_v)

        return result
