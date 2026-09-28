"""AI 응답의 커밋 제목과 PR 본문 형식을 검증한다."""

COMMIT_RECOMMENDED_TITLE_LENGTH = 50


COMMIT_MAX_TITLE_LENGTH = 72


PR_MAX_TITLE_LENGTH = 80


PR_SECTION_NAMES = ("Why", "What", "How to Test")


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
