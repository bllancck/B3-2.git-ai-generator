"""Git 변경 사항으로 AI 요청 문구를 만든다."""


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
