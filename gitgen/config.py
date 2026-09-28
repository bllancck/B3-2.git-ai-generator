"""AI API Key 설정을 읽는다."""

import os
from pathlib import Path

from dotenv import load_dotenv

from .errors import ConfigurationError


ENV_FILE_PATH = Path(__file__).resolve().parent.parent / ".env"


def get_api_key(env_file_path: Path = ENV_FILE_PATH) -> str:
    """환경변수 또는 지정한 .env 파일에서 AI API Key를 읽는다."""
    load_dotenv(dotenv_path=env_file_path, override=False)
    api_key = os.getenv("AI_API_KEY")
    if api_key is None or not api_key.strip():
        raise ConfigurationError("AI_API_KEY 환경변수가 설정되지 않았습니다.")
    return api_key
