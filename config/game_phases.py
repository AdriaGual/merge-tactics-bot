"""
Game phase detection templates and related constants.
"""

# Template file paths for game phases
PHASE_TEMPLATES = {
    'init_battle': 'templates/battle.png',
    'phase_deploy': 'templates/deploy_phase.png', 
    'phase_battle': 'templates/battle_phase.png',
    'play_again': 'templates/play_again.png',
    'quit': 'templates/quit.png',
    'reward': 'templates/reward.png',
    'back': 'templates/back.png',
    'sell_button': 'templates/sell.png',
    'empty_bench': 'templates/empty_bench.png'
}

# Game state constants
GAME_STATES = {
    'IDLE': 'idle',
    'DEPLOY': 'deploy', 
    'BATTLE': 'battle',
    'REWARD': 'reward',
    'MENU': 'menu'
}
