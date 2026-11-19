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

# Quest orbs: translucent spheres that pop up on the arena. They come in more
# than one colour (cyan, magenta), so several HSV ranges are matched together.
ORB_HSV_RANGES = [
    ((80, 40, 180), (105, 145, 255)),    # cyan
    ((135, 40, 170), (175, 160, 255)),   # magenta / pink
]
ORB_MIN_DIAMETER = 40
ORB_MAX_DIAMETER = 110

# End-of-match buttons (templates/buttons), matched anywhere on screen to walk
# out of results and start the next match. None of them appear during play.
END_BUTTONS = {
    "rematch": "templates/buttons/rematch.png",  # "Jugar de Nuevo" on the results board
    "view": "templates/buttons/view.png",        # "Ver" on the elimination banner
    "leave": "templates/buttons/leave.png",      # "Salir" while spectating survivors
}
END_BUTTON_THRESHOLD = 0.9
