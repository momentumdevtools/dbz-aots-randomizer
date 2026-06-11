#!/usr/bin/env python3
"""
config.py — Randomizer Configuration & Options
================================================
Defines all configurable options for the randomizer.
Can be loaded from YAML/JSON or constructed programmatically.
"""

from dataclasses import dataclass, field
from typing import Optional
import json
import hashlib


@dataclass
class EnemyStatsConfig:
    """Configuration for enemy stat randomization."""
    enabled: bool = True
    mode: str = "scale"           # "vanilla", "shuffle", "scale", "chaos"
    min_scale: float = 0.75       # minimum scale factor (for "scale" mode)
    max_scale: float = 1.25       # maximum scale factor
    boss_enabled: bool = True     # also randomize bosses
    boss_min_scale: float = 0.85  # bosses get tighter scaling
    boss_max_scale: float = 1.15
    preserve_level: bool = True   # don't change enemy levels


@dataclass
class EncounterConfig:
    """Configuration for encounter randomization."""
    enabled: bool = True
    mode: str = "full"            # "vanilla", "shuffle_drops", "random_resists", "full"
    shuffle_drops: bool = True    # shuffle item drops between enemies
    random_resists: bool = True   # randomize elemental/status resistances
    resist_variance: int = 30     # max resistance change (+-30)


@dataclass
class EncounterShuffleConfig:
    """Configuration for true encounter randomization (Pokemon-style)."""
    enabled: bool = False         # disabled by default
    mode: str = "shuffle_tiered"  # "vanilla", "shuffle_tiered", "shuffle_wild"
    respect_tiers: bool = True    # swap within same level tier
    skip_bosses: bool = True      # don't swap boss-immune enemies
    tier_width: int = 0           # allow cross-tier swaps (0=strict)
    include_heroes: bool = False  # add player characters as enemy sprites


@dataclass
class ItemConfig:
    """Configuration for item/capsule randomization."""
    enabled: bool = False         # disabled by default (more risky)
    mode: str = "shuffle_effects" # "vanilla", "shuffle_effects", "random_prices", "full"
    shuffle_prices: bool = False  # shuffle buy/sell prices (legacy, prefer mode)
    price_variance: float = 0.5   # ±50% price variance


@dataclass
class ShopItemConfig:
    """Configuration for shop price & equipment stat randomization."""
    enabled: bool = False
    mode: str = "shuffle_prices"   # "vanilla", "shuffle_prices", "random_prices", "chaos"
    price_variance: float = 0.5   # ±50% price variance


@dataclass
class PlayerStatsConfig:
    """Configuration for player character stat randomization."""
    enabled: bool = False         # disabled by default
    mode: str = "shuffle"         # "vanilla", "shuffle", "scale", "chaos"
    min_scale: float = 0.8        # for scale mode
    max_scale: float = 1.2
    shuffle_growth: bool = True   # randomize growth curves
    shuffle_base: bool = True     # randomize base/starting stats
    randomize_resists: bool = False  # randomize innate resistances


@dataclass
class KiBlastConfig:
    """Configuration for Ki Blast skill rebalancing."""
    enabled: bool = False
    mode: str = "rebalance"       # "vanilla", "rebalance", "chaos"
    power_variance: float = 0.3   # ±30% power scaling
    cost_variance: float = 0.3    # ±30% MP cost scaling
    shuffle_unlock: bool = True   # shuffle AP unlock order


@dataclass
class DropShuffleConfig:
    """Configuration for enemy drop shuffling."""
    enabled: bool = False
    mode: str = "shuffle"         # "vanilla", "shuffle", "random", "generous"
    include_bosses: bool = False


@dataclass
class BossScalerConfig:
    """Configuration for boss stat scaling."""
    enabled: bool = False
    mode: str = "scale"           # "vanilla", "scale", "nightmare"
    hp_multiplier: float = 1.5
    stat_multiplier: float = 1.0
    randomize_angry: bool = True


@dataclass
class ChaosResistancesConfig:
    """Configuration for resistance randomization."""
    enabled: bool = False
    mode: str = "shuffle"         # "vanilla", "shuffle", "random", "inverse"
    include_bosses: bool = False


@dataclass
class XpRewardConfig:
    """Configuration for XP/Zeni reward scaling."""
    enabled: bool = False
    xp_multiplier: float = 1.0    # global XP multiplier
    zeni_multiplier: float = 1.0  # global Zeni multiplier
    ap_multiplier: float = 1.0    # global AP multiplier


@dataclass
class MusicShuffleConfig:
    """Configuration for music/sound shuffling."""
    enabled: bool = False
    mode: str = "shuffle"         # "vanilla", "shuffle", "chaos"


