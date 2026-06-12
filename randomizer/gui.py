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
BG_CARD = "#16162a"
BG_CARD_HOVER = "#1e1e3a"
ACCENT = "#e94560"
ACCENT_HOVER = "#ff6b81"
TEXT_DIM = "#9ca3bf"
TEXT_DESC = "#707896"
GOLD = "#ffca28"
SUCCESS = "#00d26a"
DROPDOWN_BG = "#252547"

# Mode descriptions for dynamic help text under each dropdown
MODE_DESC = {
    # Encounter Shuffle
    "enc__vanilla": "No changes — enemies appear in their original locations.",
    "enc__shuffle_tiered": "Enemies swap within similar level ranges. Bosses get skin only.",
    "enc__shuffle_wild": "Any enemy can appear anywhere — full chaos! Bosses get skin only.",
    # Enemy Stats
    "stat__vanilla": "No changes — enemy stats stay at their original values.",
    "stat__shuffle": "Swap stats between enemies. A weak enemy might get strong stats and vice versa.",
    "stat__scale": "Multiply all stats by a random value within the range below.",
    "stat__chaos": "Completely randomize all enemy stats. Unpredictable difficulty!",
    # Boss Scaler
    "boss__vanilla": "No changes — bosses keep their original stats.",
    "boss__scale": "Scale boss HP and stats by the multiplier below.",
    "boss__nightmare": "Bosses get massively boosted stats. Prepare to grind!",
    # Skills
    "ki__vanilla": "No changes — skill power and cost stay original.",
    "ki__rebalance": "Slightly randomize power (±30%) and MP cost (±30%) per skill. "
                     "Shuffle AP unlock order. Feels fresh but fair.",
    "ki__chaos": "Extreme randomization (±60%). Effect types get shuffled between "
                 "skills — Kamehameha might suddenly stun!",
    # Shop
    "shop__vanilla": "No changes — shop prices stay original.",
    "shop__shuffle_prices": "Shuffle prices between items. Cheap items might become expensive.",
    "shop__random_prices": "Randomize all shop prices within reasonable bounds.",
    "shop__chaos": "Fully random prices — anything from 1 Zeni to max!",
    # Drops
    "drop__vanilla": "No changes — enemy drops stay original.",
    "drop__shuffle": "Shuffle drop tables between enemies of similar level.",
    "drop__random": "Fully randomize which items enemies drop.",
    "drop__generous": "Increase drop rates so items drop more frequently.",
    # Player Base Stats
    "pbase__vanilla": "No changes — starting stats stay original.",
    "pbase__shuffle": "Shuffle base stats between characters. Yamcha might start stronger than Goku!",
    "pbase__scale": "Randomly scale each character's starting stats (±25%).",
    # Player Growth
    "pgrow__vanilla": "No changes — level-up stat gains stay original.",
    "pgrow__shuffle": "Shuffle growth curves between characters.",
    "pgrow__scale": "Randomly scale stat gains per level-up (±25%).",
    # Enemy Resistances
    "res__vanilla": "No changes — enemy resistances stay original.",
    "res__shuffle": "Shuffle resistance profiles between enemies.",
    "res__random": "Randomize all enemy resistance values.",
    "res__inverse": "Invert resistances — resistant enemies become weak and vice versa!",
}


