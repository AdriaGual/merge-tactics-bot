"""
Logging configuration for the Merge Tactics bot.
"""

import logging

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO, 
        format='%(levelname)s: %(message)s'
    )
    return logging.getLogger(__name__)

def get_logger(name):
    """Get a logger instance"""
    return logging.getLogger(name)
