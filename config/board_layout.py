"""
Screen regions of the live Merge Tactics match, measured on a 900x1600 capture.

Everything here is in screenshot pixels (the bot always captures 900x1600).
The rectangles were measured on a Season 11 match; if the UI is restyled, the
quickest way to re-measure is to take a screenshot, open it and read the boxes.
"""

# Three shop cards of the deploy phase: (y0, y1, x0, x1)
SHOP_TILES = [
    (1385, 1535, 195, 315),
    (1385, 1535, 345, 465),
    (1385, 1535, 495, 615),
]

# Tap target of each shop card (its centre)
SHOP_CENTERS = [(255, 1460), (405, 1460), (555, 1460)]

# Golden elixir cost badge in the top-left corner of every shop card. The crop
# stops above the bottom of the badge so the card art underneath (which is just
# as bright as the digit) does not leak extra glyphs into the reading.
COST_BADGES = [
    (1378, 1420, 192, 238),
    (1378, 1420, 342, 388),
    (1378, 1420, 492, 538),
]

# Elixir drop badge (bottom right)
ELIXIR_RECT = (660, 1455, 820, 1580)

# Hex arena where troops are deployed, and the bench strip underneath it
ARENA_RECT = (230, 560, 705, 1235)
BENCH_RECT = (200, 1245, 700, 1310)

# "Fase de despliegue" / "Fase de batalla" label (top left)
PHASE_LABEL_RECT = (0, 190, 300, 260)
PHASE_LABELS = {
    "deploy": "templates/phases/deploy_label.png",
    "battle": "templates/phases/battle_label.png",
}
PHASE_THRESHOLD = 0.9

# Quest orbs: bright, saturated translucent spheres that appear on the arena in
# any colour and hand out money when tapped. Detect them by brightness (the
# grass is dimmer) with a solid-fill filter, so colour does not matter.
ORB_HSV_LOW = (0, 120, 205)
ORB_HSV_HIGH = (180, 255, 255)
ORB_MIN_DIAMETER = 40
ORB_MAX_DIAMETER = 140
ORB_MIN_FILL = 0.45

# End-of-match buttons (templates/buttons), matched anywhere on screen to walk
# out of results and start the next match. None of them appear during play.
END_BUTTONS = {
    "rematch": "templates/buttons/rematch.png",  # "Jugar de Nuevo" on the results board
    "view": "templates/buttons/view.png",        # "Ver" on the elimination banner
    "leave": "templates/buttons/leave.png",      # "Salir" while spectating survivors
}
END_BUTTON_THRESHOLD = 0.9

# Lobby "Batalla" (search match) button word, matched to start a match
SEARCH_BUTTON = "templates/buttons/search.png"
SEARCH_THRESHOLD = 0.9

# Bottom bench slots (our reserve), centre points on a 900x1600 capture. A full
# bench blocks purchases, so the planner sells a reserve unit to keep buying.
BENCH_CELLS = [(210, 1280), (315, 1280), (410, 1280), (500, 1280), (585, 1280)]

# Sell button that appears after selecting a unit
SELL_BUTTON = "templates/sell.png"
SELL_THRESHOLD = 0.85
