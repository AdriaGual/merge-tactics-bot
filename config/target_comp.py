"""
Ranked list of the troops the bot tries to build every match.

Merge Tactics reshuffles its roster and balance every season, so the comp is not
hardcoded: config/season_tier.json holds the current season's troop tier list
(S/A/B/C/D) and this module turns it into the priority order the deploy planner
forces. The bot buys S/A/B troops (strong / build-around / solid) and ignores
C/D to commit to a good comp instead of diluting with weak units.

Refresh the season data with:
    python utils/fetch_tier_list.py

If the JSON is missing the planner falls back to the last known list below.
"""

import json
import os

TIER_FILE = os.path.join(os.path.dirname(__file__), "season_tier.json")

# Tiers worth spending elixir on. C is situational and D is a trap, so they are
# left out: elixir is saved for the good troops instead of diluting the roster.
BUY_TIERS = ("S", "A", "B")
TIER_ORDER = ("S", "A", "B", "C", "D")

# Fallback if the season file is missing (Season 11 S/A/B troops).
_FALLBACK = [
    "boss_bandit", "monk", "golden_knight", "pekka", "skeleton_king",
    "mega_knight", "knight", "electro_giant", "mini_pekka", "valkyrie", "royal_giant",
    "barbarian", "wizard", "archer", "musketeer", "baby_dragon",
    "electro_wizard", "bomber", "bandit", "princess", "executioner",
]


def _load():
    try:
        with open(TIER_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return list(_FALLBACK), None

    tiers = data.get("tiers", {})
    comp = [name for tier in TIER_ORDER if tier in BUY_TIERS for name in tiers.get(tier, [])]
    if not comp:
        return list(_FALLBACK), data.get("season")
    return comp, data.get("season")


TARGET_COMP, SEASON = _load()

_RANK = {name: i for i, name in enumerate(TARGET_COMP)}


def target_rank(name):
    """Lower is stronger; troops outside the list rank after everything."""
    return _RANK.get(name, len(TARGET_COMP))
