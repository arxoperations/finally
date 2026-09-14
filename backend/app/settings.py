"""Configuración de aplicación compartida por el backend de FinAlly."""

from datetime import date
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OPENROUTER_MODEL = "openrouter/dots-studio/dots-3-note-preview:free"
DEFAULT_OPENROUTER_MODEL_RETIRES_ON = date(2026, 9, 30)


def retired_model_warning(model: str, today: date | None = None) -> str | None:
    """Advierte si ``model`` sigue siendo el modelo preview de Dots tras su retiro anunciado."""

    if today is None:
        today = date.today()
    if model == DEFAULT_OPENROUTER_MODEL and today >= DEFAULT_OPENROUTER_MODEL_RETIRES_ON:
        return (
            f"OPENROUTER_MODEL sigue apuntando a {DEFAULT_OPENROUTER_MODEL}, "
            f"retirado el {DEFAULT_OPENROUTER_MODEL_RETIRES_ON.isoformat()}. "
            "Migra a un modelo de reemplazo y actualiza .env.example."
        )
    return None


class Settings(BaseSettings):
    """Carga localmente ``.env`` y respeta las variables exportadas del proceso."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openrouter_api_key: str | None = None
    openrouter_model: str = DEFAULT_OPENROUTER_MODEL
    openrouter_provider_order: str = "cerebras"
    massive_api_key: str | None = None
    llm_mock: bool = False

    @property
    def chat_configured(self) -> bool:
        """Indica si el endpoint de chat puede responder sin exponer secretos de configuración."""

        return self.llm_mock or bool(self.openrouter_api_key and self.openrouter_api_key.strip())

    @property
    def chat_configuration_error(self) -> str | None:
        """Mensaje de error a mostrar si el chat no está configurado, o ``None`` si lo está."""

        if self.chat_configured:
            return None
        return "OPENROUTER_API_KEY es obligatoria cuando LLM_MOCK=false."

    @property
    def model_retirement_warning(self) -> str | None:
        """Mensaje de advertencia si ``openrouter_model`` ya fue retirado, o ``None``."""

        return retired_model_warning(self.openrouter_model)