class SectionFrame(ctk.CTkFrame):
    """Module section with title, icon, and description."""

    def __init__(self, master, title: str, icon: str = "",
                 description: str = "", **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=14, border_width=1,
                         border_color="#252550", **kwargs)
        self.grid_columnconfigure(1, weight=1)
        self._title = title

        # Header row
        self._header = ctk.CTkFrame(self, fg_color="transparent")
        self._header.grid(row=0, column=0, columnspan=3, sticky="ew",
                          padx=8, pady=(6, 0))
        self._header.grid_columnconfigure(1, weight=1)

        self._icon_label = ctk.CTkLabel(
            self._header, text=icon, font=("Segoe UI Emoji", 18))
        self._icon_label.grid(row=0, column=0, padx=(0, 8))

        self._title_label = ctk.CTkLabel(
            self._header, text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#eaeaff")
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
        self.title("DBZ: Attack of the Saiyans — Randomizer v1.1.0")
        self.geometry("640x920")
        self.minsize(600, 700)
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
        title_frame.grid(row=row, column=0, sticky="ew", padx=16, pady=(14, 6))
        title_row = ctk.CTkFrame(title_frame, fg_color="transparent")
        title_row.pack(anchor="w")
        ctk.CTkLabel(
            title_row, text="DBZ: Attack of the Saiyans",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=GOLD
        ).pack(side="left")
        ctk.CTkLabel(
            title_row, text="  Randomizer",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#eaeaff"
        ).pack(side="left")
        ctk.CTkLabel(
            title_frame, text="v1.1.0  ·  by Donler",
            font=ctk.CTkFont(size=11), text_color=TEXT_DIM
        ).pack(anchor="w", pady=(2, 0))
        row += 1

        # --- ROM & Seed ---
        rom_section = SectionFrame(
            self._scroll, "ROM & Seed", "📀",
            "Choose your ROM, set a seed for reproducible results, "
            "or pick a preset to get started quickly.")
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
        seed_frame = ctk.CTkFrame(
            rom_section.content, fg_color="transparent")
        seed_frame.grid(row=1, column=1, columnspan=2, sticky="w", padx=4, pady=2)
        ctk.CTkEntry(
            seed_frame, textvariable=self._seed_var, width=150
        ).pack(side="left")
        ctk.CTkButton(
            seed_frame, text="Random", width=70,
            command=self._random_seed,
            fg_color=DROPDOWN_BG, hover_color="#3a3a6a"
        ).pack(side="left", padx=(4, 0))

        # Preset
        ctk.CTkLabel(rom_section.content, text="Preset:", text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=2, column=0, sticky="w", pady=2)
        self._preset_var = ctk.StringVar(value="Custom")
        preset_menu = ctk.CTkOptionMenu(
            rom_section.content, variable=self._preset_var,
            values=get_preset_names(), command=self._apply_preset,
            width=200, fg_color=DROPDOWN_BG,
            button_color=ACCENT, button_hover_color=ACCENT_HOVER)
        preset_menu.grid(row=2, column=1, sticky="w", padx=4, pady=2)
        self._preset_desc = ctk.CTkLabel(
            rom_section.content, text="", text_color=TEXT_DIM,
            font=ctk.CTkFont(size=11, slant="italic"))
        self._preset_desc.grid(row=3, column=0, columnspan=3,
                               sticky="w", pady=(0, 2))

        # --- Encounter Shuffle ---
        enc_section = SectionFrame(
            self._scroll, "Encounters", "⚔️",
            "Shuffle which enemies you encounter. "
            "Tiered keeps them balanced by level. "
            "Wild throws anything at you!")
        enc_section.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1

        ctk.CTkLabel(enc_section.content, text="Mode:", text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, sticky="w")
        self._enc_shuffle_var = ctk.StringVar(value="vanilla")
        ctk.CTkOptionMenu(
            enc_section.content, variable=self._enc_shuffle_var,
            values=["vanilla", "shuffle_tiered", "shuffle_wild"],
            width=180, fg_color=DROPDOWN_BG,
            command=self._on_enc_mode_change
        ).grid(row=0, column=1, sticky="w", padx=4, pady=2)
        self._enc_desc = self._make_mode_label(enc_section.content, "enc", "vanilla")
        self._enc_desc.grid(row=0, column=2, sticky="w", padx=(8, 0))

        # Options frame — only visible when not vanilla
        self._enc_options_frame = ctk.CTkFrame(
            enc_section.content, fg_color="transparent")
        self._enc_options_frame.grid(
            row=1, column=0, columnspan=3, sticky="w")
        self._enc_options_frame.grid_remove()  # hidden by default

        self._heroes_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self._enc_options_frame,
            text="Include Bosses  (Raditz, Vegeta, Broly...)",
            variable=self._heroes_var, text_color="#e0e0e0",
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._on_heroes_toggle
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=2)

        self._heroes_warning = ctk.CTkLabel(
            self._enc_options_frame,
            text="⚠ May cause crashes — boss sprites in random "
                 "encounters are experimental!",
            text_color="#ff4444",
            font=ctk.CTkFont(size=11, weight="bold"),
            wraplength=400)
        self._heroes_warning.grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 2))
        self._heroes_warning.grid_remove()  # hidden by default

        self._scale_area_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self._enc_options_frame,
            text="Scale to Area (match enemy stats to area level)",
            variable=self._scale_area_var, text_color="#e0e0e0",
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._on_scale_area_toggle
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=2)

        self._scale_warning = ctk.CTkLabel(
            self._enc_options_frame,
            text="!! WARNING: Enemies keep original stats. "
                 "Late-game enemies in early areas will be nearly "
                 "impossible to beat!",
            text_color="#ff4444",
            font=ctk.CTkFont(size=11, weight="bold"),
            wraplength=400)
        self._scale_warning.grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(0, 2))
        self._scale_warning.grid_remove()  # hidden by default

        # --- Force Enemy (Debug/Fun) ---
        self._force_frame = ctk.CTkFrame(enc_section.content, fg_color="transparent")
        self._force_frame.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 2))
        self._force_frame.grid_remove()  # hidden until non-vanilla

        ctk.CTkLabel(self._force_frame, text="🎯 Force Enemy:",
                     text_color=GOLD,
                     font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, sticky="w")

        self._force_enemy_var = ctk.StringVar(value="Off")
        # All enemies sorted by name (name → file mapping)
        self._force_enemy_map = self._build_enemy_list()
        force_names = ["Off"] + sorted(self._force_enemy_map.keys())
        ctk.CTkOptionMenu(
            self._force_frame, variable=self._force_enemy_var,
            values=force_names,
            width=220, fg_color=DROPDOWN_BG,
        ).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        ctk.CTkLabel(self._force_frame,
                     text="All enemies → this sprite (bosses: skin only)",
                     text_color=TEXT_DESC,
                     font=ctk.CTkFont(size=11, slant="italic")).grid(
            row=0, column=2, sticky="w", padx=(8, 0))

        # --- Enemy Stats ---
        stat_section = SectionFrame(
            self._scroll, "Enemy Stats", "📊",
            "Change how strong enemies are. "
            "Scale adjusts stats by a multiplier. "
            "Shuffle swaps stats between enemies.")
        stat_section.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1

        ctk.CTkLabel(stat_section.content, text="Mode:", text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, sticky="w")
        self._enemy_stat_var = ctk.StringVar(value="scale")
        ctk.CTkOptionMenu(
            stat_section.content, variable=self._enemy_stat_var,
            values=["vanilla", "shuffle", "scale", "chaos"],
            width=180, fg_color=DROPDOWN_BG,
            command=self._on_enemy_stat_mode_change
        ).grid(row=0, column=1, sticky="w", padx=4, pady=2)
        self._stat_desc = self._make_mode_label(stat_section.content, "stat", "scale")
        self._stat_desc.grid(row=0, column=2, sticky="w", padx=(8, 0))

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

        ctk.CTkLabel(stat_section.content, text="Resists:",
                      text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=2, column=0, sticky="w")
        self._resist_var = ctk.StringVar(value="vanilla")
        ctk.CTkOptionMenu(
            stat_section.content, variable=self._resist_var,
            values=["vanilla", "shuffle", "random", "inverse"],
            width=180, fg_color=DROPDOWN_BG,
            command=lambda m: self._update_mode_desc(self._res_desc, "res", m)
        ).grid(row=2, column=1, sticky="w", padx=4, pady=2)
        self._res_desc = self._make_mode_label(stat_section.content, "res", "vanilla")
        self._res_desc.grid(row=2, column=2, sticky="w", padx=(8, 0))

        # --- Boss Scaler ---
        boss_section = SectionFrame(
            self._scroll, "Boss Difficulty", "👑",
            "Make story bosses tougher or easier. "
            "Adjust their HP and combat stats independently.")
        boss_section.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1

        ctk.CTkLabel(boss_section.content, text="Mode:", text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, sticky="w")
        self._boss_mode_var = ctk.StringVar(value="vanilla")
        ctk.CTkOptionMenu(
            boss_section.content, variable=self._boss_mode_var,
            values=["vanilla", "scale", "nightmare"],
            width=180, fg_color=DROPDOWN_BG,
            command=self._on_boss_mode_change
        ).grid(row=0, column=1, sticky="w", padx=4, pady=2)
        self._boss_desc = self._make_mode_label(boss_section.content, "boss", "vanilla")
        self._boss_desc.grid(row=0, column=2, sticky="w", padx=(8, 0))

        self._boss_hp_frame = ctk.CTkFrame(
            boss_section.content, fg_color="transparent")
        self._boss_hp_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        self._boss_hp_frame.grid_remove()  # hidden by default

        ctk.CTkLabel(self._boss_hp_frame, text="HP Mult:",
                      text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).pack(side="left")
        self._boss_hp_var = ctk.DoubleVar(value=1.5)
        self._boss_hp_label = ctk.CTkLabel(
            self._boss_hp_frame, text="1.5x", text_color=GOLD,
            font=ctk.CTkFont(size=12, weight="bold"))
        self._boss_hp_label.pack(side="right", padx=4)
        ctk.CTkSlider(
            self._boss_hp_frame, from_=0.5, to=5.0,
            variable=self._boss_hp_var, width=180,
            button_color=ACCENT, button_hover_color=ACCENT_HOVER,
            command=lambda v: self._boss_hp_label.configure(
                text=f"{v:.1f}x")
        ).pack(side="left", padx=4, pady=2)

        # --- Skills ---
        ki_section = SectionFrame(
            self._scroll, "Skills", "✨",
            "Shake up Ki attacks and special abilities. "
            "Rebalance keeps things fair. "
            "Chaos makes everything unpredictable!")
        ki_section.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1

        ctk.CTkLabel(ki_section.content, text="Mode:", text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, sticky="w")
        self._ki_mode_var = ctk.StringVar(value="vanilla")
        ctk.CTkOptionMenu(
            ki_section.content, variable=self._ki_mode_var,
            values=["vanilla", "rebalance", "chaos"],
            width=180, fg_color=DROPDOWN_BG,
            command=lambda m: self._update_mode_desc(self._ki_desc, "ki", m)
        ).grid(row=0, column=1, sticky="w", padx=4, pady=2)
        self._ki_desc = self._make_mode_label(ki_section.content, "ki", "vanilla")
        self._ki_desc.grid(row=0, column=2, sticky="w", padx=(8, 0))

        # --- Items & Drops ---
        item_section = SectionFrame(
            self._scroll, "Items & Drops", "🎪",
            "Randomize what shops sell and what enemies drop. "
            "Generous mode makes items rain!")
        item_section.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1

        ctk.CTkLabel(item_section.content, text="Shop:", text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, sticky="w")
        self._shop_var = ctk.StringVar(value="vanilla")
        ctk.CTkOptionMenu(
            item_section.content, variable=self._shop_var,
            values=["vanilla", "shuffle_prices", "random_prices", "chaos"],
            width=180, fg_color=DROPDOWN_BG,
            command=lambda m: self._update_mode_desc(self._shop_desc, "shop", m)
        ).grid(row=0, column=1, sticky="w", padx=4, pady=2)
        self._shop_desc = self._make_mode_label(item_section.content, "shop", "vanilla")
        self._shop_desc.grid(row=0, column=2, sticky="w", padx=(8, 0))

        ctk.CTkLabel(item_section.content, text="Drops:", text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, sticky="w")
        self._drop_var = ctk.StringVar(value="vanilla")
        ctk.CTkOptionMenu(
            item_section.content, variable=self._drop_var,
            values=["vanilla", "shuffle", "random", "generous"],
            width=180, fg_color=DROPDOWN_BG,
            command=lambda m: self._update_mode_desc(self._drop_desc, "drop", m)
        ).grid(row=1, column=1, sticky="w", padx=4, pady=2)
        self._drop_desc = self._make_mode_label(item_section.content, "drop", "vanilla")
        self._drop_desc.grid(row=1, column=2, sticky="w", padx=(8, 0))

        # --- Player Stats ---
        player_section = SectionFrame(
            self._scroll, "Player Stats", "🧬",
            "Randomize starting stats and how your characters grow. "
            "Shuffle can make Yamcha stronger than Goku!")
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
            width=180, fg_color=DROPDOWN_BG,
            command=lambda m: self._update_mode_desc(self._pbase_desc, "pbase", m)
        ).grid(row=0, column=1, sticky="w", padx=4, pady=2)
        self._pbase_desc = self._make_mode_label(player_section.content, "pbase", "vanilla")
        self._pbase_desc.grid(row=0, column=2, sticky="w", padx=(8, 0))

        ctk.CTkLabel(player_section.content, text="Growth:",
                      text_color=TEXT_DIM,
                      font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, sticky="w")
        self._growth_var = ctk.StringVar(value="vanilla")
        ctk.CTkOptionMenu(
            player_section.content, variable=self._growth_var,
            values=["vanilla", "shuffle", "scale"],
            width=180, fg_color=DROPDOWN_BG,
            command=lambda m: self._update_mode_desc(self._pgrow_desc, "pgrow", m)
        ).grid(row=1, column=1, sticky="w", padx=4, pady=2)
        self._pgrow_desc = self._make_mode_label(player_section.content, "pgrow", "vanilla")
        self._pgrow_desc.grid(row=1, column=2, sticky="w", padx=(8, 0))



        # --- Rewards ---
        reward_section = SectionFrame(
            self._scroll, "Rewards", "🏆",
            "Adjust how much XP, Zeni, and AP you earn. "
            "Crank it up for a chill run, or lower it for a challenge.")
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

        # --- Auto-switch preset to "Custom" on manual change ---
        self._applying_preset = False  # guard flag

        # All setting vars that should trigger "Custom" on change
        traced_vars = [
            self._enc_shuffle_var, self._heroes_var, self._scale_area_var,
            self._enemy_stat_var, self._stat_min_var, self._stat_max_var,
            self._boss_mode_var, self._boss_hp_var,
            self._ki_mode_var,
            self._shop_var, self._drop_var,
            self._base_stats_var, self._growth_var, self._resist_var,
            self._xp_var, self._zeni_var, self._ap_var,
        ]
        for v in traced_vars:
            v.trace_add("write", self._mark_custom)

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
            fg_color=DROPDOWN_BG, hover_color="#3a3a6a",
            command=self._save_config
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            side_btns, text="Load", width=50, height=44,
            fg_color=DROPDOWN_BG, hover_color="#3a3a6a",
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
        log_section = SectionFrame(self._scroll, "Build Log", "📝")
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

    @staticmethod
    def _make_mode_label(parent, prefix: str, mode: str) -> ctk.CTkLabel:
        """Create a small italic description label for a mode dropdown."""
        text = MODE_DESC.get(f"{prefix}__{mode}", "")
        lbl = ctk.CTkLabel(
            parent, text=text, text_color=TEXT_DESC,
            font=ctk.CTkFont(size=10, slant="italic"),
            wraplength=220, anchor="w", justify="left")
        return lbl

    @staticmethod
    def _build_enemy_list() -> dict:
        """Build name → file mapping for all enemies/bosses.

        Names sourced from BDAT character_name table (US locale).
        Returns dict like {"Broly (Lv95)" → "ene223_01", ...}
        """
        # (name_id, display_name, file, level) — from BDAT dumps
        _ENEMIES = [
            (9, "Saibaman", "ene003_01", 1),
            (14, "Pirate Robot", "ene006_01", 1),
            (18, "Red Ribbon Spy", "ene003_01", 1),
            (20, "Vodka", "ene025_01", 1),
            (24, "RR Survivor", "ene005_01", 3),
            (30, "RR Ex-Staff Sgt", "ene007_01", 3),
            (32, "Female Bandit", "ene008_01", 24),
            (35, "Bandit", "ene010_01", 8),
            (38, "Thief Fox", "ene011_01", 8),
            (41, "Sniper", "ene012_01", 43),
            (44, "Fugitive", "ene013_01", 21),
            (47, "Piratess", "ene014_01", 35),
            (50, "Pirate", "ene015_01", 35),
            (53, "Rabbit Private", "ene016_01", 8),
            (56, "Rabbit Private 2", "ene016_02", 8),
            (60, "Female Pupil", "ene017_01", 1),
            (63, "Expelled Pupil", "ene020_01", 8),
            (66, "Rowdy Fighter", "ene021_01", 8),
            (68, "Princess' Servant", "ene022_01", 21),
            (71, "Raider", "ene023_01", 3),
            (77, "Meadow Wizard", "ene026_01", 18),
            (80, "Distrustful Man", "ene027_01", 18),
            (83, "Winged Dragon", "ene029_01", 30),
            (86, "Dinosaur", "ene030_01", 43),
            (89, "Giant Snake", "ene031_01", 3),
            (92, "Lantern Ghost", "ene032_01", 3),
            (95, "Ghost Pot", "ene033_01", 8),
            (98, "Demon Denizen", "ene034_02", 8),
            (102, "Gogyo Majin", "ene035_01", 1),
            (104, "Ostrich Chicken", "ene036_01", 18),
            (107, "Firebird", "ene037_01", 48),
            (110, "Tiger", "ene038_01", 8),
            (113, "Wolf", "ene039_01", 8),
            (116, "Stray Dog", "ene040_01", 18),
            (119, "Wild Boar", "ene041_01", 18),
            (122, "Hungry Bear", "ene042_01", 18),
            (125, "Dangerous Panda", "ene042_02", 8),
            (128, "Giant Fish", "ene043_01", 28),
            (131, "Wolfman", "ene044_01", 8),
            (134, "Bloodsucker", "ene045_01", 40),
            (137, "Mummy Man", "ene046_01", 40),
            (140, "Giant Bat", "ene047_01", 8),
            (143, "Big Club", "ene051_01", 35),
            (146, "Fishman", "ene052_01", 28),
            (149, "Experiment #3", "ene053_01", 45),
            (152, "Sandman", "ene055_01", 30),
            (155, "Forest Guard", "ene057_01", 24),
            (158, "Tumble Bug", "ene058_01", 3),
            (161, "Dark Giras", "ene059_02", 48),
            (164, "Roundworm", "ene060_01", 18),
            (167, "Dark Firefly", "ene060_02", 1),
            (170, "Roundworm Larva", "ene061_01", 18),
            (173, "Firefly Larva", "ene061_02", 1),
            (176, "Helper Robot", "ene062_01", 21),
            (10, "J. Sai", "ene001_01", 48),
            (15, "Skull Robot", "ene002_01", 35),
            (21, "RR Tundra Robot", "ene025_01", 1),
            (23, "RR Deserter", "ene004_01", 35),
            (27, "RR High Soldier", "ene006_01", 1),
            (33, "Snow Bandit Girl", "ene008_01", 24),
            (36, "Snow Bandit", "ene010_01", 8),
            (39, "Veteran Fox", "ene011_01", 8),
            (42, "Refugee", "ene012_01", 43),
            (45, "Elite Assassin", "ene013_01", 21),
            (48, "Female Desert Bandit", "ene014_01", 35),
            (51, "Desert Bandit", "ene015_01", 35),
            (181, "Z-Saibaman", "ene001_02", 1),
            # Boss entries
            (182, "Jackie Chun", "ene113_01", 5),
            (184, "Monster Carrot", "ene100_01", 8),
            (186, "Chiaotzu", "ene120_01", 8),
            (187, "Piccolo (Boss)", "ene101_01", 8),
            (188, "Piccolo Jr.", "ene214_01", 10),
            (189, "Annin", "ene215_01", 10),
            (190, "Shu Machine", "ene122_01", 10),
            (191, "Mai Machine", "ene107_01", 18),
            (192, "Furnace Flame", "ene106_01", 18),
            (193, "???", "ene119_01", 20),
            (195, "Raditz", "ene220_01", 20),
            (197, "Dongiras", "ene103_01", 8),
            (198, "Spring Majin", "ene116_01", 25),
            (200, "Midgiras", "ene111_01", 32),
            (201, "Goz", "ene132_01", 22),
            (202, "Princess Snake", "ene125_01", 22),
            (206, "Eighter", "ene130_01", 35),
            (207, "General White", "ene117_01", 35),
            (208, "Giant Octopus", "ene118_01", 35),
            (209, "RR Power Robot", "ene109_01", 35),
            (210, "Ladies", "ene131_01", 35),
            (211, "Gentlemen", "ene114_01", 40),
            (214, "Pilaf Machine", "ene200_01", 45),
            (215, "Pilaf Fusion Mech", "ene105_01", 40),
            (216, "Excavated Robot v2", "ene108_01", 45),
            (217, "TPP-EX", "ene112_01", 45),
            (218, "Turles", "ene129_01", 45),
            (219, "Nappa", "ene221_01", 50),
            (221, "Vegeta", "ene222_01", 70),
            (222, "Oozaru Vegeta", "ene222_02", 70),
            (224, "Broly", "ene223_01", 95),
        ]
        result = {}
        for nid, name, file, lv in _ENEMIES:
            key = f"{name} (Lv{lv})"
            # Avoid duplicates — append file suffix if needed
            if key in result:
                key = f"{name} [{file}] (Lv{lv})"
            result[key] = file
        return result

    @staticmethod
    def _update_mode_desc(label: ctk.CTkLabel, prefix: str, mode: str):
        """Update a mode description label."""
        text = MODE_DESC.get(f"{prefix}__{mode}", "")
        label.configure(text=text)

    def _on_enc_mode_change(self, mode: str):
        """Show/hide encounter options based on mode selection."""
        self._update_mode_desc(self._enc_desc, "enc", mode)
        if mode == "vanilla":
            self._enc_options_frame.grid_remove()
            self._force_frame.grid_remove()
            self._heroes_var.set(False)
            self._heroes_warning.grid_remove()
            self._scale_area_var.set(True)
            self._scale_warning.grid_remove()
            self._force_enemy_var.set("Off")
        else:
            self._enc_options_frame.grid()
            self._force_frame.grid()

    def _on_enemy_stat_mode_change(self, mode: str):
        """Show/hide scale range based on mode selection."""
        self._update_mode_desc(self._stat_desc, "stat", mode)
        if mode == "scale":
            self._scale_frame.grid()
        else:
            self._scale_frame.grid_remove()

    def _on_boss_mode_change(self, mode: str):
        """Show/hide boss HP slider based on mode selection."""
        self._update_mode_desc(self._boss_desc, "boss", mode)
        if mode == "scale":
            self._boss_hp_frame.grid()
        else:
            self._boss_hp_frame.grid_remove()
            if mode == "vanilla":
                self._boss_hp_var.set(1.5)

    def _on_heroes_toggle(self):
        """Show/hide crash warning when Include Bosses is toggled."""
        if self._heroes_var.get():
            self._heroes_warning.grid()
        else:
            self._heroes_warning.grid_remove()

    def _on_scale_area_toggle(self):
        """Show/hide warning when Scale to Area is unchecked."""
        if self._scale_area_var.get():
            self._scale_warning.grid_remove()
        else:
            self._scale_warning.grid()

    def _browse_rom(self):
        path = filedialog.askopenfilename(
            title="Select NDS ROM",
            filetypes=[("NDS ROM", "*.nds"), ("All files", "*.*")])
        if path:
            self._rom_var.set(path)

    def _random_seed(self):
        import random
        self._seed_var.set(str(random.randint(1, 999999)))

    def _mark_custom(self, *_args):
        """Auto-switch preset to 'Custom' when user changes a setting."""
        if not self._applying_preset:
            self._preset_var.set("Custom")
            self._preset_desc.configure(text=get_preset_description("Custom"))

    def _end_preset_apply(self):
        """Re-enable _mark_custom after preset was fully applied."""
        self._applying_preset = False

    def _apply_preset(self, name: str):
        self._preset_desc.configure(text=get_preset_description(name))
        if name == "Custom":
            return

        self._applying_preset = True  # suppress _mark_custom during preset

        cfg = RandomizerConfig()
        apply_preset(cfg, name)

        # Update all GUI vars from the preset config
        enc_mode = (cfg.encounter_shuffle.mode
                    if cfg.encounter_shuffle.enabled else "vanilla")
        self._enc_shuffle_var.set(enc_mode)
        self._on_enc_mode_change(enc_mode)
        self._heroes_var.set(cfg.encounter_shuffle.include_heroes)
        self._on_heroes_toggle()
        self._scale_area_var.set(cfg.encounter_shuffle.scale_to_area)
        self._on_scale_area_toggle()

        stat_mode = (cfg.enemy_stats.mode
                     if cfg.enemy_stats.enabled else "vanilla")
        self._enemy_stat_var.set(stat_mode)
        self._on_enemy_stat_mode_change(stat_mode)
        self._stat_min_var.set(str(cfg.enemy_stats.min_scale))
        self._stat_max_var.set(str(cfg.enemy_stats.max_scale))

        boss_mode = (cfg.boss_scaler.mode
                     if cfg.boss_scaler.enabled else "vanilla")
        self._boss_mode_var.set(boss_mode)
        self._on_boss_mode_change(boss_mode)
        self._boss_hp_var.set(cfg.boss_scaler.hp_multiplier)
        self._boss_hp_label.configure(
            text=f"{cfg.boss_scaler.hp_multiplier:.1f}x")
        ki_mode = cfg.ki_blasts.mode if cfg.ki_blasts.enabled else "vanilla"
        self._ki_mode_var.set(ki_mode)
        self._update_mode_desc(self._ki_desc, "ki", ki_mode)
        shop_mode = cfg.shop_items.mode if cfg.shop_items.enabled else "vanilla"
        self._shop_var.set(shop_mode)
        self._update_mode_desc(self._shop_desc, "shop", shop_mode)
        drop_mode = cfg.drop_shuffle.mode if cfg.drop_shuffle.enabled else "vanilla"
        self._drop_var.set(drop_mode)
        self._update_mode_desc(self._drop_desc, "drop", drop_mode)
        pbase_mode = (cfg.player_stats.mode if (cfg.player_stats.enabled
            and cfg.player_stats.shuffle_base) else "vanilla")
        self._base_stats_var.set(pbase_mode)
        self._update_mode_desc(self._pbase_desc, "pbase", pbase_mode)
        pgrow_mode = (cfg.player_stats.mode if (cfg.player_stats.enabled
            and cfg.player_stats.shuffle_growth) else "vanilla")
        self._growth_var.set(pgrow_mode)
        self._update_mode_desc(self._pgrow_desc, "pgrow", pgrow_mode)
        res_mode = (cfg.chaos_resists.mode if cfg.chaos_resists.enabled
            else "vanilla")
        self._resist_var.set(res_mode)
        self._update_mode_desc(self._res_desc, "res", res_mode)
        self._xp_var.set(cfg.xp_rewards.xp_multiplier)
        self._xp_var_label.configure(
            text=f"{cfg.xp_rewards.xp_multiplier:.1f}x")
        self._zeni_var.set(cfg.xp_rewards.zeni_multiplier)
        self._zeni_var_label.configure(
            text=f"{cfg.xp_rewards.zeni_multiplier:.1f}x")
        self._ap_var.set(cfg.xp_rewards.ap_multiplier)
        self._ap_var_label.configure(
            text=f"{cfg.xp_rewards.ap_multiplier:.1f}x")

        # Delay guard reset so all pending trace callbacks fire first
        self.after(50, self._end_preset_apply)

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
        cfg.encounter_shuffle.scale_to_area = self._scale_area_var.get()
        force_sel = self._force_enemy_var.get()
        if force_sel != "Off" and force_sel in self._force_enemy_map:
            cfg.encounter_shuffle.force_enemy = self._force_enemy_map[force_sel]
            cfg.encounter_shuffle.enabled = True  # auto-enable
        else:
            cfg.encounter_shuffle.force_enemy = ""

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
                self._on_enc_mode_change(enc_mode)
                self._heroes_var.set(
                    cfg.encounter_shuffle.include_heroes)
                self._on_heroes_toggle()
                self._scale_area_var.set(
                    cfg.encounter_shuffle.scale_to_area)
                self._on_scale_area_toggle()
                stat_mode = (cfg.enemy_stats.mode
                             if cfg.enemy_stats.enabled
                             else "vanilla")
                self._enemy_stat_var.set(stat_mode)
                self._on_enemy_stat_mode_change(stat_mode)
                self._stat_min_var.set(str(cfg.enemy_stats.min_scale))
                self._stat_max_var.set(str(cfg.enemy_stats.max_scale))
                boss_mode = (cfg.boss_scaler.mode
                    if cfg.boss_scaler.enabled else "vanilla")
                self._boss_mode_var.set(boss_mode)
                self._on_boss_mode_change(boss_mode)
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
