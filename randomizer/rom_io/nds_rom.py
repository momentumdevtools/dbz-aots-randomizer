#!/usr/bin/env python3
"""
nds_rom.py — Nintendo DS ROM I/O Wrapper (via ndspy)
=====================================================
Provides safe ROM loading, file extraction, modification, and repacking.
ndspy automatically handles FAT/FNT recalculation and sector alignment.

Usage:
    rom = NdsRom.from_file("path/to/original.nds")
    bdat_bytes = rom.get_file("data/btl/bdat/US/bdat.bin")
    rom.set_file("data/btl/bdat/US/bdat.bin", modified_bytes)
    rom.save("path/to/randomized.nds")
"""

import os
from typing import Optional, List, Dict

import ndspy.rom
import ndspy.code


class NdsRom:
    """
    High-level wrapper around ndspy.rom.NintendoDSRom.

    Handles:
    - ROM loading and saving
    - File extraction by NitroFS path
    - File replacement with automatic FAT recalculation
    - ARM9/ARM7 binary access
    - ROM metadata (title, game code)
    """

    def __init__(self, rom: ndspy.rom.NintendoDSRom, source_path: str = ""):
        self._rom = rom
        self._source_path = source_path
        self._modified_files: Dict[str, bool] = {}

    @classmethod
    def from_file(cls, filepath: str) -> 'NdsRom':
        """Load an NDS ROM from a file."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"ROM not found: {filepath}")

        rom = ndspy.rom.NintendoDSRom.fromFile(filepath)
        return cls(rom, source_path=filepath)

    @classmethod
    def from_bytes(cls, data: bytes) -> 'NdsRom':
        """Load an NDS ROM from raw bytes."""
        rom = ndspy.rom.NintendoDSRom(data)
        return cls(rom)

    # ── File Access ──────────────────────────────────────────

    def get_file(self, path: str) -> bytes:
        """
        Get a file's contents by its NitroFS path.

        Args:
            path: File path within the ROM (e.g., "btl/bdat/US/bdat.bin")
                  Note: paths are relative to the ROM's data directory.

        Returns:
            Raw bytes of the file.

        Raises:
            KeyError: If the file doesn't exist in the ROM.
        """
        try:
            return self._rom.getFileByName(path)
        except Exception as e:
            raise KeyError(f"File not found in ROM: {path}") from e

    def set_file(self, path: str, data: bytes) -> None:
        """
        Replace a file's contents in the ROM.

        ndspy automatically handles FAT/FNT recalculation when saving.

        Args:
            path: NitroFS path
            data: New file contents (can be different size than original)
        """
        self._rom.setFileByName(path, data)
        self._modified_files[path] = True

    def file_exists(self, path: str) -> bool:
        """Check if a file exists in the ROM's NitroFS."""
        try:
            self._rom.getFileByName(path)
            return True
        except Exception:
            return False

    def list_files(self, directory: str = "") -> List[str]:
        """
        List all files in the ROM, optionally filtered by directory prefix.

        Args:
            directory: Optional path prefix filter (e.g., "btl/bdat/")

        Returns:
            List of file paths.
        """
        all_files = []
        self._collect_files(self._rom.filenames, "", all_files)

        if directory:
            return [f for f in all_files if f.startswith(directory)]
        return all_files

    def _collect_files(self, folder, prefix: str, result: list):
        """Recursively collect file paths from NitroFS."""
        for fname in folder.files:
            result.append(prefix + fname)

        # Handle subfolders
        for subfolder_name, subfolder in folder.folders:
            self._collect_files(subfolder, prefix + subfolder_name + "/", result)

    # ── ARM9/ARM7 Binary Access ──────────────────────────────

    @property
    def arm9(self) -> bytes:
        """Get the ARM9 binary."""
        return self._rom.arm9

    @arm9.setter
    def arm9(self, data: bytes) -> None:
        """Replace the ARM9 binary."""
        self._rom.arm9 = data
        self._modified_files['__arm9__'] = True

    @property
    def arm7(self) -> bytes:
        """Get the ARM7 binary."""
        return self._rom.arm7

    @property
    def arm9_overlays(self) -> list:
        """Get ARM9 overlay table."""
        return self._rom.arm9OverlayTable

    # ── ROM Metadata ─────────────────────────────────────────

    @property
    def title(self) -> str:
        """Game title from the ROM header."""
        return self._rom.name.decode('ascii', errors='replace').strip('\x00')

    @property
    def game_code(self) -> str:
        """4-character game code (e.g., 'YVSE' for DBZ AotS US)."""
        return self._rom.idCode.decode('ascii', errors='replace')

    @property
    def source_path(self) -> str:
        """Path the ROM was loaded from."""
        return self._source_path

    @property
    def modified_files(self) -> List[str]:
        """List of files that have been modified."""
        return list(self._modified_files.keys())

    # ── Save ─────────────────────────────────────────────────

    def save(self, filepath: str) -> int:
        """
        Save the ROM to a file.

        ndspy automatically handles:
        - FAT (File Allocation Table) recalculation
        - FNT (File Name Table) updates
        - Sector alignment and padding
        - Header checksum updates

        Args:
            filepath: Output path for the patched ROM.

        Returns:
            Size of the saved ROM in bytes.
        """
        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
        data = self._rom.save()
        with open(filepath, 'wb') as f:
            f.write(data)
        return len(data)

    def save_bytes(self) -> bytes:
        """Return the ROM as raw bytes without saving to disk."""
        return self._rom.save()

    # ── Convenience ──────────────────────────────────────────

    def get_bdat(self, locale: str = "US") -> bytes:
        """Shortcut: get the BDAT file for a specific locale."""
        return self.get_file(f"btl/bdat/{locale}/bdat.bin")

    def set_bdat(self, data: bytes, locale: str = "US") -> None:
        """Shortcut: set the BDAT file for a specific locale."""
        self.set_file(f"btl/bdat/{locale}/bdat.bin", data)

    def __repr__(self) -> str:
        return (
            f"NdsRom(title='{self.title}', code='{self.game_code}', "
            f"source='{self._source_path}', "
            f"modified={len(self._modified_files)} files)"
        )
