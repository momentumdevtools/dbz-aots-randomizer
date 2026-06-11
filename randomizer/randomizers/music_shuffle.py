#!/usr/bin/env python3
"""
music_shuffle.py — Music / Sound Shuffle Randomizer
=====================================================
Randomizes music (SSEQ) track assignments inside the game's SDAT archive.

The NDS ROM stores all audio in a single SDAT (Sound Data) archive.
Inside it, SSEQ entries are indexed sequences that correspond to
individual BGM tracks and sound effects.

Modes:
  'vanilla'  — No changes
  'shuffle'  — Shuffle all BGM tracks among themselves
  'chaos'    — Shuffle BGM tracks AND sound-effect sequences

Approach:
  1. Locate the .sdat file in the ROM filesystem
  2. Parse it with ndspy.soundArchive.SDAT
  3. Collect SSEQ entries, filter by type, shuffle the raw data blobs
  4. Write the modified SDAT back into the ROM
"""

from randomizer.randomizers.base import BaseRandomizer
from randomizer.utils.rng import GameRNG

# ndspy imports — SDAT handling
import ndspy.soundArchive


class MusicShuffleRandomizer(BaseRandomizer):
    """
    Shuffles music / sound-effect track data inside the ROM's SDAT archive.

    This randomizer does NOT use BDAT tables — it operates directly on
    the NDS ROM filesystem.  The ``randomize()`` stub exists only to
    satisfy the ABC contract; the real entry point is ``randomize_music(rom)``.

    Config keys:
        mode:  'vanilla' | 'shuffle' | 'chaos'
    """

    # Known SDAT filesystem path in DBZ AotS
    SDAT_PATH = "sound_data.sdat"

    # Heuristic separator between BGM and SFX sequence IDs.
    # In many NDS titles the first N SSEQ slots are BGM and the rest
    # are SFX.  We will detect this dynamically, but use a fallback
    # threshold if we cannot distinguish them.
    _BGM_HEURISTIC_MIN_SIZE = 512  # bytes — BGM sequences are usually larger

    def __init__(self, rng: GameRNG, config: dict):
        super().__init__(rng, config)
        self.mode: str = config.get("mode", "vanilla")

    # ── ABC compliance ───────────────────────────────────────

    def randomize(self, bdat, writer) -> None:
        """
        Not used — this randomizer works on the ROM filesystem, not BDAT.
        Call ``randomize_music(rom)`` instead.
        """
        pass

    # ── Main entry point ─────────────────────────────────────

    def randomize_music(self, rom) -> None:
        """
        Shuffle SSEQ entries inside the ROM's SDAT archive.

        Args:
            rom: NdsRom wrapper (randomizer.rom_io.nds_rom.NdsRom)
        """
        if self.mode == "vanilla":
            self._log("MusicShuffleRandomizer: mode=vanilla — skipping")
            return

        self._log(f"=== MusicShuffleRandomizer: mode={self.mode} ===")

        # 1. Locate the SDAT file
        sdat_path = self._find_sdat(rom)
        if sdat_path is None:
            self._log("ERROR: No SDAT file found in ROM filesystem!")
            return

        self._log(f"Found SDAT at: {sdat_path}")

        # 2. Parse the SDAT archive
        sdat_bytes = rom.get_file(sdat_path)
        sdat = ndspy.soundArchive.SDAT.fromData(sdat_bytes)

        # 3. Collect valid SSEQ entries (non-None)
        valid_indices = []
        for idx, seq in enumerate(sdat.sequences):
            if seq is not None:
                valid_indices.append(idx)

        if len(valid_indices) < 2:
            self._log("WARNING: Fewer than 2 SSEQ entries — nothing to shuffle")
            return

        self._log(f"Total SSEQ entries: {len(sdat.sequences)}, "
                  f"valid (non-None): {len(valid_indices)}")

        # 4. Classify into BGM vs SFX
        bgm_indices, sfx_indices = self._classify_sequences(
            sdat, valid_indices
        )
        self._log(f"Classified: {len(bgm_indices)} BGM, {len(sfx_indices)} SFX")

        # 5. Perform the shuffle based on mode
        if self.mode == "shuffle":
            self._shuffle_group(sdat, bgm_indices, "BGM")
        elif self.mode == "chaos":
            # In chaos, shuffle BGM among BGM *and* SFX among SFX,
            # then also cross-swap a few for extra craziness
            all_indices = bgm_indices + sfx_indices
            self._shuffle_group(sdat, all_indices, "ALL")
        else:
            self._log(f"WARNING: Unknown mode '{self.mode}', skipping")
            return

        # 6. Write the modified SDAT back into the ROM
        modified_sdat = sdat.save()
        rom.set_file(sdat_path, modified_sdat)
        self._log(f"Wrote modified SDAT ({len(modified_sdat):,} bytes) "
                  f"back to {sdat_path}")
        self._log("=== MusicShuffleRandomizer complete ===")

    # ── Internal helpers ─────────────────────────────────────

    def _find_sdat(self, rom) -> str | None:
        """
        Walk the ROM filesystem to find the first .sdat file.
        Returns the NitroFS path or None.
        """
        all_files = rom.list_files()
        for fpath in all_files:
            if fpath.lower().endswith(".sdat"):
                return fpath
        return None

    def _classify_sequences(
        self,
        sdat: ndspy.soundArchive.SDAT,
        valid_indices: list[int],
    ) -> tuple[list[int], list[int]]:
        """
        Heuristically split SSEQ indices into BGM and SFX groups.

        BGM sequences are usually much larger than SFX sequences.
        We use raw data length as the primary discriminator.
        """
        bgm = []
        sfx = []

        for idx in valid_indices:
            seq = sdat.sequences[idx]
            # ndspy SSEQ entry: seq is a (data, *info) tuple or an SSEQ object
            # The raw data blob size is the best heuristic
            try:
                data_size = len(seq.data) if hasattr(seq, "data") else 0
            except Exception:
                data_size = 0

            if data_size >= self._BGM_HEURISTIC_MIN_SIZE:
                bgm.append(idx)
            else:
                sfx.append(idx)

        # If the heuristic produced an empty BGM group, treat everything
        # as BGM (better to shuffle everything than nothing)
        if not bgm:
            bgm = list(valid_indices)
            sfx = []

        return bgm, sfx

    def _shuffle_group(
        self,
        sdat: ndspy.soundArchive.SDAT,
        indices: list[int],
        label: str,
    ) -> None:
        """
        Shuffle the SSEQ data blobs among the given index slots.

        The *entry metadata* (bank references, volume, player, etc.)
        stays in place — only the raw sequence data is swapped.
        This keeps each slot's playback settings intact while changing
        which tune actually plays.
        """
        if len(indices) < 2:
            self._log(f"  {label}: fewer than 2 entries, skipping")
            return

        # Collect the raw data blobs in slot order
        data_blobs = []
        for idx in indices:
            seq = sdat.sequences[idx]
            data_blobs.append(seq.data if hasattr(seq, "data") else seq)

        # Build a label map for logging (index → original position)
        original_order = list(range(len(indices)))

        # Deterministic Fisher-Yates shuffle
        shuffled_order = list(original_order)
        self.rng.shuffle(shuffled_order)

        # Write shuffled data back
        for dest_pos, src_pos in enumerate(shuffled_order):
            dest_idx = indices[dest_pos]
            src_idx = indices[src_pos]
            seq = sdat.sequences[dest_idx]

            if hasattr(seq, "data"):
                seq.data = data_blobs[src_pos]
            else:
                sdat.sequences[dest_idx] = data_blobs[src_pos]

            if dest_idx != src_idx:
                self._log(
                    f"  {label} slot {dest_idx} ← data from slot {src_idx}"
                )

        self._log(f"  Shuffled {len(indices)} {label} entries")
