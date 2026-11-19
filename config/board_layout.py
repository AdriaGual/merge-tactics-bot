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

# Golden elixir cost badge in the top-left corner of every shop card
COST_BADGES = [
    (1378, 1445, 192, 252),
    (1378, 1445, 342, 402),
    (1378, 1445, 492, 552),
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

# Quest orbs: translucent cyan spheres that pop up on the arena
ORB_HSV_LOW = (80, 40, 180)
ORB_HSV_HIGH = (105, 145, 255)
ORB_MIN_DIAMETER = 40
ORB_MAX_DIAMETER = 110
