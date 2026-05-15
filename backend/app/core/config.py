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
    id: str = "primary"
    label: str = "gpt image2(1)"
    endpoint_path: str = "/images/generations"
    retry_alternates: tuple["ImageGenerationSettings", ...] = ()
    retry_groups: int = 1

    @property
    def endpoint_url(self) -> str:
        return self.base_url.rstrip("/") + self.endpoint_path


@dataclass(frozen=True)
class ModelSettings:
    text: TextAnalysisSettings
    image: ImageGenerationSettings
    fallback_image: ImageGenerationSettings
    default_image_option_id: str
    image_options: dict[str, ImageGenerationSettings]


@dataclass(frozen=True)
class ObjectStorageSettings:
    endpoint: str
    access_key_id: str
    secret_access_key: str
    bucket: str
    region: str
    public_base_url: str
    key_prefix: str

    @property
    def configured(self) -> bool:
        return bool(self.endpoint and self.access_key_id and self.secret_access_key and self.bucket and self.public_base_url)


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
    primary_size = _read(source, "IMAGE_GENERATION_SIZE", "2048x2048")
    primary_backup_image = ImageGenerationSettings(
        id="primary_backup",
        label=_read(source, "IMAGE_GENERATION_BACKUP_LABEL", "gpt image2(1) backup"),
        api_key=_read(source, "IMAGE_GENERATION_BACKUP_API_KEY", ""),
        base_url=_read(source, "IMAGE_GENERATION_BACKUP_BASE_URL", "https://api-xai.ainaibahub.com/v1"),
        endpoint_path=_read(source, "IMAGE_GENERATION_BACKUP_ENDPOINT_PATH", "/images/generations"),
        model=_read(source, "IMAGE_GENERATION_BACKUP_MODEL", "gpt-image-2"),
        size=_read(source, "IMAGE_GENERATION_BACKUP_SIZE", primary_size),
        n=int(_read(source, "IMAGE_GENERATION_BACKUP_N", "1")),
        quality=_read(source, "IMAGE_GENERATION_BACKUP_QUALITY", ""),
        output_format=_read(source, "IMAGE_GENERATION_BACKUP_OUTPUT_FORMAT", ""),
        response_format=_read(source, "IMAGE_GENERATION_BACKUP_RESPONSE_FORMAT", ""),
    )
    primary_retry_groups = int(_read(source, "IMAGE_GENERATION_RETRY_GROUPS", "5")) if primary_backup_image.api_key else 1
    primary_image = ImageGenerationSettings(
        id="primary",
        label=_read(source, "IMAGE_GENERATION_LABEL", "gpt image2(1)"),
        api_key=_read(source, "IMAGE_GENERATION_API_KEY", ""),
        base_url=_read(source, "IMAGE_GENERATION_BASE_URL", "https://api.apiyi.com/v1"),
        endpoint_path=_read(source, "IMAGE_GENERATION_ENDPOINT_PATH", "/images/generations"),
        model=_read(source, "IMAGE_GENERATION_MODEL", "gpt-image-2-vip"),
        size=primary_size,
        n=int(_read(source, "IMAGE_GENERATION_N", "0")),
        quality=_read(source, "IMAGE_GENERATION_QUALITY", ""),
        output_format=_read(source, "IMAGE_GENERATION_OUTPUT_FORMAT", "png"),
        response_format=_read(source, "IMAGE_GENERATION_RESPONSE_FORMAT", "url"),
        retry_alternates=(primary_backup_image,) if primary_backup_image.api_key else (),
        retry_groups=max(1, primary_retry_groups),
    )
    fallback_size = _read(source, "FALLBACK_IMAGE_GENERATION_SIZE", "2048x2048")
    fallback_backup_image = ImageGenerationSettings(
        id="fallback_backup",
        label=_read(source, "FALLBACK_IMAGE_GENERATION_BACKUP_LABEL", "gpt image2(2) backup"),
        api_key=_read(source, "FALLBACK_IMAGE_GENERATION_BACKUP_API_KEY", ""),
        base_url=_read(source, "FALLBACK_IMAGE_GENERATION_BACKUP_BASE_URL", "https://api-xai.ainaibahub.com/v1"),
        endpoint_path=_read(source, "FALLBACK_IMAGE_GENERATION_BACKUP_ENDPOINT_PATH", "/images/generations"),
        model=_read(source, "FALLBACK_IMAGE_GENERATION_BACKUP_MODEL", "gpt-image-2"),
        size=_read(source, "FALLBACK_IMAGE_GENERATION_BACKUP_SIZE", fallback_size),
        n=int(_read(source, "FALLBACK_IMAGE_GENERATION_BACKUP_N", "1")),
        quality=_read(source, "FALLBACK_IMAGE_GENERATION_BACKUP_QUALITY", ""),
        output_format=_read(source, "FALLBACK_IMAGE_GENERATION_BACKUP_OUTPUT_FORMAT", ""),
        response_format=_read(source, "FALLBACK_IMAGE_GENERATION_BACKUP_RESPONSE_FORMAT", ""),
    )
    fallback_retry_groups = int(_read(source, "FALLBACK_IMAGE_GENERATION_RETRY_GROUPS", "5")) if fallback_backup_image.api_key else 1
    fallback_image = ImageGenerationSettings(
        id="fallback",
        label=_read(source, "FALLBACK_IMAGE_GENERATION_LABEL", "gpt image2(2)"),
        api_key=_read(source, "FALLBACK_IMAGE_GENERATION_API_KEY", _read(source, "LEGACY_IMAGE_GENERATION_API_KEY", "")),
        base_url=_read(source, "FALLBACK_IMAGE_GENERATION_BASE_URL", _read(source, "LEGACY_IMAGE_GENERATION_BASE_URL", "https://yunwu.ai/v1")),
        endpoint_path=_read(source, "FALLBACK_IMAGE_GENERATION_ENDPOINT_PATH", "/images/generations"),
        model=_read(source, "FALLBACK_IMAGE_GENERATION_MODEL", _read(source, "LEGACY_IMAGE_GENERATION_MODEL", "gpt-image-2-all")),
        size=fallback_size,
        n=int(_read(source, "FALLBACK_IMAGE_GENERATION_N", _read(source, "LEGACY_IMAGE_GENERATION_N", "1"))),
        retry_alternates=(fallback_backup_image,) if fallback_backup_image.api_key else (),
        retry_groups=max(1, fallback_retry_groups),
    )
    gemini_flash_image = ImageGenerationSettings(
        id="gemini_flash_image",
        label=_read(source, "GEMINI_FLASH_IMAGE_LABEL", "Gemini 3.1 Flash Image Preview"),
        api_key=_read(source, "GEMINI_FLASH_IMAGE_API_KEY", _read(source, "TEXT_ANALYSIS_API_KEY", "")),
        base_url=_read(source, "GEMINI_FLASH_IMAGE_BASE_URL", "https://www.shanbaob.net/v1"),
        endpoint_path=_read(source, "GEMINI_FLASH_IMAGE_ENDPOINT_PATH", "/chat/completions"),
        model=_read(source, "GEMINI_FLASH_IMAGE_MODEL", "gemini-3.1-flash-image-preview"),
        size=_read(source, "GEMINI_FLASH_IMAGE_SIZE", "2048x2048"),
        n=int(_read(source, "GEMINI_FLASH_IMAGE_N", "1")),
        response_format=_read(source, "GEMINI_FLASH_IMAGE_RESPONSE_FORMAT", "b64_json"),
    )
    image_options = {
        primary_image.id: primary_image,
        fallback_image.id: fallback_image,
        gemini_flash_image.id: gemini_flash_image,
    }
    default_image_option_id = _read(source, "DEFAULT_IMAGE_GENERATION_OPTION_ID", fallback_image.id)
    if default_image_option_id not in image_options:
        default_image_option_id = fallback_image.id

    return ModelSettings(
        text=TextAnalysisSettings(
            api_key=_read(source, "TEXT_ANALYSIS_API_KEY", ""),
            base_url=_read(source, "TEXT_ANALYSIS_BASE_URL", "https://www.shanbaob.net/v1"),
            model=_read(source, "TEXT_ANALYSIS_MODEL", "gemini-3.1-pro-preview"),
            max_tokens=int(_read(source, "TEXT_ANALYSIS_MAX_TOKENS", "4096")),
            temperature=float(_read(source, "TEXT_ANALYSIS_TEMPERATURE", "0.7")),
        ),
        image=primary_image,
        fallback_image=fallback_image,
        default_image_option_id=default_image_option_id,
        image_options=image_options,
    )


