#!/usr/bin/env python3
"""
bdat_writer.py — In-Place BDAT Binary Patcher
===============================================
Writes modified row data back into BDAT binary format.

CRITICAL DESIGN DECISION: In-Place Patching Only
-------------------------------------------------
We NEVER rebuild the BDAT file from scratch. Instead:
  1. Start from the original raw bytes (BdatFile.raw_data)
  2. Overwrite ONLY the data row bytes at their exact offsets
  3. Headers, hash tables, string pools remain UNTOUCHED

This guarantees:
  - Output is EXACTLY the same size as input (no FAT cascade)
  - No risk of corrupting hash chains or string pool offsets
  - Only numeric values (u8/u16/u32/s8/s16) are modified
  - String references (type 7) are NEVER modified

Safety Properties:
  - len(output) == len(input)  ALWAYS
  - Header bytes are identical
  - String pool bytes are identical
  - Only bytes within [data_offset, data_offset + num_rows * row_size] change
"""

import struct
from typing import Dict, Any, Optional

from .bdat_reader import BdatFile, BdatTable, BdatColumn, TYPE_TABLE


class BdatWriter:
    """
    In-place patcher for BDAT binary data.

    Usage:
        bdat = read_bdat(raw_bytes)
        writer = BdatWriter(bdat)

        # Modify individual cells
        writer.set_value("enemy_param", 5, "hp", 9999)
        writer.set_value("enemy_param", 5, "str", 500)

        # Or batch-modify entire rows
        writer.patch_row("enemy_param", 5, {"hp": 9999, "str": 500, "def": 300})

        # Get the patched bytes
        patched = writer.build()
        assert len(patched) == len(raw_bytes)
    """

    def __init__(self, bdat: BdatFile):
        self._bdat = bdat
        self._data = bdat.raw_data  # already a mutable bytearray
        self._patch_count = 0

    def set_value(self, table_name: str, row_idx: int,
                  col_name: str, value: int) -> bool:
        """
        Set a single numeric value in a BDAT table row.

        Args:
            table_name: Name of the BDAT sub-table (e.g., "enemy_param")
            row_idx:    Row index (0-based)
            col_name:   Column name (e.g., "hp", "str", "def")
            value:      New integer value (will be clamped to type range)

        Returns:
            True if the value was written, False if table/row/column not found.

        Raises:
            ValueError: If trying to write a string column (type 7)
        """
        table = self._bdat.get_table(table_name)
        if table is None:
            return False

        col = table.get_column(col_name)
        if col is None:
            return False

        if col.is_string:
            raise ValueError(
                f"Cannot write string column '{col_name}' — "
                f"string pool modification would corrupt offsets. "
                f"Only numeric types (u8/u16/u32/s8/s16) are supported."
            )

        if not (0 <= row_idx < table.num_rows):
            return False

        return self._write_cell(table, row_idx, col, value)

    def patch_row(self, table_name: str, row_idx: int,
                  values: Dict[str, int]) -> int:
        """
        Patch multiple columns in a single row.

        Args:
            table_name: Table name
            row_idx:    Row index
            values:     Dict of {column_name: new_value}

        Returns:
            Number of columns successfully patched.
        """
        count = 0
        for col_name, value in values.items():
            if self.set_value(table_name, row_idx, col_name, value):
                count += 1
        return count

    def patch_table(self, table_name: str,
                    modifications: Dict[int, Dict[str, int]]) -> int:
        """
        Batch-patch multiple rows in a table.

        Args:
            table_name:    Table name
            modifications: Dict of {row_idx: {col_name: value, ...}, ...}

        Returns:
            Total number of cells patched.
        """
        total = 0
        for row_idx, values in modifications.items():
            total += self.patch_row(table_name, row_idx, values)
        return total

    def _write_cell(self, table: BdatTable, row_idx: int,
                    col: BdatColumn, value: int) -> bool:
        """Write a single cell value into the raw byte array."""
        type_info = TYPE_TABLE.get(col.type_id)
        if type_info is None or type_info.is_string:
            return False

        # Clamp value to type range
        value = self._clamp_value(value, col.type_id)

        # Calculate absolute byte offset in the file
        abs_offset = (
            table.file_offset +
            table.data_offset +
            row_idx * table.row_size +
            col.row_offset
        )

        # Bounds check
        if abs_offset + type_info.size > len(self._data):
            return False

        # Write the value
        struct.pack_into(type_info.fmt, self._data, abs_offset, value)

        # Also update the in-memory row data for consistency
        if row_idx < len(table.rows) and col.name in table.rows[row_idx]:
            table.rows[row_idx][col.name] = value

        self._patch_count += 1
        return True

    @staticmethod
    def _clamp_value(value: int, type_id: int) -> int:
        """Clamp a value to the valid range for its BDAT type."""
        ranges = {
            0: (0, 255),         # nop (u8)
            1: (0, 255),         # u8
            2: (0, 65535),       # u16
            3: (0, 4294967295),  # u32
            4: (-128, 127),      # s8
            5: (-32768, 32767),  # s16
            6: (0, 4294967295),  # u32 alias
        }
        lo, hi = ranges.get(type_id, (0, 255))
        return max(lo, min(hi, value))

    def build(self) -> bytes:
        """
        Return the patched BDAT bytes.

        GUARANTEE: len(output) == len(original)
        """
        return bytes(self._data)

    @property
    def patch_count(self) -> int:
        """Total number of cells patched so far."""
        return self._patch_count

    def get_diff_summary(self) -> str:
        """Return a human-readable summary of what was patched."""
        return f"BdatWriter: {self._patch_count} cells patched across BDAT data"

    def verify_size(self, original_size: int) -> bool:
        """Verify the output is exactly the same size as the input."""
        return len(self._data) == original_size
