"""현재 Git 작업 트리의 변경 사항을 수집한다."""

import subprocess

from .errors import GitCommandError


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