@dataclass
class PaletteConfig:
    """Configuration for enemy palette randomization."""
    enabled: bool = False
    mode: str = "shift"           # "vanilla", "shift", "random", "chaos"


@dataclass
class RandomizerConfig:
    """Master configuration for the randomizer."""
    # Core settings
    seed: int = 42
    rom_path: str = ""
    output_path: str = ""
    locale: str = "US"            # BDAT locale (US, JP, EN, FR, GR, IT, SP)

    # Sub-randomizer configs
    enemy_stats: EnemyStatsConfig = field(default_factory=EnemyStatsConfig)
    encounters: EncounterConfig = field(default_factory=EncounterConfig)
    encounter_shuffle: EncounterShuffleConfig = field(default_factory=EncounterShuffleConfig)
    items: ItemConfig = field(default_factory=ItemConfig)
    player_stats: PlayerStatsConfig = field(default_factory=PlayerStatsConfig)
    xp_rewards: XpRewardConfig = field(default_factory=XpRewardConfig)
    ki_blasts: KiBlastConfig = field(default_factory=KiBlastConfig)
    drop_shuffle: DropShuffleConfig = field(default_factory=DropShuffleConfig)
    boss_scaler: BossScalerConfig = field(default_factory=BossScalerConfig)
    chaos_resists: ChaosResistancesConfig = field(default_factory=ChaosResistancesConfig)
    shop_items: ShopItemConfig = field(default_factory=ShopItemConfig)
    music_shuffle: MusicShuffleConfig = field(default_factory=MusicShuffleConfig)
    palette: PaletteConfig = field(default_factory=PaletteConfig)

    @property
    def seed_hash(self) -> str:
        """Short hash of the seed for filenames."""
        return hashlib.md5(str(self.seed).encode()).hexdigest()[:8]

    @property
    def default_output_path(self) -> str:
        """Generate default output filename from seed."""
        return f"DBZ_AotS_Randomized_{self.seed}.nds"

    def to_dict(self) -> dict:
        """Serialize to a dict (for JSON export)."""
        return {
            "seed": self.seed,
            "rom_path": self.rom_path,
            "output_path": self.output_path,
            "locale": self.locale,
            "enemy_stats": {
                "enabled": self.enemy_stats.enabled,
                "mode": self.enemy_stats.mode,
                "min_scale": self.enemy_stats.min_scale,
                "max_scale": self.enemy_stats.max_scale,
                "boss_enabled": self.enemy_stats.boss_enabled,
                "boss_min_scale": self.enemy_stats.boss_min_scale,
                "boss_max_scale": self.enemy_stats.boss_max_scale,
                "preserve_level": self.enemy_stats.preserve_level,
            },
            "encounters": {
                "enabled": self.encounters.enabled,
                "mode": self.encounters.mode,
                "shuffle_drops": self.encounters.shuffle_drops,
                "random_resists": self.encounters.random_resists,
                "resist_variance": self.encounters.resist_variance,
            },
            "encounter_shuffle": {
                "enabled": self.encounter_shuffle.enabled,
                "mode": self.encounter_shuffle.mode,
                "respect_tiers": self.encounter_shuffle.respect_tiers,
                "skip_bosses": self.encounter_shuffle.skip_bosses,
                "tier_width": self.encounter_shuffle.tier_width,
                "include_heroes": self.encounter_shuffle.include_heroes,
            },
            "items": {
                "enabled": self.items.enabled,
                "mode": self.items.mode,
                "shuffle_prices": self.items.shuffle_prices,
                "price_variance": self.items.price_variance,
            },
            "player_stats": {
                "enabled": self.player_stats.enabled,
                "mode": self.player_stats.mode,
                "min_scale": self.player_stats.min_scale,
                "max_scale": self.player_stats.max_scale,
                "shuffle_growth": self.player_stats.shuffle_growth,
                "randomize_resists": self.player_stats.randomize_resists,
            },
            "xp_rewards": {
                "enabled": self.xp_rewards.enabled,
                "xp_multiplier": self.xp_rewards.xp_multiplier,
                "zeni_multiplier": self.xp_rewards.zeni_multiplier,
                "ap_multiplier": self.xp_rewards.ap_multiplier,
            },
            "ki_blasts": {
                "enabled": self.ki_blasts.enabled,
                "mode": self.ki_blasts.mode,
                "power_variance": self.ki_blasts.power_variance,
                "cost_variance": self.ki_blasts.cost_variance,
                "shuffle_unlock": self.ki_blasts.shuffle_unlock,
            },
            "drop_shuffle": {
                "enabled": self.drop_shuffle.enabled,
                "mode": self.drop_shuffle.mode,
                "include_bosses": self.drop_shuffle.include_bosses,
            },
            "boss_scaler": {
                "enabled": self.boss_scaler.enabled,
                "mode": self.boss_scaler.mode,
                "hp_multiplier": self.boss_scaler.hp_multiplier,
                "stat_multiplier": self.boss_scaler.stat_multiplier,
                "randomize_angry": self.boss_scaler.randomize_angry,
            },
            "chaos_resists": {
                "enabled": self.chaos_resists.enabled,
                "mode": self.chaos_resists.mode,
                "include_bosses": self.chaos_resists.include_bosses,
            },
            "shop_items": {
                "enabled": self.shop_items.enabled,
                "mode": self.shop_items.mode,
                "price_variance": self.shop_items.price_variance,
            },
            "music_shuffle": {
                "enabled": self.music_shuffle.enabled,
                "mode": self.music_shuffle.mode,
            },
            "palette": {
                "enabled": self.palette.enabled,
                "mode": self.palette.mode,
            },
        }

    def save_json(self, filepath: str) -> None:
        """Save config to a JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> 'RandomizerConfig':
        """Load config from a dict."""
        cfg = cls()
        cfg.seed = d.get("seed", 42)
        cfg.rom_path = d.get("rom_path", "")
        cfg.output_path = d.get("output_path", "")
        cfg.locale = d.get("locale", "US")

        if "enemy_stats" in d:
            es = d["enemy_stats"]
            cfg.enemy_stats = EnemyStatsConfig(
                enabled=es.get("enabled", True),
                mode=es.get("mode", "scale"),
                min_scale=es.get("min_scale", 0.75),
                max_scale=es.get("max_scale", 1.25),
                boss_enabled=es.get("boss_enabled", True),
                boss_min_scale=es.get("boss_min_scale", 0.85),
                boss_max_scale=es.get("boss_max_scale", 1.15),
                preserve_level=es.get("preserve_level", True),
            )

        if "encounters" in d:
            enc = d["encounters"]
            cfg.encounters = EncounterConfig(
                enabled=enc.get("enabled", True),
                mode=enc.get("mode", "full"),
                shuffle_drops=enc.get("shuffle_drops", True),
                random_resists=enc.get("random_resists", True),
                resist_variance=enc.get("resist_variance", 30),
            )

        if "encounter_shuffle" in d:
            es2 = d["encounter_shuffle"]
            cfg.encounter_shuffle = EncounterShuffleConfig(
                enabled=es2.get("enabled", False),
                mode=es2.get("mode", "shuffle_tiered"),
                respect_tiers=es2.get("respect_tiers", True),
                skip_bosses=es2.get("skip_bosses", True),
                tier_width=es2.get("tier_width", 0),
                include_heroes=es2.get("include_heroes", False),
            )

        if "items" in d:
            it = d["items"]
            cfg.items = ItemConfig(
                enabled=it.get("enabled", False),
                mode=it.get("mode", "shuffle_effects"),
                shuffle_prices=it.get("shuffle_prices", False),
                price_variance=it.get("price_variance", 0.5),
            )

        if "player_stats" in d:
            ps = d["player_stats"]
            cfg.player_stats = PlayerStatsConfig(
                enabled=ps.get("enabled", False),
                mode=ps.get("mode", "shuffle"),
                min_scale=ps.get("min_scale", 0.8),
                max_scale=ps.get("max_scale", 1.2),
                shuffle_growth=ps.get("shuffle_growth", True),
                randomize_resists=ps.get("randomize_resists", False),
            )

        if "xp_rewards" in d:
            xp = d["xp_rewards"]
            cfg.xp_rewards = XpRewardConfig(
                enabled=xp.get("enabled", False),
                xp_multiplier=xp.get("xp_multiplier", 1.0),
                zeni_multiplier=xp.get("zeni_multiplier", 1.0),
                ap_multiplier=xp.get("ap_multiplier", 1.0),
            )

        if "ki_blasts" in d:
            kb = d["ki_blasts"]
            cfg.ki_blasts = KiBlastConfig(
                enabled=kb.get("enabled", False),
                mode=kb.get("mode", "rebalance"),
                power_variance=kb.get("power_variance", 0.3),
                cost_variance=kb.get("cost_variance", 0.3),
                shuffle_unlock=kb.get("shuffle_unlock", True),
            )

        if "drop_shuffle" in d:
            ds = d["drop_shuffle"]
            cfg.drop_shuffle = DropShuffleConfig(
                enabled=ds.get("enabled", False),
                mode=ds.get("mode", "shuffle"),
                include_bosses=ds.get("include_bosses", False),
            )

        if "boss_scaler" in d:
            bs = d["boss_scaler"]
            cfg.boss_scaler = BossScalerConfig(
                enabled=bs.get("enabled", False),
                mode=bs.get("mode", "scale"),
                hp_multiplier=bs.get("hp_multiplier", 1.5),
                stat_multiplier=bs.get("stat_multiplier", 1.0),
                randomize_angry=bs.get("randomize_angry", True),
            )

        if "chaos_resists" in d:
            cr = d["chaos_resists"]
            cfg.chaos_resists = ChaosResistancesConfig(
                enabled=cr.get("enabled", False),
                mode=cr.get("mode", "shuffle"),
                include_bosses=cr.get("include_bosses", False),
            )

        if "shop_items" in d:
            si = d["shop_items"]
            cfg.shop_items = ShopItemConfig(
                enabled=si.get("enabled", False),
                mode=si.get("mode", "shuffle_prices"),
                price_variance=si.get("price_variance", 0.5),
            )

        if "music_shuffle" in d:
            ms = d["music_shuffle"]
            cfg.music_shuffle = MusicShuffleConfig(
                enabled=ms.get("enabled", False),
                mode=ms.get("mode", "shuffle"),
            )

        if "palette" in d:
            pal = d["palette"]
            cfg.palette = PaletteConfig(
                enabled=pal.get("enabled", False),
                mode=pal.get("mode", "shift"),
            )

        return cfg

    @classmethod
    def load_json(cls, filepath: str) -> 'RandomizerConfig':
        """Load config from a JSON file."""
        with open(filepath, 'r') as f:
            return cls.from_dict(json.load(f))

    def summary(self) -> str:
        """Human-readable summary of active settings."""
        lines = [
            f"=== DBZ AotS Randomizer Config ===",
            f"Seed: {self.seed}",
            f"Locale: {self.locale}",
            f"",
            f"Enemy Stats: {'ON' if self.enemy_stats.enabled else 'OFF'}"
            f" ({self.enemy_stats.mode})",
        ]
        if self.enemy_stats.enabled:
            lines.append(
                f"  Scale: {self.enemy_stats.min_scale:.0%}–"
                f"{self.enemy_stats.max_scale:.0%}"
            )
            lines.append(
                f"  Bosses: {'ON' if self.enemy_stats.boss_enabled else 'OFF'}"
            )

        lines.append(
            f"Encounters: {'ON' if self.encounters.enabled else 'OFF'}"
            f" ({self.encounters.mode})"
        )
        lines.append(
            f"Items: {'ON' if self.items.enabled else 'OFF'}"
            + (f" ({self.items.mode})" if self.items.enabled else "")
        )
        lines.append(
            f"Player Stats: {'ON' if self.player_stats.enabled else 'OFF'}"
            + (f" ({self.player_stats.mode})" if self.player_stats.enabled else "")
        )
        lines.append(
            f"XP Rewards: {'ON' if self.xp_rewards.enabled else 'OFF'}"
        )
        if self.xp_rewards.enabled:
            lines.append(
                f"  XP x{self.xp_rewards.xp_multiplier:.1f} / "
                f"Zeni x{self.xp_rewards.zeni_multiplier:.1f} / "
                f"AP x{self.xp_rewards.ap_multiplier:.1f}"
            )
        lines.append(
            f"Ki Blasts: {'ON' if self.ki_blasts.enabled else 'OFF'}"
            + (f" ({self.ki_blasts.mode})" if self.ki_blasts.enabled else "")
        )
        lines.append(
            f"Drop Shuffle: {'ON' if self.drop_shuffle.enabled else 'OFF'}"
            + (f" ({self.drop_shuffle.mode})" if self.drop_shuffle.enabled else "")
        )
        lines.append(
            f"Boss Scaler: {'ON' if self.boss_scaler.enabled else 'OFF'}"
            + (f" ({self.boss_scaler.mode})" if self.boss_scaler.enabled else "")
        )
        lines.append(
            f"Chaos Resists: {'ON' if self.chaos_resists.enabled else 'OFF'}"
            + (f" ({self.chaos_resists.mode})" if self.chaos_resists.enabled else "")
        )
        lines.append(
            f"Shop Items: {'ON' if self.shop_items.enabled else 'OFF'}"
            + (f" ({self.shop_items.mode})" if self.shop_items.enabled else "")
        )
        lines.append(
            f"Music Shuffle: {'ON' if self.music_shuffle.enabled else 'OFF'}"
            + (f" ({self.music_shuffle.mode})" if self.music_shuffle.enabled else "")
        )
        lines.append(
            f"Palette: {'ON' if self.palette.enabled else 'OFF'}"
            + (f" ({self.palette.mode})" if self.palette.enabled else "")
        )
        return "\n".join(lines)
