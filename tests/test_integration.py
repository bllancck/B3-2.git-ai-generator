"""실제 Git 저장소를 사용하는 CLI 통합 테스트."""

import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import error

import main


class MockAPIResponse:
    """통합 테스트에서 사용할 OpenAI 호환 응답 객체."""

    def __init__(self, generated_text: str):
        self.body = json.dumps(
            {
                "choices": [
                    {"message": {"content": generated_text}},
                ]
            }
        ).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self) -> bytes:
        return self.body


class CLIFullFlowIntegrationTest(unittest.TestCase):
    """Git 수집부터 최종 출력까지 한 번에 연결해서 확인한다."""

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repo_path = Path(self.temporary_directory.name)
        self.sample_path = self.repo_path / "sample.py"
        self.env_path = self.repo_path / ".env"

        self.run_git("init", "-q")
        (self.repo_path / ".gitignore").write_text(
            ".env\n", encoding="utf-8"
        )
        self.sample_path.write_text(
            'def greeting():\n    return "hello"\n',
            encoding="utf-8",
        )
        self.run_git("add", ".gitignore", "sample.py")
        self.run_git(
            "-c",
            "user.name=Integration Test",
            "-c",
            "user.email=integration@example.com",
            "commit",
            "-q",
            "-m",
            "initial",
        )
        self.env_path.write_text(
            "AI_API_KEY=integration-secret\n", encoding="utf-8"
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def run_git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
            text=True,
        )

    def invoke_cli(
        self,
        arguments: list[str],
        *,
        response: MockAPIResponse | None = None,
        api_error: Exception | None = None,
        cwd: Path | None = None,
        env_path: Path | None = None,
    ):
        stdout = io.StringIO()
        stderr = io.StringIO()
        environment_without_key = {
            name: value
            for name, value in os.environ.items()
            if name != "AI_API_KEY"
        }
        original_directory = Path.cwd()
        execution_directory = cwd or self.repo_path
        dotenv_path = env_path or self.env_path

        try:
            os.chdir(execution_directory)
            with (
                patch("sys.argv", ["main.py", *arguments]),
                patch.object(main, "ENV_FILE_PATH", dotenv_path),
                patch.dict(
                    os.environ,
                    environment_without_key,
                    clear=True,
                ),
                patch(
                    "main.request.urlopen",
                    return_value=response,
                    side_effect=api_error,
                ) as urlopen,
                patch("sys.stdout", stdout),
                patch("sys.stderr", stderr),
            ):
                exit_code = main.main()
        finally:
            os.chdir(original_directory)

        return exit_code, stdout.getvalue(), stderr.getvalue(), urlopen

    def test_commit_flow_connects_git_env_options_api_and_output(self):
        self.sample_path.write_text(
            'def greeting():\n    return "hello"\n\n'
            'def farewell():\n    return "bye"\n',
            encoding="utf-8",
        )

        exit_code, stdout, stderr, urlopen = self.invoke_cli(
            [
                "commit",
                "--model",
                "integration-model",
                "--temperature",
                "0.6",
                "--max-tokens",
                "444",
            ],
            response=MockAPIResponse("인사 모듈에 작별 인사 함수 추가"),
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        urlopen.assert_called_once()
        sent_request = urlopen.call_args.args[0]
        payload = json.loads(sent_request.data.decode("utf-8"))
        prompt = payload["messages"][0]["content"]
        self.assertEqual(
            sent_request.get_header("Authorization"),
            "Bearer integration-secret",
        )
        self.assertEqual(payload["model"], "integration-model")
        self.assertEqual(payload["temperature"], 0.6)
        self.assertEqual(payload["max_tokens"], 444)
        self.assertIn("sample.py", prompt)
        self.assertIn("+def farewell():", prompt)
        self.assertIn("[INFO] Git status 수집 완료: 1개 파일 변경 감지", stdout)
        self.assertIn("[INFO] Git diff 수집 완료", stdout)
        self.assertIn("[INFO] AI API 호출 횟수: 1회", stdout)
        self.assertIn(
            "--- Commit Message ---\n"
            "인사 모듈에 작별 인사 함수 추가\n"
            "----------------------",
            stdout,
        )

    def test_pr_safe_mode_masks_diff_and_normalizes_generated_draft(self):
        fake_key = "sk-integrationSecret1234"
        fake_email = "student@example.com"
        self.sample_path.write_text(
            'def greeting():\n    return "hello"\n\n'
            f'API_KEY = "{fake_key}"\n'
            f'CONTACT = "{fake_email}"\n',
            encoding="utf-8",
        )
        long_title = "통" * 81
        draft = (
            f"{long_title}\n"
            "Why\n변경 배경 확인\n"
            "What\n민감정보 마스킹 확인\n"
            "How to Test\n통합 테스트 실행"
        )

        exit_code, stdout, stderr, urlopen = self.invoke_cli(
            ["pr", "--safe-mode"],
            response=MockAPIResponse(draft),
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        urlopen.assert_called_once()
        sent_request = urlopen.call_args.args[0]
        payload = json.loads(sent_request.data.decode("utf-8"))
        prompt = payload["messages"][0]["content"]
        self.assertNotIn(fake_key, prompt)
        self.assertNotIn(fake_email, prompt)
        self.assertIn("[MASKED_SECRET]", prompt)
        self.assertIn("[MASKED_EMAIL]", prompt)
        self.assertIn("[INFO] safe-mode 적용: 민감정보 2건 마스킹", stdout)
        self.assertNotIn(fake_key, stdout)
        self.assertNotIn(fake_email, stdout)
        self.assertIn("[MASKED_SECRET]", stdout)
        self.assertIn("[MASKED_EMAIL]", stdout)
        self.assertIn("[WARN] PR 제목이 80자를 넘어", stdout)
        self.assertIn(
            f"--- PR Title ---\n{main.shorten_title(long_title, 80)}",
            stdout,
        )
        self.assertIn("## Why\n- 변경 배경 확인", stdout)
        self.assertIn("## What\n- 민감정보 마스킹 확인", stdout)
        self.assertIn("## How to Test\n- 통합 테스트 실행", stdout)
        self.assertTrue(stdout.rstrip().endswith("----------------------"))

    def test_clean_repository_stops_without_api_request(self):
        exit_code, stdout, stderr, urlopen = self.invoke_cli(["commit"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        urlopen.assert_not_called()
        self.assertIn("변경 사항이 없습니다", stdout)
        self.assertIn("[INFO] AI API 호출 횟수: 0회", stdout)

    def test_missing_api_key_stops_before_api_request(self):
        self.sample_path.write_text(
            'def greeting():\n    return "changed"\n', encoding="utf-8"
        )
        missing_env_path = self.repo_path / "missing.env"

        exit_code, stdout, stderr, urlopen = self.invoke_cli(
            ["commit"], env_path=missing_env_path
        )

        self.assertEqual(exit_code, 1)
        urlopen.assert_not_called()
        self.assertIn("AI_API_KEY 환경변수가 설정되지 않았습니다", stderr)
        self.assertIn("[INFO] AI API 호출 횟수: 0회", stdout)

    def test_authentication_and_network_failures_include_the_cause(self):
        self.sample_path.write_text(
            'def greeting():\n    return "changed"\n', encoding="utf-8"
        )
        failures = (
            (
                error.HTTPError(
                    main.CODYSSEY_CHAT_COMPLETIONS_URL,
                    401,
                    "Unauthorized",
                    {},
                    io.BytesIO(
                        json.dumps(
                            {"error": {"message": "잘못된 테스트 Key"}}
                        ).encode("utf-8")
                    ),
                ),
                "AI API 인증 실패: 잘못된 테스트 Key",
            ),
            (error.URLError("테스트 연결 끊김"), "AI API 네트워크 오류"),
        )

        for api_error, expected_message in failures:
            with self.subTest(expected_message=expected_message):
                exit_code, stdout, stderr, urlopen = self.invoke_cli(
                    ["commit"], api_error=api_error
                )

                self.assertEqual(exit_code, 1)
                urlopen.assert_called_once()
                self.assertIn(expected_message, stderr)
                self.assertIn("[INFO] AI API 호출 횟수: 1회", stdout)

    def test_non_git_directory_reports_git_error_without_api_request(self):
        with tempfile.TemporaryDirectory() as directory:
            non_git_path = Path(directory)
            exit_code, stdout, stderr, urlopen = self.invoke_cli(
                ["pr"], cwd=non_git_path
            )

        self.assertEqual(exit_code, 1)
        urlopen.assert_not_called()
        self.assertIn("[ERROR]", stderr)
        self.assertIn("git status --short", stderr)
        self.assertIn("[INFO] AI API 호출 횟수: 0회", stdout)


if __name__ == "__main__":
    unittest.main()
