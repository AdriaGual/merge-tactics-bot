"""
Refresh the season tier list from crownstats.com for the bot's target comp.

Merge Tactics changes its roster and balance every season, so a hardcoded comp
goes stale. This tool pulls the published troop tier list (S/A/B/C/D, ranked by
the site's methodology) and writes config/season_tier.json, which
config/target_comp.py reads to rank the troops the bot buys.

Usage:
    python utils/fetch_tier_list.py            # fetch and write config/season_tier.json
    python utils/fetch_tier_list.py --print    # print the parsed result only

The troop names are mapped back to the bot's internal names through ART_MAP, so
they line up with the templates and unit_costs.
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.card_identifier import ART_MAP  # noqa: E402

TIER_URL = "https://crownstats.com/merge-tactics/tier-list"
OUT_FILE = os.path.join("config", "season_tier.json")
TIERS = ("S", "A", "B", "C", "D")

# art filename -> internal troop name
_ART_NAME = {os.path.basename(v): k for k, v in ART_MAP.items()}


def _internal_name(art, troop_id):
    base = os.path.basename(art)
    return _ART_NAME.get(base) or troop_id.replace("-", "_")


def fetch_html(url=TIER_URL):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def parse(html):
    # Troops come as one ordered JSON array (S..D order). Quotes are escaped.
    troop_pat = r'\{\\"id\\":\\"([^"\\]+)\\",\\"name\\":\\"([^"\\]+)\\",\\"art\\":\\"([^"\\]+)\\"\}'
    troops = re.findall(troop_pat, html)
    if not troops:
        raise RuntimeError("no troop list found; page layout changed?")

    names = [_internal_name(art, tid) for tid, _name, art in troops]

    # Rendered buttons carry title="Name — X tier"; use the letters in order.
    tier_seq = []
    for title in re.findall(r'title="([^"]+)"', html):
        if " tier" in title:
            m = re.search(r"\b([SABCD])\s*tier\b", title)
            if m:
                tier_seq.append(m.group(1))

    tiers = {t: [] for t in TIERS}
    if len(tier_seq) == len(names):
        for name, tier in zip(names, tier_seq):
            tiers[tier].append(name)
    else:
        # Fallback: no tier info, keep the flat order under "order" only.
        tiers = {t: [] for t in TIERS}
        tiers["_ordered"] = names

    season = None
    m = re.search(r"Season\s+(\d+)", html)
    if m:
        season = int(m.group(1))

    order = [n for t in TIERS for n in tiers.get(t, [])] or names
    return {
        "season": season,
        "source": TIER_URL,
        "fetched": date.today().isoformat(),
        "tiers": tiers,
        "order": order,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print", dest="print_only", action="store_true",
                        help="print the parsed result without writing the file")
    args = parser.parse_args()

    data = parse(fetch_html())
    text = json.dumps(data, indent=4, ensure_ascii=False)
    if args.print_only:
        print(text)
        return

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"[tier] season {data['season']} -> {OUT_FILE}")
    for t in TIERS:
        if data["tiers"].get(t):
            print(f"  {t}: {', '.join(data['tiers'][t])}")


if __name__ == "__main__":
    main()
