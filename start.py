# Start script: apply the disable_voice patch in this process, then execute bot.py as a script.
# This ensures the patch is effective before discord is imported.
import disable_voice
import runpy
import sys

# If your main script is named bot.py, run it as a module __main__ so top-level code executes.
# Adjust the module name if your main file is different.
MODULE_NAME = 'bot'

# If bot.py is not importable as a module (e.g., different package layout), you can use runpy.run_path:
# runpy.run_path('bot.py', run_name='__main__')

# Use run_module to run it as __main__ (preserves expected behavior if bot.py checks __name__ == '__main__').
runpy.run_module(MODULE_NAME, run_name='__main__')
