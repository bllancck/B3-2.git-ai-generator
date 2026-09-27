"""AI 기반 Git 커밋/PR 자동 생성기의 CLI 진입점."""

import argparse
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from urllib import error, request

from dotenv import load_dotenv


CODYSSEY_CHAT_COMPLETIONS_URL = (
    "https://copa.codyssey.kr/v1/chat/completions"
)
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_OUTPUT_TOKENS = 300
REQUEST_TIMEOUT_SECONDS = 30
COMMIT_RECOMMENDED_TITLE_LENGTH = 50
COMMIT_MAX_TITLE_LENGTH = 72
PR_MAX_TITLE_LENGTH = 80
PR_SECTION_NAMES = ("Why", "What", "How to Test")
MAX_API_CALLS_PER_COMMAND = 1
RESULT_SEPARATOR = "----------------------"
ENV_FILE_PATH = Path(__file__).resolve().parent / ".env"
SENSITIVE_PATTERNS = (
    (
        re.compile(
            r'''(?ix)
            (["']?(?:api[_-]?key|access[_-]?token|token|secret|password)["']?
            \s*[:=]\s*["']?)
            ([^\s,"']+)
            '''
        ),
        r"\1[MASKED_SECRET]",
    ),
    (
        re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/-]+"),
        r"\1[MASKED_TOKEN]",
    ),
    (
        re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
        "[MASKED_API_KEY]",
    ),
    (
        re.compile(
            r"\b[A-Za-z0-9.!#$%&'*+=?^_`{|}~-]+@"
            r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
            r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+\b"
        ),
        "[MASKED_EMAIL]",
    ),
)


class GitCommandError(RuntimeError):
    """Git 명령을 실행하지 못했을 때 발생하는 오류."""


class ConfigurationError(RuntimeError):
    """프로그램 실행에 필요한 설정이 올바르지 않을 때 발생하는 오류."""


class AIAPIError(RuntimeError):
    """AI API 요청 또는 응답 처리에 실패했을 때 발생하는 오류."""


def get_api_key() -> str:
    """.env 또는 기존 환경변수에서 AI API Key를 읽고 검사한다."""
    load_dotenv(dotenv_path=ENV_FILE_PATH, override=False)
    api_key = os.getenv("AI_API_KEY")
    if api_key is None or not api_key.strip():
        raise ConfigurationError("AI_API_KEY 환경변수가 설정되지 않았습니다.")
    return api_key


def build_basic_prompt(
    command: str, changed_files: list[str], diff_output: str
) -> str:
    """API 연결을 확인하기 위한 기본 Git 변경 요약 요청을 만든다."""
    file_list = "\n".join(f"- {path}" for path in changed_files)
    diff_text = diff_output.strip() or "(diff 내용 없음)"
    return (
        "다음 Git 변경 사항을 한국어 한 문장으로 간단히 요약하세요.\n"
        f"요청 명령: {command}\n\n"
        f"변경 파일:\n{file_list}\n\n"
        f"Git diff:\n{diff_text}"
    )


def build_commit_prompt(changed_files: list[str], diff_output: str) -> str:
    """Git 변경 내용을 기반으로 커밋 제목 한 줄을 요청한다."""
    file_list = "\n".join(f"- {path}" for path in changed_files)
    diff_text = diff_output.strip() or "(diff 내용 없음)"
    return (
        "다음 Git 변경 사항만 근거로 한국어 커밋 메시지를 작성하세요.\n"
        "규칙:\n"
        "- 변경의 핵심을 요약한 간결한 제목 한 줄만 작성하세요.\n"
        "- 제목 앞에 '커밋 메시지:' 같은 설명이나 마크다운을 붙이지 마세요.\n"
        "- 제공되지 않은 변경 내용을 추측하지 마세요.\n\n"
        f"변경 파일:\n{file_list}\n\n"
        f"Git diff:\n{diff_text}"
    )


