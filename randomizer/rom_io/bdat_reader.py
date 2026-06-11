#!/usr/bin/env python3
"""
bdat_reader.py — Monolith Soft BDAT Binary Format Reader
==========================================================
Refactored from scripts/parse_bdat.py (Ghidra-verified v2.0).

BDAT is Monolith Soft's proprietary multi-table binary container format.
Verified against ARM9 decompilation of the runtime accessor chain:
    FUN_0202a788 (getValue) → FUN_0202a894 (column lookup via hash)
    → FUN_0202a948 (row+offset calc) → FUN_0202a9a4 (type-specific read)

File Layout:
    u32  table_count
    u32  file_size
    u32[table_count]  offset_table (absolute from file start)

Per-Table Layout:
    +0x00: "BDAT" magic (4 bytes)
    +0x04: u16  flags
    +0x06: u16  name_offset     (from table_base → table name string)
    +0x08: u16  row_size        (bytes per data row)
    +0x0A: u16  data_offset     (from table_base → first data row)
    +0x0C: u16  num_rows
    +0x0E: u16  hash_offset     (from table_base → hash bucket table)
    +0x10: u16  hash_buckets    (number of hash buckets)
"""

import struct
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple


# ──────────────────────────────────────────────────────────────
# Type system — verified from ARM9 switch at 0x0202a9a4
# ──────────────────────────────────────────────────────────────

@dataclass
class BdatTypeInfo:
    """Describes a BDAT column data type."""
    name: str
    size: int       # bytes
    fmt: str        # struct format char
    is_string: bool = False


# Type ID → info mapping (from ARM9 disassembly)
TYPE_TABLE: Dict[int, BdatTypeInfo] = {
    0: BdatTypeInfo('nop',  1, 'B'),        # invalid / placeholder
    1: BdatTypeInfo('u8',   1, 'B'),        # unsigned byte
    2: BdatTypeInfo('u16',  2, '<H'),       # unsigned 16-bit
    3: BdatTypeInfo('u32',  4, '<I'),       # unsigned 32-bit
    4: BdatTypeInfo('s8',   1, 'b'),        # signed byte
    5: BdatTypeInfo('s16',  2, '<h'),       # signed 16-bit
    6: BdatTypeInfo('u32',  4, '<I'),       # unsigned 32-bit (alias for 3)
    7: BdatTypeInfo('str',  2, '<H', True), # string offset (table_base + u16)
}


# ──────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────

@dataclass
class BdatColumn:
    """A single column definition within a BDAT table."""
    name: str
    type_id: int
    type_name: str
    size: int           # byte size of this field
    row_offset: int     # byte offset within a data row
    is_string: bool = False
    col_type_idx: int = 0  # index into the column type table at table_base


@dataclass
class BdatTable:
    """
    A parsed BDAT sub-table with its schema and row data.

    Attributes:
        index:        Table index within the BDAT file
        name:         Table name (from string pool)
        file_offset:  Absolute byte offset in the BDAT file
        flags:        Table flags
        row_size:     Bytes per data row
        data_offset:  Offset from table_base to first data row
        num_rows:     Number of data rows
        hash_offset:  Offset from table_base to hash bucket table
        hash_buckets: Number of hash buckets
        columns:      Ordered list of column definitions
        rows:         List of dicts — each dict maps column_name → value
    """
    index: int
    name: str
    file_offset: int
    flags: int
    row_size: int
    data_offset: int
    num_rows: int
    hash_offset: int
    hash_buckets: int
    columns: List[BdatColumn] = field(default_factory=list)
    rows: List[Dict[str, Any]] = field(default_factory=list)

    def get_column(self, name: str) -> Optional[BdatColumn]:
        """Find a column by name."""
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def get_row(self, idx: int) -> Optional[Dict[str, Any]]:
        """Get a row by index."""
        if 0 <= idx < len(self.rows):
            return self.rows[idx]
        return None


@dataclass
class BdatFile:
    """
    A complete BDAT file with all sub-tables.

    This is the primary interface for reading BDAT data.
    Preserves the raw bytes for in-place patching by BdatWriter.
    """
    table_count: int
    file_size: int
    table_offsets: List[int]
    tables: List[BdatTable]
    raw_data: bytearray  # mutable copy for patching

    def get_table(self, name: str) -> Optional[BdatTable]:
        """Find a table by name (case-sensitive)."""
        for table in self.tables:
            if table.name == name:
                return table
        return None

    def get_table_by_index(self, idx: int) -> Optional[BdatTable]:
        """Find a table by its index."""
        for table in self.tables:
            if table.index == idx:
                return table
        return None

    def list_tables(self) -> List[Tuple[int, str, int]]:
        """Return [(index, name, num_rows), ...] for all tables."""
        return [(t.index, t.name, t.num_rows) for t in self.tables]


# ──────────────────────────────────────────────────────────────
# Hash function — replicated from FUN_0202a8f0
# ──────────────────────────────────────────────────────────────

def bdat_hash(name: str, num_buckets: int) -> int:
    """
    Replicate the BDAT name hash function (FUN_0202a8f0).
    hash = 0; for each char in name[:8]: hash = hash * 7 + ord(char)
    return hash % num_buckets
    """
    h = 0
    for ch in name[:8]:
        h = h * 7 + ord(ch)
    return h % num_buckets


# ──────────────────────────────────────────────────────────────
# Reader implementation
# ──────────────────────────────────────────────────────────────

