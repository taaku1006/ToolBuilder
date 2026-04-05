from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Provider-agnostic LLM settings (take precedence over openai_* when set)
    llm_model: str = ""
    llm_base_url: str = ""

    # Per-provider API keys
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # Claude Agent SDK (subscription-based, OAuth token)
    claude_oauth_token: str = ""  # env: CLAUDE_CODE_OAUTH_TOKEN

    # Embedding model (empty = auto-select based on available keys)
    embedding_model: str = ""

    # Legacy OpenAI-specific (used as fallback when llm_* is empty)
    openai_model: str = "gpt-4o"

    @property
    def active_model(self) -> str:
        """Return the effective model: LLM_MODEL takes precedence over OPENAI_MODEL."""
        return self.llm_model or self.openai_model

    @property
    def active_base_url(self) -> str:
        """Return the effective base URL: LLM_BASE_URL takes precedence."""
        return self.llm_base_url

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
    llm_eval_loop_enabled: bool = False
    llm_eval_retry_limit: int = 2
    llm_eval_score_threshold: float = 7.0
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
