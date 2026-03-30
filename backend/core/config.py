from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openai_api_key: str
    openai_model: str = "gpt-4o"

    database_url: str = "sqlite+aiosqlite:///./db/history.db"
    upload_dir: str = "./uploads"
    output_dir: str = "./outputs"
    max_upload_mb: int = 50
    exec_timeout: int = 30
    cors_origins: str = "http://localhost:5173"

    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "text"

    reflection_enabled: bool = True
    reflection_phase_enabled: bool = True
    reflection_max_steps: int = 3
    tools_dir: str = "./tools"

    debug_loop_enabled: bool = True
    debug_retry_limit: int = 3

    skills_enabled: bool = True
    skills_dir: str = "./skills"
    skills_similarity_threshold: float = 0.4

    eval_debug_loop_enabled: bool = False
    eval_debug_retry_limit: int = 3
    eval_debug_quality_threshold: float = 0.85
    eval_retry_strategy: str = "none"  # "none" | "restart" | "replan"
    eval_retry_max_loops: int = 2

    task_decomposition_enabled: bool = False
    max_subtasks: int = 5
    subtask_debug_retries: int = 2

    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]
