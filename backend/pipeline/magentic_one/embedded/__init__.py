"""MagenticOne embedded implementation — no autogen dependency.

Faithful port of autogen's MagenticOneOrchestrator:
  - CoderAgent      (mirrors MagenticOneCoderAgent)
  - ComputerTerminalAgent (mirrors CodeExecutorAgent + LocalCommandLineCodeExecutor)
  - MagenticOneOrchestrator (2-loop: Task Ledger / Progress Ledger)
"""

from pipeline.magentic_one.embedded.runner import run_magentic_one_embedded

__all__ = ["run_magentic_one_embedded"]
