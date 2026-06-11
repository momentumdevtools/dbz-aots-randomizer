#!/usr/bin/env python3
"""
base.py — Abstract Base Class for all Randomizers
===================================================
Every randomizer in the system inherits from BaseRandomizer.
This guarantees:
  - Deterministic RNG (GameRNG) for reproducibility
  - Consistent config interface
  - Human-readable change log for every run
"""

from abc import ABC, abstractmethod
from randomizer.utils.rng import GameRNG
from randomizer.rom_io.bdat_reader import BdatFile
from randomizer.rom_io.bdat_writer import BdatWriter


class BaseRandomizer(ABC):
    """
    Abstract base for all BDAT table randomizers.

    Subclasses MUST implement randomize() which reads from a BdatFile
    and applies mutations via BdatWriter (in-place binary patching).

    Attributes:
        rng:    Deterministic GameRNG instance (seeded, reproducible)
        config: Dict of mode-specific settings (mode, scale factors, etc.)
        log:    List of human-readable strings documenting every change
    """

    def __init__(self, rng: GameRNG, config: dict):
        self.rng = rng
        self.config = config
        self.log: list[str] = []  # human-readable log of changes

    @abstractmethod
    def randomize(self, bdat: BdatFile, writer: BdatWriter) -> None:
        """
        Apply randomization to BDAT data.

        Args:
            bdat:   Parsed BdatFile (read-only reference)
            writer: BdatWriter for in-place binary patching
        """
        pass

    def get_log(self) -> list[str]:
        """Return the list of human-readable change descriptions."""
        return self.log

    def _log(self, msg: str) -> None:
        """Append a message to the change log."""
        self.log.append(msg)
