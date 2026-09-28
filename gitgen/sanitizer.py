"""AI 입력과 터미널 출력에 사용할 민감정보 마스킹."""

import re


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
