"""코디세이 Chat Completions API 요청과 응답 처리."""

import json
import socket
from urllib import error, request

from .errors import AIAPIError


CODYSSEY_CHAT_COMPLETIONS_URL = (
    "https://copa.codyssey.kr/v1/chat/completions"
)


DEFAULT_MODEL = "gpt-5.4-mini"


DEFAULT_TEMPERATURE = 0.2


DEFAULT_MAX_OUTPUT_TOKENS = 300


REQUEST_TIMEOUT_SECONDS = 30


def extract_response_text(response_data: dict) -> str:
    """Chat Completions 응답에서 생성된 텍스트를 추출한다."""
    texts: list[str] = []
    for choice in response_data.get("choices", []):
        message = choice.get("message", {})
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            texts.append(content.strip())

    if not texts:
        raise AIAPIError("AI API 응답에서 생성된 텍스트를 찾을 수 없습니다.")
    return "\n".join(texts)


def parse_api_error(error_body: bytes) -> str:
    """API 오류 응답에서 사용자에게 보여 줄 원인 메시지를 추출한다."""
    try:
        error_data = json.loads(error_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "API가 오류 상세 내용을 제공하지 않았습니다."

    message = error_data.get("error", {}).get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()
    return "API가 오류 상세 내용을 제공하지 않았습니다."


def call_ai_api(
    api_key: str,
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    api_url: str = CODYSSEY_CHAT_COMPLETIONS_URL,
) -> str:
    """코디세이 OpenAI 호환 API를 호출하고 생성된 텍스트를 반환한다."""
    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    api_request = request.Request(
        api_url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(
            api_request, timeout=REQUEST_TIMEOUT_SECONDS
        ) as response:
            response_body = response.read()
    except error.HTTPError as api_error:
        reason = parse_api_error(api_error.read())
        if api_error.code in (401, 403):
            raise AIAPIError(f"AI API 인증 실패: {reason}") from api_error
        raise AIAPIError(
            f"AI API 요청 실패(HTTP {api_error.code}): {reason}"
        ) from api_error
    except (error.URLError, TimeoutError, socket.timeout) as network_error:
        raise AIAPIError(
            f"AI API 네트워크 오류: {network_error}"
        ) from network_error

    try:
        response_data = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as response_error:
        raise AIAPIError(
            "AI API 응답을 JSON 형식으로 해석할 수 없습니다."
        ) from response_error

    return extract_response_text(response_data)
