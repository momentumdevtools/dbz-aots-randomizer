#!/usr/bin/env python3
"""
rng.py — Deterministic seed-based RNG for the Randomizer
=========================================================
Uses the same Linear Congruential Generator (LCG) as the NDS game itself.
Verified from ARM9 disassembly: seed = seed * 0x41C64E6D + 0x3039

This ensures reproducible randomization — same seed always produces
the same output, regardless of platform or Python version.
"""


class GameRNG:
    """
    Deterministic pseudo-random number generator.

    Implements the exact same LCG algorithm found in the NDS ARM9 binary
    at the rng_rand16 function (0x02007C70). This guarantees that seed-based
    randomization is fully reproducible.

    The LCG constants are:
        multiplier = 0x41C64E6D  (1103515245)
        increment  = 0x3039      (12345)
        modulus    = 0x100000000 (2^32, implicit via masking)

    Output: bits [31:16] of the state (16-bit value, 0–65535).
    """

    MULTIPLIER = 0x41C64E6D
    INCREMENT = 0x3039
    MASK_32 = 0xFFFFFFFF

    def __init__(self, seed: int):
        """Initialize with a 32-bit seed value."""
        self.initial_seed = seed & self.MASK_32
        self.state = self.initial_seed

    def next_raw(self) -> int:
        """Advance the state and return the raw 16-bit output."""
        self.state = (self.state * self.MULTIPLIER + self.INCREMENT) & self.MASK_32
        return (self.state >> 16) & 0xFFFF

    def next(self) -> int:
        """Alias for next_raw() — returns 0–65535."""
        return self.next_raw()

    def randint(self, lo: int, hi: int) -> int:
        """Return a random integer in [lo, hi] inclusive."""
        if lo >= hi:
            return lo
        span = hi - lo + 1
        return lo + (self.next() % span)

    def random_float(self) -> float:
        """Return a random float in [0.0, 1.0)."""
        return self.next() / 65536.0

    def chance(self, percent: int) -> bool:
        """Return True with the given percentage probability (0–100)."""
        return (self.next() % 100) < percent

    def choose(self, items: list):
        """Pick a random element from a non-empty list."""
        if not items:
            raise ValueError("Cannot choose from empty list")
        return items[self.next() % len(items)]

    def weighted_choice(self, items: list, weights: list):
        """
        Pick an item using weighted random selection.
        Mirrors the NDS encounter group selection algorithm:
        accumulate weights, compare against rng value.
        """
        if len(items) != len(weights):
            raise ValueError("items and weights must have same length")

        total = sum(weights)
        if total <= 0:
            return self.choose(items)

        roll = self.next() % total
        cumulative = 0
        for item, weight in zip(items, weights):
            cumulative += weight
            if roll < cumulative:
                return item
        return items[-1]  # fallback (shouldn't happen)

    def shuffle(self, lst: list) -> list:
        """
        In-place Fisher-Yates shuffle using deterministic RNG.
        Returns the same list (mutated) for convenience.
        """
        for i in range(len(lst) - 1, 0, -1):
            j = self.next() % (i + 1)
            lst[i], lst[j] = lst[j], lst[i]
        return lst

    def sample(self, population: list, k: int) -> list:
        """Return k unique elements from population without replacement."""
        if k > len(population):
            k = len(population)
        pool = list(population)
        self.shuffle(pool)
        return pool[:k]

    def gauss_int(self, mean: int, stddev: int) -> int:
        """
        Approximate Gaussian (normal) distribution using sum of randoms.
        Returns an integer. Uses Box-Muller-like approximation via
        the central limit theorem (sum of 6 uniform values).
        """
        # Sum of 6 uniform [0,1) ≈ N(3, 0.5) → scale to desired mean/stddev
        total = sum(self.random_float() for _ in range(6))
        # total is approximately N(3.0, sqrt(0.5))
        # Normalize to N(0,1): z = (total - 3.0) / sqrt(0.5)
        z = (total - 3.0) / 0.7071
        return int(round(mean + z * stddev))

    def scale_value(self, value: int, min_scale: float, max_scale: float,
                    clamp_min: int = 0, clamp_max: int = 65535) -> int:
        """
        Scale a value by a random factor in [min_scale, max_scale].
        Result is clamped to [clamp_min, clamp_max].
        Useful for stat randomization.
        """
        # Use 1000 steps of precision for the scale factor
        scale_1000 = self.randint(int(min_scale * 1000), int(max_scale * 1000))
        result = (value * scale_1000) // 1000
        return max(clamp_min, min(clamp_max, result))

    def reset(self):
        """Reset to the initial seed."""
        self.state = self.initial_seed

    def fork(self, domain: str) -> 'GameRNG':
        """
        Create a child RNG seeded by hashing this RNG's state with a domain string.
        This ensures different randomizer passes (encounters, stats, items)
        don't interfere with each other — changing one doesn't cascade.
        """
        h = self.state
        for ch in domain:
            h = (h * 31 + ord(ch)) & self.MASK_32
        return GameRNG(h)

    def __repr__(self) -> str:
        return f"GameRNG(seed=0x{self.initial_seed:08X}, state=0x{self.state:08X})"
