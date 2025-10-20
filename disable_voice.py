# This patches discord.py to disable voice support. Use a real dummy module object,
# not None, and set env vars. Must be imported in the same process before any
# `import discord`.
import os
import sys
import types

# Recommended env vars used by different patches/versions
os.environ.setdefault('DISABLE_DISCORD_VOICE', '1')
os.environ.setdefault('DISABLE_VOICE', '1')

# Provide dummy module objects so `import discord.voice_client` succeeds without real voice support.
sys.modules['discord.voice_client'] = types.ModuleType('discord.voice_client')
sys.modules['discord.player'] = types.ModuleType('discord.player')
