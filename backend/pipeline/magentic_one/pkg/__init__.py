"""MagenticOne package implementation — uses autogen-agentchat directly.

Requires: autogen-agentchat, autogen-ext[openai]
"""

from pipeline.magentic_one.pkg.runner import run_magentic_one_pkg

__all__ = ["run_magentic_one_pkg"]
