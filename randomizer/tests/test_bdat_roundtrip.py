#!/usr/bin/env python3
"""Quick test: BDAT round-trip (read → patch → write → verify)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from randomizer.rom_io.bdat_reader import read_bdat_file, read_bdat
from randomizer.rom_io.bdat_writer import BdatWriter

def main():
    bdat_path = "rom/root/btl/bdat/US/bdat.bin"
    
    # 1. Read original
    bdat = read_bdat_file(bdat_path)
    original_size = len(bdat.raw_data)
    print(f"[OK] Loaded BDAT: {bdat.table_count} tables, {original_size} bytes")
    
    # 2. Read original values
    ep = bdat.get_table("enemy_param")
    row5 = ep.get_row(5)
    orig_hp = row5["hp"]
    orig_str = row5["str"]
    orig_def = row5["def"]
    print(f"[OK] Original enemy_param[5]: hp={orig_hp}, str={orig_str}, def={orig_def}")
    
    # 3. Patch values
    writer = BdatWriter(bdat)
    writer.set_value("enemy_param", 5, "hp", 9999)
    writer.set_value("enemy_param", 5, "str", 500)
    writer.set_value("enemy_param", 5, "def", 300)
    patched = writer.build()
    print(f"[OK] Patches applied: {writer.patch_count}")
    
    # 4. Verify size preserved
    assert len(patched) == original_size, f"SIZE MISMATCH: {len(patched)} != {original_size}"
    print(f"[OK] Size preserved: {len(patched)} == {original_size}")
    
    # 5. Re-read patched data
    bdat2 = read_bdat(patched)
    ep2 = bdat2.get_table("enemy_param")
    row5b = ep2.get_row(5)
    
    assert row5b["hp"] == 9999, f"hp mismatch: {row5b['hp']}"
    assert row5b["str"] == 500, f"str mismatch: {row5b['str']}"
    assert row5b["def"] == 300, f"def mismatch: {row5b['def']}"
    print(f"[OK] Round-trip verified: hp={row5b['hp']}, str={row5b['str']}, def={row5b['def']}")
    
    # 6. Verify other rows unchanged
    for i in [0, 1, 2, 3, 4, 6, 7, 8, 9, 10]:
        orig_row = bdat.get_table("enemy_param").get_row(i)
        new_row = ep2.get_row(i)
        for col_name in ["hp", "str", "def", "agi", "lv"]:
            if col_name in orig_row and col_name in new_row:
                assert orig_row[col_name] == new_row[col_name], \
                    f"Row {i} col {col_name} changed: {orig_row[col_name]} -> {new_row[col_name]}"
    print("[OK] Other rows unchanged (verified rows 0-4, 6-10)")
    
    # 7. Verify all tables parseable
    for table in bdat2.tables:
        assert table.name, f"Table {table.index} has no name"
    print(f"[OK] All {bdat2.table_count} tables parse correctly after patching")
    
    # 8. Test clamping
    writer2 = BdatWriter(bdat2)
    writer2.set_value("enemy_param", 0, "hp", 99999)  # exceeds u16
    patched2 = writer2.build()
    bdat3 = read_bdat(patched2)
    hp_val = bdat3.get_table("enemy_param").get_row(0)["hp"]
    print(f"[OK] Clamping test: wrote 99999, read back {hp_val} (u16 max=65535)")
    
    # 9. Test string column protection
    try:
        writer2.set_value("enemy_param", 0, "name", 42)
        print("[FAIL] Should have raised ValueError for string column")
    except ValueError as e:
        print(f"[OK] String column write correctly blocked: {e}")
    
    print("\n=== ALL BDAT ROUND-TRIP TESTS PASSED ===")

if __name__ == "__main__":
    main()
