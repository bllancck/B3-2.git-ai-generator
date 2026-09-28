"""commit 및 pr 명령의 옵션을 정의한다."""

import argparse

from .ai import DEFAULT_MODEL, DEFAULT_TEMPERATURE, DEFAULT_MAX_OUTPUT_TOKENS


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
        help="AI 전송과 터미널 출력 전에 API Key, 인증값, 이메일 등 민감정보를 마스킹",
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
