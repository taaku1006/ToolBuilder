"""MagenticOne integration for ToolBuilder.

Two architecture options:

  embedded — Faithful port of autogen's MagenticOneOrchestrator.
             No autogen dependency. Uses ToolBuilder's OpenAIClient + sandbox.
             Directory: pipeline/magentic_one/embedded/

  pkg      — Thin wrapper around autogen-agentchat's MagenticOneGroupChat.
             Requires: autogen-agentchat, autogen-ext[openai]
             Directory: pipeline/magentic_one/pkg/
"""

from pipeline.magentic_one.embedded.runner import run_magentic_one_embedded
from pipeline.magentic_one.pkg.runner import run_magentic_one_pkg

__all__ = ["run_magentic_one_embedded", "run_magentic_one_pkg"]