def build_pr_prompt(changed_files: list[str], diff_output: str) -> str:
    """Git 변경 내용을 기반으로 PR 제목과 본문 초안을 요청한다."""
    file_list = "\n".join(f"- {path}" for path in changed_files)
    diff_text = diff_output.strip() or "(diff 내용 없음)"
    return (
        "다음 Git 변경 사항만 근거로 한국어 Pull Request 초안을 작성하세요.\n"
        "아래 형식을 정확히 따르세요.\n\n"
        "<PR 제목 한 줄>\n"
        "## Why\n"
        "- <변경 배경을 설명하는 내용>\n"
        "## What\n"
        "- <핵심 변경 사항>\n"
        "## How to Test\n"
        "- <변경 사항을 확인하는 방법>\n\n"
        "규칙:\n"
        "- 첫 줄에는 간결한 PR 제목만 작성하세요.\n"
        "- Why, What, How to Test에 각각 불릿을 한 개 이상 작성하세요.\n"
        "- 제목이나 본문을 코드 블록으로 감싸지 마세요.\n"
        "- 제공되지 않은 변경 내용이나 테스트 결과를 추측하지 마세요.\n"
        "- 테스트 방법을 알 수 없다면 '사용자 확인 필요'라고 작성하세요.\n\n"
        f"변경 파일:\n{file_list}\n\n"
        f"Git diff:\n{diff_text}"
    )


def split_pr_draft(generated_text: str) -> tuple[str, str]:
    """AI 응답의 첫 줄을 PR 제목으로, 나머지를 본문으로 나눈다."""
    lines = generated_text.strip().splitlines()
    title = lines[0].strip()
    body = "\n".join(lines[1:]).strip()
    return title, body


def shorten_title(title: str, maximum_length: int) -> str:
    """제목을 최대 길이 안으로 줄이고 말줄임표를 붙인다."""
    if len(title) <= maximum_length:
        return title
    return f"{title[:maximum_length - 3].rstrip()}..."


def validate_commit_message(generated_text: str) -> tuple[str, list[str]]:
    """커밋 제목 길이를 확인하고 필요한 경우 후처리한다."""
    title = generated_text.strip().splitlines()[0].strip()
    warnings: list[str] = []

    if len(title) > COMMIT_MAX_TITLE_LENGTH:
        title = shorten_title(title, COMMIT_MAX_TITLE_LENGTH)
        warnings.append(
            f"커밋 제목이 {COMMIT_MAX_TITLE_LENGTH}자를 넘어 자동으로 줄였습니다."
        )
    elif len(title) > COMMIT_RECOMMENDED_TITLE_LENGTH:
        warnings.append(
            f"커밋 제목이 권장 길이 {COMMIT_RECOMMENDED_TITLE_LENGTH}자를 넘습니다."
        )

    return title, warnings


def normalize_section_heading(line: str) -> str | None:
    """PR 섹션 헤더를 표준 이름으로 변환한다."""
    normalized = line.strip().lstrip("#").strip().rstrip(":").strip().lower()
    headings = {name.lower(): name for name in PR_SECTION_NAMES}
    return headings.get(normalized)


def validate_pr_draft(
    generated_text: str,
) -> tuple[str, str, list[str]]:
    """PR 제목과 필수 본문 구조를 확인하고 정해진 형식으로 보완한다."""
    title, body = split_pr_draft(generated_text)
    warnings: list[str] = []

    if len(title) > PR_MAX_TITLE_LENGTH:
        title = shorten_title(title, PR_MAX_TITLE_LENGTH)
        warnings.append(
            f"PR 제목이 {PR_MAX_TITLE_LENGTH}자를 넘어 자동으로 줄였습니다."
        )

    sections: dict[str, list[tuple[str, bool]]] = {
        name: [] for name in PR_SECTION_NAMES
    }
    found_sections: set[str] = set()
    current_section: str | None = None

    for line in body.splitlines():
        heading = normalize_section_heading(line)
        if heading is not None:
            current_section = heading
            found_sections.add(heading)
            continue

        content = line.strip()
        if not content or current_section is None:
            continue

        has_bullet = content.startswith(("- ", "* ", "+ "))
        if has_bullet:
            content = content[2:].strip()
        if content:
            sections[current_section].append((content, has_bullet))

    normalized_sections: list[str] = []
    for section_name in PR_SECTION_NAMES:
        entries = sections[section_name]
        if section_name not in found_sections:
            warnings.append(f"PR 본문에 {section_name} 섹션을 추가했습니다.")
        elif entries and not any(has_bullet for _, has_bullet in entries):
            warnings.append(
                f"PR 본문의 {section_name} 내용을 불릿 형식으로 바꿨습니다."
            )

        bullets = [f"- {content}" for content, _ in entries]
        if not bullets:
            bullets = ["- 사용자 확인 필요"]
            warnings.append(
                f"PR 본문의 {section_name} 섹션에 확인용 불릿을 추가했습니다."
            )

        normalized_sections.append(
            f"## {section_name}\n" + "\n".join(bullets)
        )

    return title, "\n\n".join(normalized_sections), warnings


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


