#!/usr/bin/env python3
"""
__main__.py — CLI Entry Point for the DBZ AotS Randomizer
===========================================================
Usage:
    python -m randomizer --rom "path/to/rom.nds" --seed 42
    python -m randomizer --rom "path/to/rom.nds" --seed 42 --enemy-stats scale
    python -m randomizer --rom "path/to/rom.nds" --config settings.json

Full options:
    --rom PATH          Path to the original NDS ROM (required)
    --seed N            Seed value (default: random)
    --output PATH       Output ROM path (default: auto-generated)
    --locale CODE       BDAT locale: US, JP, EN, FR, GR, IT, SP (default: US)
    --config PATH       Load settings from a JSON config file
    --enemy-stats MODE  Enemy stat mode: vanilla/shuffle/scale/chaos (default: scale)
    --enemy-scale MIN MAX  Scale range for enemy stats (default: 0.75 1.25)
    --encounters MODE   Encounter mode: vanilla/shuffle_drops/random_resists/full
    --xp-mult N         XP multiplier (e.g., 1.5 for 50% more XP)
    --zeni-mult N       Zeni multiplier
    --no-bosses         Don't randomize boss stats
    --dump-tables       Dump all BDAT tables to JSON and exit
"""

import argparse
import sys
import os
import time
import json

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from randomizer.config import RandomizerConfig
from randomizer.patcher.rom_builder import RomBuilder


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="randomizer",
        description="DBZ: Attack of the Saiyans — NDS ROM Randomizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m randomizer --rom game.nds --seed 42
  python -m randomizer --rom game.nds --seed 42 --enemy-stats chaos
  python -m randomizer --rom game.nds --seed 42 --xp-mult 2.0
  python -m randomizer --rom game.nds --dump-tables
        """,
    )

    # Required
    parser.add_argument("--rom", required=True, help="Path to original NDS ROM")

    # Core
    parser.add_argument("--seed", type=int, default=None,
                        help="Seed value (default: random)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output ROM path")
    parser.add_argument("--locale", default="US",
                        choices=["US", "JP", "EN", "FR", "GR", "IT", "SP"],
                        help="BDAT locale (default: US)")
    parser.add_argument("--config", default=None,
                        help="Load settings from JSON config file")

    # Enemy stats
    parser.add_argument("--enemy-stats", default="scale",
                        choices=["vanilla", "shuffle", "scale", "chaos"],
                        help="Enemy stat randomization mode")
    parser.add_argument("--enemy-scale", nargs=2, type=float,
                        metavar=("MIN", "MAX"), default=[0.75, 1.25],
                        help="Scale range for enemy stats")
    parser.add_argument("--no-bosses", action="store_true",
                        help="Don't randomize boss stats")

    # Encounters
    parser.add_argument("--encounters", default="full",
                        choices=["vanilla", "shuffle_drops",
                                 "random_resists", "full"],
                        help="Encounter randomization mode")

    # Encounter Shuffle (Pokemon-style)
    parser.add_argument("--encounter-shuffle", default="vanilla",
                        choices=["vanilla", "shuffle_tiered", "shuffle_wild"],
                        help="Shuffle which enemies appear (Pokemon-style)")
    parser.add_argument("--include-heroes", action="store_true",
                        help="Add player characters (Goku, Gohan...) as enemy encounters")

    # Rewards
    parser.add_argument("--xp-mult", type=float, default=1.0,
                        help="XP multiplier")
    parser.add_argument("--zeni-mult", type=float, default=1.0,
                        help="Zeni multiplier")
    parser.add_argument("--ap-mult", type=float, default=1.0,
                        help="AP multiplier")

    # Items
    parser.add_argument("--items", default="vanilla",
                        choices=["vanilla", "shuffle_effects",
                                 "random_prices", "full"],
                        help="Item randomization mode (default: vanilla/off)")

    # Player stats
    parser.add_argument("--player-stats", default="vanilla",
                        choices=["vanilla", "shuffle", "scale", "chaos"],
                        help="Player character stat mode (default: vanilla/off)")

    # Utility
    parser.add_argument("--dump-tables", action="store_true",
                        help="Dump all BDAT tables to JSON and exit")

    # Ki Blast Rebalancer
    parser.add_argument("--ki-blasts", default="vanilla",
                        choices=["vanilla", "rebalance", "chaos"],
                        help="Ki Blast skill rebalancing mode")

    # Drop Shuffle
    parser.add_argument("--drop-shuffle", default="vanilla",
                        choices=["vanilla", "shuffle", "random", "generous"],
                        help="Enemy drop shuffle mode")

    # Boss Scaler
    parser.add_argument("--boss-scaler", default="vanilla",
                        choices=["vanilla", "scale", "nightmare"],
                        help="Boss stat scaling mode")
    parser.add_argument("--boss-hp-mult", type=float, default=1.5,
                        help="Boss HP multiplier (for scale mode)")
    parser.add_argument("--boss-stat-mult", type=float, default=1.0,
                        help="Boss combat stat multiplier")

    # Chaos Resistances
    parser.add_argument("--chaos-resists", default="vanilla",
                        choices=["vanilla", "shuffle", "random", "inverse"],
                        help="Resistance randomization mode")

    return parser.parse_args()


def dump_tables(rom_path: str, locale: str) -> None:
    """Dump all BDAT tables to JSON for reference."""
    from randomizer.rom_io.nds_rom import NdsRom
    from randomizer.rom_io.bdat_reader import read_bdat

    print(f"Loading ROM: {rom_path}")
    rom = NdsRom.from_file(rom_path)
    bdat_bytes = rom.get_bdat(locale)
    bdat = read_bdat(bdat_bytes)

    output_dir = os.path.join("output", "bdat_dump")
    os.makedirs(output_dir, exist_ok=True)

    print(f"\nDumping {bdat.table_count} tables to {output_dir}/")
    for table in bdat.tables:
        filename = f"{table.index:02d}_{table.name}.json"
        filepath = os.path.join(output_dir, filename)
        data = {
            "name": table.name,
            "index": table.index,
            "num_rows": table.num_rows,
            "row_size": table.row_size,
            "columns": [
                {"name": c.name, "type": c.type_name,
                 "offset": f"0x{c.row_offset:02X}"}
                for c in table.columns
            ],
            "rows": table.rows,
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  {filename} ({table.num_rows} rows)")

    print(f"\nDone! {bdat.table_count} tables exported.")


def main() -> int:
    args = parse_args()

    # Validate ROM exists
    if not os.path.exists(args.rom):
        print(f"ERROR: ROM not found: {args.rom}", file=sys.stderr)
        return 1

    # Dump tables mode
    if args.dump_tables:
        dump_tables(args.rom, args.locale)
        return 0

    # Build config
    if args.config and os.path.exists(args.config):
        config = RandomizerConfig.load_json(args.config)
        config.rom_path = args.rom  # override ROM path
    else:
        # Generate seed if not provided
        seed = args.seed
        if seed is None:
            seed = int(time.time()) & 0xFFFFFFFF
            print(f"Generated seed: {seed}")

        config = RandomizerConfig(
            seed=seed,
            rom_path=args.rom,
            output_path=args.output or "",
            locale=args.locale,
        )

        # Apply CLI options
        config.enemy_stats.enabled = (args.enemy_stats != "vanilla")
        config.enemy_stats.mode = args.enemy_stats
        config.enemy_stats.min_scale = args.enemy_scale[0]
        config.enemy_stats.max_scale = args.enemy_scale[1]
        config.enemy_stats.boss_enabled = not args.no_bosses

        config.encounters.enabled = (args.encounters != "vanilla")
        config.encounters.mode = args.encounters
        config.encounters.shuffle_drops = args.encounters in (
            "shuffle_drops", "full")
        config.encounters.random_resists = args.encounters in (
            "random_resists", "full")

        xp_changed = (args.xp_mult != 1.0 or args.zeni_mult != 1.0
                      or args.ap_mult != 1.0)
        config.xp_rewards.enabled = xp_changed
        config.xp_rewards.xp_multiplier = args.xp_mult
        config.xp_rewards.zeni_multiplier = args.zeni_mult
        config.xp_rewards.ap_multiplier = args.ap_mult

        # Items
        config.items.enabled = (args.items != "vanilla")
        config.items.mode = args.items

        # Player stats
        config.player_stats.enabled = (args.player_stats != "vanilla")
        config.player_stats.mode = args.player_stats

        # Encounter shuffle
        config.encounter_shuffle.enabled = (args.encounter_shuffle != "vanilla")
        config.encounter_shuffle.mode = args.encounter_shuffle
        config.encounter_shuffle.include_heroes = args.include_heroes

        # If heroes requested, force encounter shuffle on
        if args.include_heroes and not config.encounter_shuffle.enabled:
            config.encounter_shuffle.enabled = True
            config.encounter_shuffle.mode = "shuffle_tiered"

        # Ki Blast Rebalancer
        config.ki_blasts.enabled = (args.ki_blasts != "vanilla")
        config.ki_blasts.mode = args.ki_blasts

        # Drop Shuffle
        config.drop_shuffle.enabled = (args.drop_shuffle != "vanilla")
        config.drop_shuffle.mode = args.drop_shuffle

        # Boss Scaler
        config.boss_scaler.enabled = (args.boss_scaler != "vanilla")
        config.boss_scaler.mode = args.boss_scaler
        config.boss_scaler.hp_multiplier = args.boss_hp_mult
        config.boss_scaler.stat_multiplier = args.boss_stat_mult

        # Chaos Resistances
        config.chaos_resists.enabled = (args.chaos_resists != "vanilla")
        config.chaos_resists.mode = args.chaos_resists

    # Show config summary
    print(config.summary())
    print("")

    # Build!
    builder = RomBuilder(config)
    try:
        output_path = builder.build()
        print(f"\nDone! Randomized ROM saved to: {output_path}")
        return 0
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
