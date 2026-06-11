#!/usr/bin/env python3
"""
gui.py — Desktop GUI for DBZ AotS Randomizer
===============================================
CustomTkinter-based desktop application.
Run directly or via: python -m randomizer.gui
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import customtkinter as ctk
from randomizer.config import RandomizerConfig
from randomizer.presets import get_preset_names, apply_preset, get_preset_description

# Theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# App colors
BG_DARK = "#0d0d0d"
BG_CARD = "#1a1a2e"
ACCENT = "#e94560"
ACCENT_HOVER = "#ff6b81"
TEXT_DIM = "#8892b0"
TEXT_DESC = "#667088"
GOLD = "#ffd700"
SUCCESS = "#00d26a"


class SectionFrame(ctk.CTkFrame):
    """Module section with title, icon, and description."""

    def __init__(self, master, title: str, icon: str = "",
                 description: str = "", **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=10, **kwargs)
        self.grid_columnconfigure(1, weight=1)
        self._title = title

        # Header row
        self._header = ctk.CTkFrame(self, fg_color="transparent")
        self._header.grid(row=0, column=0, columnspan=3, sticky="ew",
                          padx=8, pady=(6, 0))
        self._header.grid_columnconfigure(1, weight=1)

        self._icon_label = ctk.CTkLabel(
            self._header, text=icon, font=("Segoe UI Emoji", 16))
        self._icon_label.grid(row=0, column=0, padx=(0, 6))

        self._title_label = ctk.CTkLabel(
            self._header, text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#e0e0e0")
        self._title_label.grid(row=0, column=1, sticky="w")

        # Description row (if provided)
        if description:
            self._desc_label = ctk.CTkLabel(
                self, text=description,
                font=ctk.CTkFont(size=11), text_color=TEXT_DESC,
                wraplength=540, justify="left")
            self._desc_label.grid(row=1, column=0, columnspan=3, sticky="w",
                                  padx=12, pady=(0, 2))

        # Content frame (holds widgets)
        content_row = 2 if description else 1
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.grid(row=content_row, column=0, columnspan=3,
                           sticky="ew", padx=12, pady=(0, 8))
        self._content.grid_columnconfigure(1, weight=1)

    @property
    def content(self):
        return self._content


class RandomizerApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title("DBZ: Attack of the Saiyans Randomizer")
        self.geometry("620x900")
        self.minsize(580, 700)
        self.configure(fg_color=BG_DARK)

        self._config = RandomizerConfig()
        self._building = False

        self._create_widgets()

    def _create_widgets(self):
        # Main scrollable container
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=BG_DARK, corner_radius=0)
        self._scroll.pack(fill="both", expand=True, padx=0, pady=0)
        self._scroll.grid_columnconfigure(0, weight=1)

        row = 0

        # --- Title Bar ---
        title_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        title_frame.grid(row=row, column=0, sticky="ew", padx=16, pady=(12, 4))
        ctk.CTkLabel(
            title_frame, text="DBZ: Attack of the Saiyans",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=GOLD
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_frame, text="Randomizer v1.0",
            font=ctk.CTkFont(size=12), text_color=TEXT_DIM
        ).pack(anchor="w")
        row += 1

        # --- ROM & Seed ---
        rom_section = SectionFrame(
            self._scroll, "ROM & Seed", "ROM",
            "Select your original NDS ROM, set a seed, "
            "and optionally pick a preset.")
        rom_section.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1

        # ROM path
        ctk.CTkLabel(rom_section.content, text="ROM:", text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, sticky="w", pady=2)
        self._rom_var = ctk.StringVar()
        rom_entry = ctk.CTkEntry(
            rom_section.content, textvariable=self._rom_var,
            placeholder_text="Path to .nds ROM file...",
            width=380)
        rom_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        ctk.CTkButton(
            rom_section.content, text="Browse",
            width=70, command=self._browse_rom,
            fg_color=ACCENT, hover_color=ACCENT_HOVER
        ).grid(row=0, column=2, padx=4, pady=2)

        # Seed
        ctk.CTkLabel(rom_section.content, text="Seed:", text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, sticky="w", pady=2)
        self._seed_var = ctk.StringVar(value="42")
        ctk.CTkEntry(
            rom_section.content, textvariable=self._seed_var, width=150
        ).grid(row=1, column=1, sticky="w", padx=4, pady=2)
        ctk.CTkButton(
            rom_section.content, text="Random", width=70,
            command=self._random_seed,
            fg_color="#2a2a4a", hover_color="#3a3a6a"
        ).grid(row=1, column=2, sticky="w", padx=4, pady=2)

        # Preset
        ctk.CTkLabel(rom_section.content, text="Preset:", text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=2, column=0, sticky="w", pady=2)
        self._preset_var = ctk.StringVar(value="Custom")
        preset_menu = ctk.CTkOptionMenu(
            rom_section.content, variable=self._preset_var,
            values=get_preset_names(), command=self._apply_preset,
            width=200, fg_color="#2a2a4a",
            button_color=ACCENT, button_hover_color=ACCENT_HOVER)
        preset_menu.grid(row=2, column=1, sticky="w", padx=4, pady=2)
        self._preset_desc = ctk.CTkLabel(
            rom_section.content, text="", text_color=TEXT_DIM,
            font=ctk.CTkFont(size=11, slant="italic"))
        self._preset_desc.grid(row=3, column=0, columnspan=3,
                               sticky="w", pady=(0, 2))

        # --- Encounter Shuffle ---
        enc_section = SectionFrame(
            self._scroll, "Encounter Shuffle", "ENE",
            "Swap enemy sprites between encounters. "
            "Tiered keeps enemies within similar level ranges. "
            "Wild mode ignores tiers for full chaos.")
        enc_section.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1

        ctk.CTkLabel(enc_section.content, text="Mode:", text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, sticky="w")
        self._enc_shuffle_var = ctk.StringVar(value="vanilla")
        ctk.CTkOptionMenu(
            enc_section.content, variable=self._enc_shuffle_var,
            values=["vanilla", "shuffle_tiered", "shuffle_wild"],
            width=180, fg_color="#2a2a4a"
        ).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        self._heroes_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            enc_section.content,
            text="Include Bosses (Raditz, Vegeta, Broly...)",
            variable=self._heroes_var, text_color="#e0e0e0",
            fg_color=ACCENT, hover_color=ACCENT_HOVER
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=2)

        # --- Enemy Stats ---
        stat_section = SectionFrame(
            self._scroll, "Enemy Stats", "STS",
            "Modify enemy HP, ATK, DEF etc. "
            "Scale applies a random multiplier within the range below. "
            "Shuffle swaps stats between enemies. Chaos fully randomizes.")
        stat_section.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1

        ctk.CTkLabel(stat_section.content, text="Mode:", text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, sticky="w")
        self._enemy_stat_var = ctk.StringVar(value="scale")
        ctk.CTkOptionMenu(
            stat_section.content, variable=self._enemy_stat_var,
            values=["vanilla", "shuffle", "scale", "chaos"],
            width=180, fg_color="#2a2a4a",
            command=self._on_enemy_stat_mode_change
        ).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        # Scale range (only visible when mode = "scale")
        self._scale_frame = ctk.CTkFrame(
            stat_section.content, fg_color="transparent")
        self._scale_frame.grid(row=1, column=0, columnspan=3,
                               sticky="w", padx=0)
        ctk.CTkLabel(self._scale_frame, text="Range:", text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).pack(
            side="left", padx=(0, 4))
        self._stat_min_var = ctk.StringVar(value="0.75")
        self._stat_max_var = ctk.StringVar(value="1.25")
        ctk.CTkEntry(self._scale_frame, textvariable=self._stat_min_var,
                      width=60).pack(side="left", padx=2)
        ctk.CTkLabel(self._scale_frame, text="to",
                      text_color=TEXT_DIM).pack(side="left", padx=4)
        ctk.CTkEntry(self._scale_frame, textvariable=self._stat_max_var,
                      width=60).pack(side="left", padx=2)
        ctk.CTkLabel(self._scale_frame,
                      text="(multiplier, e.g. 0.75 = 75%)",
                      text_color=TEXT_DESC,
                      font=ctk.CTkFont(size=10)).pack(
            side="left", padx=(8, 0))

        # --- Boss Scaler ---
        boss_section = SectionFrame(
            self._scroll, "Boss Scaler", "BOS",
            "Scale boss stats independently. "
            "Nightmare mode makes bosses significantly stronger "
            "with higher HP and stat multipliers.")
        boss_section.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1

        ctk.CTkLabel(boss_section.content, text="Mode:", text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, sticky="w")
        self._boss_mode_var = ctk.StringVar(value="vanilla")
        ctk.CTkOptionMenu(
            boss_section.content, variable=self._boss_mode_var,
            values=["vanilla", "scale", "nightmare"],
            width=180, fg_color="#2a2a4a"
        ).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        ctk.CTkLabel(boss_section.content, text="HP Mult:",
                      text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, sticky="w")
        self._boss_hp_var = ctk.DoubleVar(value=1.5)
        self._boss_hp_label = ctk.CTkLabel(
            boss_section.content, text="1.5x", text_color=GOLD,
            font=ctk.CTkFont(size=12, weight="bold"))
        self._boss_hp_label.grid(row=1, column=2, padx=4)
        ctk.CTkSlider(
            boss_section.content, from_=0.5, to=5.0,
            variable=self._boss_hp_var, width=180,
            button_color=ACCENT, button_hover_color=ACCENT_HOVER,
            command=lambda v: self._boss_hp_label.configure(
                text=f"{v:.1f}x")
        ).grid(row=1, column=1, padx=4, pady=2)

        # --- Ki Blasts ---
        ki_section = SectionFrame(
            self._scroll, "Ki Blasts", "KI",
            "Adjust Ki blast power and cost. "
            "Rebalance normalizes outliers. "
            "Chaos fully randomizes damage and Ki cost.")
        ki_section.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1

        ctk.CTkLabel(ki_section.content, text="Mode:", text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, sticky="w")
        self._ki_mode_var = ctk.StringVar(value="vanilla")
        ctk.CTkOptionMenu(
            ki_section.content, variable=self._ki_mode_var,
            values=["vanilla", "rebalance", "chaos"],
            width=180, fg_color="#2a2a4a"
        ).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        # --- Items & Drops ---
        item_section = SectionFrame(
            self._scroll, "Items & Drops", "ITM",
            "Shop: Shuffle or randomize shop prices. "
            "Drops: Change which items enemies drop after battle. "
            "Generous mode increases drop rates.")
        item_section.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1

        ctk.CTkLabel(item_section.content, text="Shop:", text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, sticky="w")
        self._shop_var = ctk.StringVar(value="vanilla")
        ctk.CTkOptionMenu(
            item_section.content, variable=self._shop_var,
            values=["vanilla", "shuffle_prices", "random_prices", "chaos"],
            width=180, fg_color="#2a2a4a"
        ).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        ctk.CTkLabel(item_section.content, text="Drops:", text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, sticky="w")
        self._drop_var = ctk.StringVar(value="vanilla")
        ctk.CTkOptionMenu(
            item_section.content, variable=self._drop_var,
            values=["vanilla", "shuffle", "random", "generous"],
            width=180, fg_color="#2a2a4a"
        ).grid(row=1, column=1, sticky="w", padx=4, pady=2)

        # --- Player Stats ---
        player_section = SectionFrame(
            self._scroll, "Player Stats", "PLR",
            "Base Stats: Randomize starting HP, KI, ATK, DEF etc. "
            "Growth: Randomize stat gains per level-up. "
            "Resists: Change elemental/status resistances.")
        player_section.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1

        ctk.CTkLabel(player_section.content, text="Base Stats:",
                      text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, sticky="w")
        self._base_stats_var = ctk.StringVar(value="vanilla")
        ctk.CTkOptionMenu(
            player_section.content, variable=self._base_stats_var,
            values=["vanilla", "shuffle", "scale"],
            width=180, fg_color="#2a2a4a"
        ).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        ctk.CTkLabel(player_section.content, text="Growth:",
                      text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, sticky="w")
        self._growth_var = ctk.StringVar(value="vanilla")
        ctk.CTkOptionMenu(
            player_section.content, variable=self._growth_var,
            values=["vanilla", "shuffle", "scale"],
            width=180, fg_color="#2a2a4a"
        ).grid(row=1, column=1, sticky="w", padx=4, pady=2)

        ctk.CTkLabel(player_section.content, text="Resists:",
                      text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=2, column=0, sticky="w")
        self._resist_var = ctk.StringVar(value="vanilla")
        ctk.CTkOptionMenu(
            player_section.content, variable=self._resist_var,
            values=["vanilla", "shuffle", "random", "inverse"],
            width=180, fg_color="#2a2a4a"
        ).grid(row=2, column=1, sticky="w", padx=4, pady=2)

        # --- Rewards ---
        reward_section = SectionFrame(
            self._scroll, "Rewards", "RWD",
            "Multiply XP, Zeni, and AP gained after battle. "
            "Values above 1.0 make leveling faster, "
            "below 1.0 makes it a grind.")
        reward_section.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1

        for i, (label, var_name, default) in enumerate([
            ("XP:", "_xp_var", 1.0),
            ("Zeni:", "_zeni_var", 1.0),
            ("AP:", "_ap_var", 1.0),
        ]):
            ctk.CTkLabel(reward_section.content, text=label,
                          text_color=TEXT_DIM,
                          font=ctk.CTkFont(size=12)).grid(
                row=i, column=0, sticky="w")
            var = ctk.DoubleVar(value=default)
            setattr(self, var_name, var)
            lbl = ctk.CTkLabel(
                reward_section.content, text=f"{default:.1f}x",
                text_color=GOLD,
                font=ctk.CTkFont(size=12, weight="bold"))
            lbl.grid(row=i, column=2, padx=4)
            setattr(self, f"{var_name}_label", lbl)
            ctk.CTkSlider(
                reward_section.content, from_=0.1, to=5.0,
                variable=var, width=180,
                button_color=ACCENT, button_hover_color=ACCENT_HOVER,
                command=lambda v, l=lbl: l.configure(text=f"{v:.1f}x")
            ).grid(row=i, column=1, padx=4, pady=2)


        # --- Action Buttons ---
        btn_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        btn_frame.grid(row=row, column=0, sticky="ew", padx=12, pady=(8, 4))
        btn_frame.grid_columnconfigure(0, weight=1)
        row += 1

        self._build_btn = ctk.CTkButton(
            btn_frame, text="Randomize!", height=44,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._start_build)
        self._build_btn.grid(row=0, column=0, sticky="ew", padx=4, pady=2)

        side_btns = ctk.CTkFrame(btn_frame, fg_color="transparent")
        side_btns.grid(row=0, column=1, padx=4)
        ctk.CTkButton(
            side_btns, text="Save", width=50, height=44,
            fg_color="#2a2a4a", hover_color="#3a3a6a",
            command=self._save_config
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            side_btns, text="Load", width=50, height=44,
            fg_color="#2a2a4a", hover_color="#3a3a6a",
            command=self._load_config
        ).pack(side="left", padx=2)

        # --- Progress ---
        self._progress = ctk.CTkProgressBar(
            self._scroll, mode="indeterminate",
            progress_color=ACCENT, height=3)
        self._progress.grid(row=row, column=0, sticky="ew", padx=12, pady=2)
        self._progress.set(0)
        row += 1

        # --- Log ---
        log_section = SectionFrame(self._scroll, "Build Log", "LOG")
        log_section.grid(row=row, column=0, sticky="ew",
                         padx=12, pady=(4, 12))
        row += 1

        self._log_text = ctk.CTkTextbox(
            log_section.content, height=160,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0a0a1a", text_color="#a0d0a0",
            corner_radius=6)
        self._log_text.grid(row=0, column=0, columnspan=3,
                            sticky="ew", pady=4)
        self._log_text.insert("end",
                              "Ready. Select a ROM and click Randomize!\n")
        self._log_text.configure(state="disabled")

    # --- UI Callbacks ---

    def _on_enemy_stat_mode_change(self, mode: str):
        """Show/hide scale range based on mode selection."""
        if mode == "scale":
            self._scale_frame.grid()
        else:
            self._scale_frame.grid_remove()

    def _browse_rom(self):
        path = filedialog.askopenfilename(
            title="Select NDS ROM",
            filetypes=[("NDS ROM", "*.nds"), ("All files", "*.*")])
        if path:
            self._rom_var.set(path)

    def _random_seed(self):
        import random
        self._seed_var.set(str(random.randint(1, 999999)))

    def _apply_preset(self, name: str):
        self._preset_desc.configure(text=get_preset_description(name))
        if name == "Custom":
            return

        cfg = RandomizerConfig()
        apply_preset(cfg, name)

        # Update all GUI vars from the preset config
        enc_mode = (cfg.encounter_shuffle.mode
                    if cfg.encounter_shuffle.enabled else "vanilla")
        self._enc_shuffle_var.set(enc_mode)
        self._heroes_var.set(cfg.encounter_shuffle.include_heroes)

        stat_mode = (cfg.enemy_stats.mode
                     if cfg.enemy_stats.enabled else "vanilla")
        self._enemy_stat_var.set(stat_mode)
        self._on_enemy_stat_mode_change(stat_mode)
        self._stat_min_var.set(str(cfg.enemy_stats.min_scale))
        self._stat_max_var.set(str(cfg.enemy_stats.max_scale))

        self._boss_mode_var.set(
            cfg.boss_scaler.mode if cfg.boss_scaler.enabled else "vanilla")
        self._boss_hp_var.set(cfg.boss_scaler.hp_multiplier)
        self._boss_hp_label.configure(
            text=f"{cfg.boss_scaler.hp_multiplier:.1f}x")
        self._ki_mode_var.set(
            cfg.ki_blasts.mode if cfg.ki_blasts.enabled else "vanilla")
        self._shop_var.set(
            cfg.shop_items.mode if cfg.shop_items.enabled else "vanilla")
        self._drop_var.set(
            cfg.drop_shuffle.mode if cfg.drop_shuffle.enabled else "vanilla")
        self._base_stats_var.set(
            cfg.player_stats.mode if (cfg.player_stats.enabled
            and cfg.player_stats.shuffle_base) else "vanilla")
        self._growth_var.set(
            cfg.player_stats.mode if (cfg.player_stats.enabled
            and cfg.player_stats.shuffle_growth) else "vanilla")
        self._resist_var.set(
            cfg.chaos_resists.mode if cfg.chaos_resists.enabled
            else "vanilla")
        self._xp_var.set(cfg.xp_rewards.xp_multiplier)
        self._xp_var_label.configure(
            text=f"{cfg.xp_rewards.xp_multiplier:.1f}x")
        self._zeni_var.set(cfg.xp_rewards.zeni_multiplier)
        self._zeni_var_label.configure(
            text=f"{cfg.xp_rewards.zeni_multiplier:.1f}x")
        self._ap_var.set(cfg.xp_rewards.ap_multiplier)
        self._ap_var_label.configure(
            text=f"{cfg.xp_rewards.ap_multiplier:.1f}x")

    def _build_config(self) -> RandomizerConfig:
        """Build a RandomizerConfig from the current GUI state."""
        cfg = RandomizerConfig()
        cfg.rom_path = self._rom_var.get()
        try:
            cfg.seed = int(self._seed_var.get())
        except ValueError:
            cfg.seed = 42

        # Encounter Shuffle
        enc_mode = self._enc_shuffle_var.get()
        cfg.encounter_shuffle.enabled = (enc_mode != "vanilla")
        cfg.encounter_shuffle.mode = enc_mode
        cfg.encounter_shuffle.include_heroes = self._heroes_var.get()

        # Enemy Stats
        stat_mode = self._enemy_stat_var.get()
        cfg.enemy_stats.enabled = (stat_mode != "vanilla")
        cfg.enemy_stats.mode = stat_mode
        if stat_mode == "scale":
            try:
                cfg.enemy_stats.min_scale = float(
                    self._stat_min_var.get())
                cfg.enemy_stats.max_scale = float(
                    self._stat_max_var.get())
            except ValueError:
                pass

        # Boss Scaler
        boss_mode = self._boss_mode_var.get()
        cfg.boss_scaler.enabled = (boss_mode != "vanilla")
        cfg.boss_scaler.mode = boss_mode
        cfg.boss_scaler.hp_multiplier = self._boss_hp_var.get()

        # Ki Blasts
        ki_mode = self._ki_mode_var.get()
        cfg.ki_blasts.enabled = (ki_mode != "vanilla")
        cfg.ki_blasts.mode = ki_mode

        # Shop Items
        shop_mode = self._shop_var.get()
        cfg.shop_items.enabled = (shop_mode != "vanilla")
        cfg.shop_items.mode = shop_mode

        # Drop Shuffle
        drop_mode = self._drop_var.get()
        cfg.drop_shuffle.enabled = (drop_mode != "vanilla")
        cfg.drop_shuffle.mode = drop_mode

        # Player Stats (separate base + growth controls)
        base_mode = self._base_stats_var.get()
        growth_mode = self._growth_var.get()
        has_base = (base_mode != "vanilla")
        has_growth = (growth_mode != "vanilla")
        cfg.player_stats.enabled = (has_base or has_growth)
        # Use the non-vanilla mode; prefer base_mode if both differ
        if has_base:
            cfg.player_stats.mode = base_mode
        elif has_growth:
            cfg.player_stats.mode = growth_mode
        else:
            cfg.player_stats.mode = "vanilla"
        cfg.player_stats.shuffle_base = has_base
        cfg.player_stats.shuffle_growth = has_growth

        # Chaos Resistances
        resist_mode = self._resist_var.get()
        cfg.chaos_resists.enabled = (resist_mode != "vanilla")
        cfg.chaos_resists.mode = resist_mode

        # Rewards
        xp = self._xp_var.get()
        zeni = self._zeni_var.get()
        ap = self._ap_var.get()
        cfg.xp_rewards.enabled = (xp != 1.0 or zeni != 1.0 or ap != 1.0)
        cfg.xp_rewards.xp_multiplier = xp
        cfg.xp_rewards.zeni_multiplier = zeni
        cfg.xp_rewards.ap_multiplier = ap

        # Output path
        rom_dir = os.path.dirname(cfg.rom_path) or "."
        rom_base = os.path.splitext(os.path.basename(cfg.rom_path))[0]
        cfg.output_path = os.path.join(
            rom_dir, "output", f"{rom_base}_seed{cfg.seed}.nds")

        return cfg

    def _log(self, msg: str):
        """Thread-safe log append."""
        def _append():
            self._log_text.configure(state="normal")
            self._log_text.insert("end", msg + "\n")
            self._log_text.see("end")
            self._log_text.configure(state="disabled")
        self.after(0, _append)

    def _start_build(self):
        if self._building:
            return
        rom_path = self._rom_var.get()
        if not rom_path or not os.path.isfile(rom_path):
            messagebox.showerror(
                "Error", "Please select a valid ROM file.")
            return

        self._building = True
        self._build_btn.configure(state="disabled", text="Building...")
        self._progress.start()

        # Clear log
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

        # Run build in background thread
        thread = threading.Thread(target=self._run_build, daemon=True)
        thread.start()

    def _run_build(self):
        try:
            cfg = self._build_config()
            self._log(f"Seed: {cfg.seed}")
            self._log(f"ROM: {cfg.rom_path}")
            self._log(f"Output: {cfg.output_path}")
            self._log("")

            from randomizer.patcher.rom_builder import RomBuilder
            builder = RomBuilder(cfg)

            # Redirect builder logging to our GUI
            original_log = builder._log

            def gui_log(msg):
                original_log(msg)
                self._log(msg)

            builder._log = gui_log

            output = builder.build()

            self._log("")
            self._log(f"Done! ROM saved to: {output}")

            # Show success
            self.after(0, lambda: messagebox.showinfo(
                "Done!",
                f"Randomized ROM saved to:\n{output}"))

        except Exception as e:
            self._log(f"\nERROR: {e}")
            import traceback
            self._log(traceback.format_exc())
            self.after(0, lambda: messagebox.showerror(
                "Error", f"Build failed:\n{e}"))
        finally:
            self.after(0, self._build_done)

    def _build_done(self):
        self._building = False
        self._build_btn.configure(state="normal", text="Randomize!")
        self._progress.stop()
        self._progress.set(0)

    def _save_config(self):
        path = filedialog.asksaveasfilename(
            title="Save Config",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")])
        if path:
            cfg = self._build_config()
            cfg.save_json(path)
            self._log(f"Config saved: {path}")

    def _load_config(self):
        path = filedialog.askopenfilename(
            title="Load Config",
            filetypes=[("JSON", "*.json")])
        if path:
            try:
                import json
                with open(path) as f:
                    d = json.load(f)
                cfg = RandomizerConfig.from_dict(d)
                # Update GUI from loaded config
                self._rom_var.set(cfg.rom_path)
                self._seed_var.set(str(cfg.seed))
                enc_mode = (cfg.encounter_shuffle.mode
                            if cfg.encounter_shuffle.enabled
                            else "vanilla")
                self._enc_shuffle_var.set(enc_mode)
                self._heroes_var.set(
                    cfg.encounter_shuffle.include_heroes)
                stat_mode = (cfg.enemy_stats.mode
                             if cfg.enemy_stats.enabled
                             else "vanilla")
                self._enemy_stat_var.set(stat_mode)
                self._on_enemy_stat_mode_change(stat_mode)
                self._stat_min_var.set(str(cfg.enemy_stats.min_scale))
                self._stat_max_var.set(str(cfg.enemy_stats.max_scale))
                self._boss_mode_var.set(
                    cfg.boss_scaler.mode if cfg.boss_scaler.enabled
                    else "vanilla")
                self._boss_hp_var.set(cfg.boss_scaler.hp_multiplier)
                self._boss_hp_label.configure(
                    text=f"{cfg.boss_scaler.hp_multiplier:.1f}x")
                self._ki_mode_var.set(
                    cfg.ki_blasts.mode if cfg.ki_blasts.enabled
                    else "vanilla")
                self._shop_var.set(
                    cfg.shop_items.mode if cfg.shop_items.enabled
                    else "vanilla")
                self._drop_var.set(
                    cfg.drop_shuffle.mode if cfg.drop_shuffle.enabled
                    else "vanilla")
                self._base_stats_var.set(
                    cfg.player_stats.mode
                    if (cfg.player_stats.enabled
                        and cfg.player_stats.shuffle_base)
                    else "vanilla")
                self._growth_var.set(
                    cfg.player_stats.mode
                    if (cfg.player_stats.enabled
                        and cfg.player_stats.shuffle_growth)
                    else "vanilla")
                self._resist_var.set(
                    cfg.chaos_resists.mode
                    if cfg.chaos_resists.enabled
                    else "vanilla")
                self._xp_var.set(cfg.xp_rewards.xp_multiplier)
                self._zeni_var.set(cfg.xp_rewards.zeni_multiplier)
                self._ap_var.set(cfg.xp_rewards.ap_multiplier)

                self._preset_var.set("Custom")
                self._log(f"Config loaded: {path}")
            except Exception as e:
                messagebox.showerror(
                    "Error", f"Failed to load config:\n{e}")


def main():
    app = RandomizerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
