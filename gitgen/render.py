"""Git 변경 사항과 생성 결과를 터미널에 출력한다."""

from .postprocess import validate_commit_message, validate_pr_draft


RESULT_SEPARATOR = "----------------------"


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


def print_commit_result(generated_text: str) -> None:
    """커밋 제목과 형식 경고를 출력한다."""
    commit_title, warnings = validate_commit_message(generated_text)
    for warning in warnings:
        print(f"[WARN] {warning}")
    print("[DONE] 커밋 메시지 생성 완료")
    print("\n--- Commit Message ---")
    print(commit_title)
    print(RESULT_SEPARATOR)


def print_pr_result(generated_text: str) -> None:
    """PR 제목과 본문, 형식 경고를 출력한다."""
    pr_title, pr_body, warnings = validate_pr_draft(generated_text)
    for warning in warnings:
        print(f"[WARN] {warning}")
    print("[DONE] PR 초안 생성 완료")
    print("\n--- PR Title ---")
    print(pr_title)
    print("\n--- PR Body ---")
    print(pr_body)
    print(RESULT_SEPARATOR)
