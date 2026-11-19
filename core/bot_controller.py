"""
Bot controller interface for GUI integration.
Provides a clean interface between the GUI and bot logic.
"""

import logging
from core.game_logic import GameLogic

logger = logging.getLogger(__name__)

class BotController:
    def __init__(self, merge_tactics_bot):
        self.bot = merge_tactics_bot
        
    def start_bot(self):
        """Start the bot"""
        self.bot.start_bot()
        
    def stop_bot(self):
        """Stop the bot"""
        self.bot.stop_bot()
        
    def is_running(self):
        """Check if bot is running"""
        return self.bot.is_running()
        
    def get_last_elixir_value(self):
        """Get the last read elixir value"""
        return getattr(self.bot, 'last_elixir_value', None)

    def run_loop(self):
        """Run the bot loop"""
        self.bot.run_loop()
