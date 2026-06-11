#!/usr/bin/env python3
"""
presets.py — Pre-configured Randomizer Settings
=================================================
One-click configurations for different play styles.
"""

from randomizer.config import (
    RandomizerConfig, EnemyStatsConfig, EncounterConfig,
    EncounterShuffleConfig, ItemConfig, PlayerStatsConfig,
    XpRewardConfig, KiBlastConfig, DropShuffleConfig,
    BossScalerConfig, ChaosResistancesConfig, ShopItemConfig,
    MusicShuffleConfig, PaletteConfig,
)


PRESETS = {
    "Custom": None,  # User-defined, no preset applied

    "Balanced": {
        "description": "Gentle randomization — same difficulty, fresh experience",
        "encounter_shuffle": EncounterShuffleConfig(
            enabled=True, mode="shuffle_tiered", include_heroes=False),
        "enemy_stats": EnemyStatsConfig(
            enabled=True, mode="scale", min_scale=0.9, max_scale=1.1),
        "encounters": EncounterConfig(enabled=False),
        "items": ItemConfig(enabled=True, mode="shuffle_effects"),
        "player_stats": PlayerStatsConfig(enabled=False),
        "xp_rewards": XpRewardConfig(enabled=False),
        "ki_blasts": KiBlastConfig(enabled=True, mode="rebalance",
                                   power_variance=0.15, cost_variance=0.15),
        "drop_shuffle": DropShuffleConfig(enabled=True, mode="shuffle"),
        "boss_scaler": BossScalerConfig(enabled=False),
        "chaos_resists": ChaosResistancesConfig(enabled=False),
        "shop_items": ShopItemConfig(enabled=True, mode="shuffle_prices"),
    },

    "Chaos": {
        "description": "Total chaos — everything is randomized, anything can happen",
        "encounter_shuffle": EncounterShuffleConfig(
            enabled=True, mode="shuffle_wild", include_heroes=True),
        "enemy_stats": EnemyStatsConfig(
            enabled=True, mode="chaos"),
        "encounters": EncounterConfig(enabled=True, mode="full"),
        "items": ItemConfig(enabled=True, mode="full"),
        "player_stats": PlayerStatsConfig(
            enabled=True, mode="shuffle", shuffle_growth=True),
        "xp_rewards": XpRewardConfig(
            enabled=True, xp_multiplier=0.5, zeni_multiplier=0.5),
        "ki_blasts": KiBlastConfig(enabled=True, mode="chaos"),
        "drop_shuffle": DropShuffleConfig(
            enabled=True, mode="random", include_bosses=True),
        "boss_scaler": BossScalerConfig(
            enabled=True, mode="nightmare", hp_multiplier=2.0),
        "chaos_resists": ChaosResistancesConfig(
            enabled=True, mode="random", include_bosses=True),
        "shop_items": ShopItemConfig(enabled=True, mode="chaos"),
    },

    "Nightmare": {
        "description": "Maximum challenge — for veteran players only",
        "encounter_shuffle": EncounterShuffleConfig(
            enabled=True, mode="shuffle_tiered", include_heroes=True),
        "enemy_stats": EnemyStatsConfig(
            enabled=True, mode="scale", min_scale=1.3, max_scale=1.8),
        "encounters": EncounterConfig(enabled=False),
        "items": ItemConfig(enabled=False),
        "player_stats": PlayerStatsConfig(enabled=False),
        "xp_rewards": XpRewardConfig(
            enabled=True, xp_multiplier=0.5, zeni_multiplier=0.3),
        "ki_blasts": KiBlastConfig(enabled=False),
        "drop_shuffle": DropShuffleConfig(enabled=False),
        "boss_scaler": BossScalerConfig(
            enabled=True, mode="nightmare",
            hp_multiplier=2.5, stat_multiplier=1.5),
        "chaos_resists": ChaosResistancesConfig(enabled=False),
        "shop_items": ShopItemConfig(enabled=False),
    },

    "Chill": {
        "description": "Relaxed run — weaker enemies, bigger rewards",
        "encounter_shuffle": EncounterShuffleConfig(enabled=False),
        "enemy_stats": EnemyStatsConfig(
            enabled=True, mode="scale", min_scale=0.4, max_scale=0.7),
        "encounters": EncounterConfig(enabled=False),
        "items": ItemConfig(enabled=True, mode="random_prices"),
        "player_stats": PlayerStatsConfig(enabled=False),
        "xp_rewards": XpRewardConfig(
            enabled=True, xp_multiplier=3.0,
            zeni_multiplier=3.0, ap_multiplier=2.0),
        "ki_blasts": KiBlastConfig(enabled=False),
        "drop_shuffle": DropShuffleConfig(
            enabled=True, mode="generous"),
        "boss_scaler": BossScalerConfig(
            enabled=True, mode="scale", hp_multiplier=0.5, stat_multiplier=0.7),
        "chaos_resists": ChaosResistancesConfig(enabled=False),
        "shop_items": ShopItemConfig(
            enabled=True, mode="random_prices", price_variance=0.8),
    },

    "Boss Mix": {
        "description": "Adds boss sprites (Raditz, Vegeta, Broly...) into the random encounter pool alongside regular enemies",
        "encounter_shuffle": EncounterShuffleConfig(
            enabled=True, mode="shuffle_tiered", include_heroes=True),
        "enemy_stats": EnemyStatsConfig(
            enabled=True, mode="scale", min_scale=1.0, max_scale=1.3),
        "encounters": EncounterConfig(enabled=False),
        "items": ItemConfig(enabled=False),
        "player_stats": PlayerStatsConfig(enabled=False),
        "xp_rewards": XpRewardConfig(
            enabled=True, xp_multiplier=1.5, zeni_multiplier=1.5),
        "ki_blasts": KiBlastConfig(enabled=True, mode="rebalance"),
        "drop_shuffle": DropShuffleConfig(enabled=True, mode="shuffle"),
        "boss_scaler": BossScalerConfig(
            enabled=True, mode="scale", hp_multiplier=1.5),
        "chaos_resists": ChaosResistancesConfig(
            enabled=True, mode="shuffle"),
        "shop_items": ShopItemConfig(enabled=False),
    },
}


def get_preset_names() -> list[str]:
    """Return list of available preset names."""
    return list(PRESETS.keys())


def apply_preset(config: RandomizerConfig, preset_name: str) -> None:
    """Apply a preset to the given config, overwriting module settings."""
    preset = PRESETS.get(preset_name)
    if preset is None:
        return  # "Custom" or unknown — don't change anything

    for key, value in preset.items():
        if key == "description":
            continue
        if hasattr(config, key):
            setattr(config, key, value)


def get_preset_description(preset_name: str) -> str:
    """Return the human-readable description for a preset."""
    preset = PRESETS.get(preset_name)
    if preset is None:
        return "Custom settings"
    return preset.get("description", "")
