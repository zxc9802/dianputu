from __future__ import annotations

from dataclasses import dataclass
from os import environ
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class TextAnalysisSettings:
    api_key: str
    base_url: str
    model: str
    max_tokens: int
    temperature: float

    @property
    def endpoint_url(self) -> str:
        return self.base_url.rstrip("/") + "/chat/completions"


@dataclass(frozen=True)
class ImageGenerationSettings:
    api_key: str
    base_url: str
    model: str
    size: str
    n: int
    quality: str = ""
    output_format: str = ""
    response_format: str = ""

    @property
    def endpoint_url(self) -> str:
        return self.base_url.rstrip("/") + "/images/generations"


@dataclass(frozen=True)
class ModelSettings:
    text: TextAnalysisSettings
    image: ImageGenerationSettings
    fallback_image: ImageGenerationSettings


def _read(env: Mapping[str, str], key: str, default: str) -> str:
    value = env.get(key)
    return value if value not in (None, "") else default


def _project_env_path() -> Path:
    return Path(__file__).resolve().parents[3] / ".env"


def _read_env_file(path: Path | str | None) -> dict[str, str]:
    if path is None:
        return {}

    env_path = Path(path)
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _merge_env(dotenv_values: Mapping[str, str], env_values: Mapping[str, str]) -> dict[str, str]:
    merged = dict(dotenv_values)
    for key, value in env_values.items():
        if value not in (None, ""):
            merged[key] = value
    return merged


def get_model_settings(env: Mapping[str, str] | None = None, env_file: Path | str | None = None) -> ModelSettings:
    dotenv_values = _read_env_file(_project_env_path() if env is None and env_file is None else env_file)
    source = _merge_env(dotenv_values, environ if env is None else env)
    return ModelSettings(
        text=TextAnalysisSettings(
            api_key=_read(source, "TEXT_ANALYSIS_API_KEY", ""),
            base_url=_read(source, "TEXT_ANALYSIS_BASE_URL", "https://www.shanbaob.net/v1"),
            model=_read(source, "TEXT_ANALYSIS_MODEL", "gemini-3.1-pro-preview"),
            max_tokens=int(_read(source, "TEXT_ANALYSIS_MAX_TOKENS", "4096")),
            temperature=float(_read(source, "TEXT_ANALYSIS_TEMPERATURE", "0.2")),
        ),
        image=ImageGenerationSettings(
            api_key=_read(source, "IMAGE_GENERATION_API_KEY", ""),
            base_url=_read(source, "IMAGE_GENERATION_BASE_URL", "https://api-xai.ainaibahub.com/v1"),
            model=_read(source, "IMAGE_GENERATION_MODEL", "gpt-image-2"),
            size=_read(source, "IMAGE_GENERATION_SIZE", "1024x1024"),
            n=int(_read(source, "IMAGE_GENERATION_N", "1")),
            quality=_read(source, "IMAGE_GENERATION_QUALITY", "high"),
            output_format=_read(source, "IMAGE_GENERATION_OUTPUT_FORMAT", "png"),
            response_format=_read(source, "IMAGE_GENERATION_RESPONSE_FORMAT", "b64_json"),
        ),
        fallback_image=ImageGenerationSettings(
            api_key=_read(source, "FALLBACK_IMAGE_GENERATION_API_KEY", _read(source, "LEGACY_IMAGE_GENERATION_API_KEY", "")),
            base_url=_read(source, "FALLBACK_IMAGE_GENERATION_BASE_URL", _read(source, "LEGACY_IMAGE_GENERATION_BASE_URL", "https://yunwu.ai/v1")),
            model=_read(source, "FALLBACK_IMAGE_GENERATION_MODEL", _read(source, "LEGACY_IMAGE_GENERATION_MODEL", "gpt-image-2-all")),
            size=_read(source, "FALLBACK_IMAGE_GENERATION_SIZE", _read(source, "LEGACY_IMAGE_GENERATION_SIZE", "1024x1024")),
            n=int(_read(source, "FALLBACK_IMAGE_GENERATION_N", _read(source, "LEGACY_IMAGE_GENERATION_N", "1"))),
        ),
    )