@dataclass(frozen=True)
class DatabaseSettings:
    url: str

    @property
    def configured(self) -> bool:
        return bool(self.url)


def get_object_storage_settings(env: Mapping[str, str] | None = None, env_file: Path | str | None = None) -> ObjectStorageSettings:
    dotenv_values = _read_env_file(_project_env_path() if env is None and env_file is None else env_file)
    source = _merge_env(dotenv_values, environ if env is None else env)
    return ObjectStorageSettings(
        endpoint=_read(source, "R2_ENDPOINT", ""),
        access_key_id=_read(source, "R2_ACCESS_KEY_ID", ""),
        secret_access_key=_read(source, "R2_SECRET_ACCESS_KEY", ""),
        bucket=_read(source, "R2_BUCKET", ""),
        region=_read(source, "R2_REGION", "auto"),
        public_base_url=_read(source, "R2_PUBLIC_BASE_URL", ""),
        key_prefix=_read(source, "R2_KEY_PREFIX", ""),
    )


def get_database_settings(env: Mapping[str, str] | None = None, env_file: Path | str | None = None) -> DatabaseSettings:
    dotenv_values = _read_env_file(_project_env_path() if env is None and env_file is None else env_file)
    source = _merge_env(dotenv_values, environ if env is None else env)
    return DatabaseSettings(
        url=_read(source, "DATABASE_URL", ""),
    )
