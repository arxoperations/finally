from datetime import date

from app.settings import DEFAULT_OPENROUTER_MODEL, DEFAULT_OPENROUTER_MODEL_RETIRES_ON, Settings, retired_model_warning


def test_settings_loads_values_from_env_file(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENROUTER_API_KEY=from-dotenv\nOPENROUTER_MODEL=from-dotenv-model\n")
    monkeypatch.chdir(tmp_path)

    settings = Settings(_env_file=env_file)

    assert settings.openrouter_api_key == "from-dotenv"
    assert settings.openrouter_model == "from-dotenv-model"


def test_exported_env_var_takes_precedence_over_env_file(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENROUTER_API_KEY=from-dotenv\n")
    monkeypatch.setenv("OPENROUTER_API_KEY", "from-exported-env")

    settings = Settings(_env_file=env_file)

    assert settings.openrouter_api_key == "from-exported-env"


def test_mock_mode_allows_chat_without_api_key() -> None:
    settings = Settings(_env_file=None, openrouter_api_key=None, llm_mock=True)

    assert settings.chat_configured is True
    assert settings.chat_configuration_error is None


def test_real_chat_requires_an_api_key() -> None:
    settings = Settings(_env_file=None, openrouter_api_key=None, llm_mock=False)

    assert settings.chat_configured is False
    assert settings.chat_configuration_error == "OPENROUTER_API_KEY es obligatoria cuando LLM_MOCK=false."


def test_default_model_uses_the_litellm_openrouter_prefix() -> None:
    settings = Settings(_env_file=None, openrouter_api_key=None)

    assert settings.openrouter_model == DEFAULT_OPENROUTER_MODEL


def test_default_model_is_not_past_its_retirement_date() -> None:
    """Falla a partir de la fecha de retiro para forzar la migración fuera del modelo preview."""
    settings = Settings(_env_file=None, openrouter_api_key=None)

    assert settings.model_retirement_warning is None, (
        f"{DEFAULT_OPENROUTER_MODEL} fue retirado el "
        f"{DEFAULT_OPENROUTER_MODEL_RETIRES_ON.isoformat()}; actualiza DEFAULT_OPENROUTER_MODEL "
        "en settings.py y OPENROUTER_MODEL en .env.example a un modelo vigente."
    )


def test_retired_model_warning_triggers_on_and_after_the_retirement_date() -> None:
    day_before = DEFAULT_OPENROUTER_MODEL_RETIRES_ON.replace(day=DEFAULT_OPENROUTER_MODEL_RETIRES_ON.day - 1)

    assert retired_model_warning(DEFAULT_OPENROUTER_MODEL, today=day_before) is None
    assert retired_model_warning(DEFAULT_OPENROUTER_MODEL, today=DEFAULT_OPENROUTER_MODEL_RETIRES_ON) is not None
    assert retired_model_warning("openrouter/some-other-model", today=DEFAULT_OPENROUTER_MODEL_RETIRES_ON) is None
