"""AI 기반 Git 커밋/PR 자동 생성기의 CLI 진입점."""

import sys
from urllib import request

from gitgen.ai import (
    CODYSSEY_CHAT_COMPLETIONS_URL,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    call_ai_api,
    extract_response_text,
    parse_api_error,
)
from gitgen.cli import (
    add_ai_options,
    create_parser,
    non_empty_model,
    positive_integer,
    temperature_value,
)
from gitgen.config import ENV_FILE_PATH, get_api_key as _get_api_key
from gitgen.errors import AIAPIError, ConfigurationError, GitCommandError
from gitgen.gitctx import collect_git_changes, extract_changed_files, run_git_command
from gitgen.postprocess import (
    COMMIT_MAX_TITLE_LENGTH,
    COMMIT_RECOMMENDED_TITLE_LENGTH,
    PR_MAX_TITLE_LENGTH,
    PR_SECTION_NAMES,
    normalize_section_heading,
    shorten_title,
    split_pr_draft,
    validate_commit_message,
    validate_pr_draft,
)
from gitgen.prompts import build_commit_prompt, build_pr_prompt
from gitgen.render import (
    RESULT_SEPARATOR,
    print_commit_result,
    print_git_changes,
    print_pr_result,
)
from gitgen.sanitizer import (
    SENSITIVE_PATTERNS,
    mask_changes_for_safe_mode,
    mask_sensitive_text,
)


MAX_API_CALLS_PER_COMMAND = 1


def get_api_key() -> str:
    """프로젝트의 .env 경로에서 API Key를 읽는다."""
    return _get_api_key(ENV_FILE_PATH)


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
    prompt_files = changed_files
    prompt_diff = diff_output
    if args.safe_mode:
        prompt_files, prompt_diff, masked_count = (
            mask_changes_for_safe_mode(changed_files, diff_output)
        )
        print(f"\n[INFO] safe-mode 적용: 민감정보 {masked_count}건 마스킹")
    print_git_changes(prompt_files, prompt_diff)

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
        print_commit_result(generated_text)
    else:
        print_pr_result(generated_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