def run_git_command(*args: str) -> str:
    """Git 명령을 실행하고 표준 출력 내용을 반환한다."""
    command = ["git", *args]

    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise GitCommandError("Git 실행 파일을 찾을 수 없습니다.") from error
    except subprocess.CalledProcessError as error:
        reason = error.stderr.strip() or "알 수 없는 Git 오류가 발생했습니다."
        raise GitCommandError(
            f"`{' '.join(command)}` 실행 실패: {reason}"
        ) from error

    return result.stdout


def extract_changed_files(status_output: str) -> list[str]:
    """`git status --short` 출력에서 변경된 파일 표시를 추출한다."""
    return [line[3:] for line in status_output.splitlines() if len(line) >= 4]


def collect_git_changes() -> tuple[list[str], str]:
    """현재 저장소의 변경 파일 목록과 diff 내용을 수집한다."""
    status_output = run_git_command("status", "--short")
    diff_output = run_git_command("diff")
    changed_files = extract_changed_files(status_output)
    return changed_files, diff_output


def print_git_changes(changed_files: list[str], diff_output: str) -> None:
    """수집한 Git 변경 정보를 확인할 수 있도록 출력한다."""
    print(f"[INFO] Git status 수집 완료: {len(changed_files)}개 파일 변경 감지")
    print("[INFO] Git diff 수집 완료")

    print("\n--- Changed Files ---")
    if changed_files:
        for file_path in changed_files:
            print(f"- {file_path}")
    else:
        print("(변경된 파일 없음)")

    print("\n--- Git Diff ---")
    print(diff_output.rstrip() or "(diff 내용 없음)")


def mask_sensitive_text(text: str) -> tuple[str, int]:
    """알려진 민감정보 패턴을 대체 문자열로 바꾼다."""
    masked_text = text
    masked_count = 0
    for pattern, replacement in SENSITIVE_PATTERNS:
        masked_text, replacement_count = pattern.subn(replacement, masked_text)
        masked_count += replacement_count
    return masked_text, masked_count


def mask_changes_for_safe_mode(
    changed_files: list[str], diff_output: str
) -> tuple[list[str], str, int]:
    """변경 파일명과 diff에서 민감정보 패턴을 마스킹한다."""
    masked_files: list[str] = []
    masked_count = 0
    for file_path in changed_files:
        masked_path, path_count = mask_sensitive_text(file_path)
        masked_files.append(masked_path)
        masked_count += path_count

    masked_diff, diff_count = mask_sensitive_text(diff_output)
    masked_count += diff_count
    return masked_files, masked_diff, masked_count


def non_empty_model(value: str) -> str:
    """빈 모델 이름이 API 요청에 전달되지 않도록 검사한다."""
    model = value.strip()
    if not model:
        raise argparse.ArgumentTypeError("모델 이름은 비워 둘 수 없습니다.")
    return model


def temperature_value(value: str) -> float:
    """temperature가 API에서 사용하는 0~2 범위인지 검사한다."""
    try:
        temperature = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "temperature는 숫자여야 합니다."
        ) from error

    if not 0 <= temperature <= 2:
        raise argparse.ArgumentTypeError(
            "temperature는 0 이상 2 이하이어야 합니다."
        )
    return temperature


def positive_integer(value: str) -> int:
    """max-tokens가 1 이상의 정수인지 검사한다."""
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "max-tokens는 정수여야 합니다."
        ) from error

    if number < 1:
        raise argparse.ArgumentTypeError(
            "max-tokens는 1 이상이어야 합니다."
        )
    return number