def _read_cstring(data: bytes, offset: int) -> str:
    """Read a null-terminated ASCII string from data."""
    chars = []
    pos = offset
    while pos < len(data) and data[pos] != 0:
        if 0x20 <= data[pos] <= 0x7E:
            chars.append(chr(data[pos]))
        pos += 1
    return ''.join(chars)


def _read_typed_value(data: bytes, offset: int, type_id: int,
                      table_base: int = 0) -> Any:
    """Read a value from data at offset based on type_id."""
    info = TYPE_TABLE.get(type_id)
    if info is None:
        return data[offset] if offset < len(data) else 0

    if offset + info.size > len(data):
        return 0

    raw_val = struct.unpack_from(info.fmt, data, offset)[0]

    if info.is_string:
        # Type 7: string offset relative to table_base
        str_addr = table_base + raw_val
        if str_addr < len(data):
            return _read_cstring(data, str_addr)
        return f"<str@0x{raw_val:04X}>"

    return raw_val


def _parse_columns(data: bytes, table_offset: int,
                   hash_offset: int, hash_count: int) -> List[BdatColumn]:
    """Parse column definitions from the hash chain table."""
    columns = []
    seen_offsets = set()

    for bucket in range(hash_count):
        entry_off = struct.unpack_from(
            '<H', data, table_offset + hash_offset + bucket * 2
        )[0]

        while entry_off != 0:
            if entry_off in seen_offsets:
                break  # prevent infinite loop on malformed data
            seen_offsets.add(entry_off)

            entry_addr = table_offset + entry_off
            col_type_idx = data[entry_addr]
            next_chain = struct.unpack_from('<H', data, entry_addr + 2)[0]

            # Read column name (null-terminated at entry+4)
            col_name = _read_cstring(data, entry_addr + 4)

            # Read type entry from table_base + col_type_idx
            type_addr = table_offset + col_type_idx
            flag = data[type_addr]
            type_id = data[type_addr + 1]
            row_off = struct.unpack_from('<H', data, type_addr + 2)[0]

            if flag == 1 and col_name:  # data column
                info = TYPE_TABLE.get(type_id, BdatTypeInfo('unk', 1, 'B'))
                columns.append(BdatColumn(
                    name=col_name,
                    type_id=type_id,
                    type_name=info.name,
                    size=info.size,
                    row_offset=row_off,
                    is_string=info.is_string,
                    col_type_idx=col_type_idx,
                ))

            entry_off = next_chain

    # Sort by row offset for deterministic ordering
    columns.sort(key=lambda c: c.row_offset)
    return columns


def parse_table(data: bytes, table_offset: int, table_index: int) -> BdatTable:
    """Parse a single BDAT sub-table."""
    magic = data[table_offset:table_offset + 4]
    if magic != b'BDAT':
        return BdatTable(
            index=table_index, name=f'error_{table_index}',
            file_offset=table_offset, flags=0, row_size=0,
            data_offset=0, num_rows=0, hash_offset=0, hash_buckets=0,
        )

    # Parse 18-byte header
    flags      = struct.unpack_from('<H', data, table_offset + 0x04)[0]
    name_off   = struct.unpack_from('<H', data, table_offset + 0x06)[0]
    row_size   = struct.unpack_from('<H', data, table_offset + 0x08)[0]
    data_off   = struct.unpack_from('<H', data, table_offset + 0x0A)[0]
    num_rows   = struct.unpack_from('<H', data, table_offset + 0x0C)[0]
    hash_off   = struct.unpack_from('<H', data, table_offset + 0x0E)[0]
    hash_count = struct.unpack_from('<H', data, table_offset + 0x10)[0]

    # Table name
    table_name = _read_cstring(data, table_offset + name_off)
    if not table_name:
        table_name = f'table_{table_index}'

    # Columns
    columns = _parse_columns(data, table_offset, hash_off, hash_count)

    # Data rows
    rows = []
    row_base = table_offset + data_off
    for r in range(num_rows):
        row = {}
        for col in columns:
            val = _read_typed_value(
                data,
                row_base + r * row_size + col.row_offset,
                col.type_id,
                table_base=table_offset,
            )
            row[col.name] = val
        rows.append(row)

    return BdatTable(
        index=table_index,
        name=table_name,
        file_offset=table_offset,
        flags=flags,
        row_size=row_size,
        data_offset=data_off,
        num_rows=num_rows,
        hash_offset=hash_off,
        hash_buckets=hash_count,
        columns=columns,
        rows=rows,
    )


def read_bdat(data: bytes) -> BdatFile:
    """
    Parse a complete BDAT file from raw bytes.

    Args:
        data: Raw bytes of the BDAT file (e.g., btl/bdat/US/bdat.bin)

    Returns:
        BdatFile with all parsed tables and a mutable copy of the raw data
    """
    table_count = struct.unpack_from('<I', data, 0)[0]
    file_size = struct.unpack_from('<I', data, 4)[0]

    offsets = [
        struct.unpack_from('<I', data, 8 + i * 4)[0]
        for i in range(table_count)
    ]

    tables = [
        parse_table(data, off, i)
        for i, off in enumerate(offsets)
    ]

    return BdatFile(
        table_count=table_count,
        file_size=file_size,
        table_offsets=offsets,
        tables=tables,
        raw_data=bytearray(data),  # mutable copy for patching
    )


def read_bdat_file(filepath: str) -> BdatFile:
    """Load and parse a BDAT file from disk."""
    with open(filepath, 'rb') as f:
        return read_bdat(f.read())
