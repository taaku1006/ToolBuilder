from pydantic import BaseModel


class GenerateRequest(BaseModel):
    task: str
    file_id: str | None = None
    max_steps: int = 3
    skill_id: str | None = None
    model: str | None = None
    stage_models: dict[str, str] | None = None


class AgentLogEntry(BaseModel):
    phase: str       # "A", "B", "C", "D", "E"
    action: str      # "start", "complete", "error"
    content: str     # details
    timestamp: str   # ISO format


class GenerateResponse(BaseModel):
    id: str
    summary: str
    python_code: str
    steps: list[str]
    tips: str
    agent_log: list[AgentLogEntry] = []
    reflection_steps: int = 0
    debug_retries: int = 0
