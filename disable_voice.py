# This patches discord.py to disable voice support
import sys
sys.modules['discord.voice_client'] = None
sys.modules['discord.player'] = None
