from pydantic import BaseModel


class GenerateRequest(BaseModel):
    task: str
    file_id: str | None = None
    max_steps: int = 3
    skill_id: str | None = None


class GenerateResponse(BaseModel):
    id: str
    summary: str
    python_code: str
    steps: list[str]
    tips: str