def add_ai_options(command_parser: argparse.ArgumentParser) -> None:
    """commit과 pr 명령에서 공통으로 사용할 AI 옵션을 추가한다."""
    command_parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        type=non_empty_model,
        help=f"AI 모델 이름 (기본값: {DEFAULT_MODEL})",
    )
    command_parser.add_argument(
        "--temperature",
        default=DEFAULT_TEMPERATURE,
        type=temperature_value,
        help=f"응답의 무작위성, 0~2 (기본값: {DEFAULT_TEMPERATURE})",
    )
    command_parser.add_argument(
        "--max-tokens",
        default=DEFAULT_MAX_OUTPUT_TOKENS,
        type=positive_integer,
        help=f"응답 최대 토큰 수, 1 이상 (기본값: {DEFAULT_MAX_OUTPUT_TOKENS})",
    )
    command_parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="AI 전송 전에 API Key, 인증값, 이메일 등 민감정보를 마스킹",
    )


def create_parser() -> argparse.ArgumentParser:
    """프로그램에서 사용할 명령행 인자 파서를 만든다."""
    parser = argparse.ArgumentParser(
        description="Git 변경 사항을 바탕으로 커밋 메시지와 PR 초안을 생성합니다."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    commit_parser = subparsers.add_parser(
        "commit", help="커밋 메시지 생성을 선택합니다."
    )
    pr_parser = subparsers.add_parser("pr", help="PR 초안 생성을 선택합니다.")
    add_ai_options(commit_parser)
    add_ai_options(pr_parser)
    return parser


def main() -> int:
    """CLI 명령을 읽고 현재 Git 변경 사항을 수집한다."""
    args = create_parser().parse_args()
    api_call_count = 0

    print(f"[INFO] 실행 명령: {args.command}")

    try:
        changed_files, diff_output = collect_git_changes()
    except GitCommandError as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        print(f"[INFO] AI API 호출 횟수: {api_call_count}회")
        return 1

    if not changed_files and not diff_output.strip():
        print("[INFO] 변경 사항이 없습니다. 생성을 진행하지 않고 종료합니다.")
        print(f"[INFO] AI API 호출 횟수: {api_call_count}회")
        return 0

    try:
        api_key = get_api_key()
    except ConfigurationError as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        print(f"[INFO] AI API 호출 횟수: {api_call_count}회")
        return 1

    print("[INFO] AI_API_KEY 환경변수를 확인했습니다.")
    print_git_changes(changed_files, diff_output)

    prompt_files = changed_files
    prompt_diff = diff_output
    if args.safe_mode:
        prompt_files, prompt_diff, masked_count = (
            mask_changes_for_safe_mode(changed_files, diff_output)
        )
        print(f"\n[INFO] safe-mode 적용: 민감정보 {masked_count}건 마스킹")

    if args.command == "commit":
        prompt = build_commit_prompt(prompt_files, prompt_diff)
    else:
        prompt = build_pr_prompt(prompt_files, prompt_diff)
    api_call_count += 1
    print(
        f"\n[INFO] AI API 요청 중... "
        f"({api_call_count}/{MAX_API_CALLS_PER_COMMAND})"
    )
    try:
        generated_text = call_ai_api(
            api_key,
            prompt,
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
    except AIAPIError as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        print(f"[INFO] AI API 호출 횟수: {api_call_count}회")
        return 1

    print(f"[INFO] AI API 호출 횟수: {api_call_count}회")
    if args.command == "commit":
        commit_title, warnings = validate_commit_message(generated_text)
        for warning in warnings:
            print(f"[WARN] {warning}")
        print("[DONE] 커밋 메시지 생성 완료")
        print("\n--- Commit Message ---")
        print(commit_title)
        print(RESULT_SEPARATOR)
    else:
        pr_title, pr_body, warnings = validate_pr_draft(generated_text)
        for warning in warnings:
            print(f"[WARN] {warning}")
        print("[DONE] PR 초안 생성 완료")
        print("\n--- PR Title ---")
        print(pr_title)
        print("\n--- PR Body ---")
        print(pr_body)
        print(RESULT_SEPARATOR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
