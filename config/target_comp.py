"""
Ranked list of the troops the bot tries to build every match.

Merge Tactics has no control over which cards the shop offers, so the closest
thing to a "good composition" is a focused priority list: always buy the
strongest troop of this list that is on offer, prefer merging what is already
deployed, and never spend elixir on troops outside it (save for the comp). The
roster is capped so it commits to a handful of strong troops instead of
spreading thin, which is what makes high-star merges reachable.

Edit this list to change the composition the deploy planner forces.
"""

# Strongest first. Ties are broken by elixir cost in the planner.
TARGET_COMP = [
    "mega_knight",
    "archer_queen",
    "golden_knight",
    "pekka",
    "prince",
    "dark_prince",
    "bandit",
    "hog_rider",
    "musketeer",
    "witch",
    "wizard",
    "electro_wizard",
    "executioner",
    "magic_archer",
    "mini_pekka",
    "valkyrie",
]

_RANK = {name: i for i, name in enumerate(TARGET_COMP)}


def target_rank(name):
    """Lower is stronger; troops outside the list rank after everything."""
    return _RANK.get(name, len(TARGET_COMP))
