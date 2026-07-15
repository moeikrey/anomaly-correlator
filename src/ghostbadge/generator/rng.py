"""Seeded randomness scaffolding for the generator.

Determinism is a hard project convention: same seed + same params must yield
byte-identical output, because tests hash the files and ground-truth labels
must stay aligned with the events they describe. Two rules enforce that here:

1. Never touch the global `random` module — every consumer gets an explicit
   `random.Random` instance.
2. Independent parts of the world (the roster, each employee's daily
   narrative, each scenario injector) draw from *separate child streams*
   derived from the master seed. That way adding a draw in one component
   cannot shift the values every other component sees.
"""

import random


def child_rng(seed: int, *scope: str) -> random.Random:
    """Derive an independent RNG stream from the master seed and a scope key.

    String seeding uses SHA-512 internally (`random.seed(..., version=2)`),
    so streams are stable across platforms, Python versions, and
    PYTHONHASHSEED — unlike `hash()`-based derivation.

    Example: ``child_rng(42, "narrative", "E017")`` gives employee E017's
    personal stream; it never collides with ``child_rng(42, "roster")``.
    """
    return random.Random(":".join((str(seed), *scope)))
