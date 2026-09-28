"""AI API 기본 호출, 오류 처리, CLI 파라미터 테스트."""

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import error

import main


class MockResponse:
    """urlopen 응답처럼 사용할 수 있는 최소 테스트 객체."""

    def __init__(self, body: dict | bytes):
        if isinstance(body, dict):
            body = json.dumps(body).encode("utf-8")
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self) -> bytes:
        return self.body


class APIKeyConfigurationTest(unittest.TestCase):
    def test_loads_api_key_from_dotenv_file(self):
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text("AI_API_KEY=file-secret\n", encoding="utf-8")

            with (
                patch.object(main, "ENV_FILE_PATH", env_path),
                patch.dict(os.environ, {}, clear=True),
            ):
                api_key = main.get_api_key()

        self.assertEqual(api_key, "file-secret")

    def test_existing_environment_variable_has_priority(self):
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text("AI_API_KEY=file-secret\n", encoding="utf-8")

            with (
                patch.object(main, "ENV_FILE_PATH", env_path),
                patch.dict(
                    os.environ,
                    {"AI_API_KEY": "terminal-secret"},
                    clear=True,
                ),
            ):
                api_key = main.get_api_key()

        self.assertEqual(api_key, "terminal-secret")

    def test_reports_missing_key_when_dotenv_file_does_not_exist(self):
        missing_path = Path("/path/that/does/not/exist/.env")

        with (
            patch.object(main, "ENV_FILE_PATH", missing_path),
            patch.dict(os.environ, {}, clear=True),
        ):
            with self.assertRaisesRegex(
                main.ConfigurationError,
                "AI_API_KEY 환경변수가 설정되지 않았습니다",
            ):
                main.get_api_key()


class CallAIAPITest(unittest.TestCase):
    def test_returns_generated_text_without_exposing_key(self):
        response = MockResponse(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "변경 사항 요약",
                        }
                    }
                ]
            }
        )

        with patch("main.request.urlopen", return_value=response) as urlopen:
            result = main.call_ai_api(
                "dummy-secret", "테스트 프롬프트", api_url="https://example.test"
            )

        self.assertEqual(result, "변경 사항 요약")
        sent_request = urlopen.call_args.args[0]
        self.assertEqual(sent_request.get_method(), "POST")
        self.assertEqual(
            sent_request.get_header("Authorization"), "Bearer dummy-secret"
        )
        request_data = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(request_data["model"], main.DEFAULT_MODEL)
        self.assertEqual(
            request_data["messages"],
            [{"role": "user", "content": "테스트 프롬프트"}],
        )
        self.assertEqual(
            request_data["max_tokens"], main.DEFAULT_MAX_OUTPUT_TOKENS
        )
        self.assertEqual(
            request_data["temperature"], main.DEFAULT_TEMPERATURE
        )
        self.assertFalse(request_data["stream"])

    def test_applies_custom_parameters_to_request(self):
        response = MockResponse(
            {
                "choices": [
                    {"message": {"content": "사용자 지정 파라미터 응답"}}
                ]
            }
        )

        with patch("main.request.urlopen", return_value=response) as urlopen:
            main.call_ai_api(
                "dummy-secret",
                "테스트 프롬프트",
                model="custom-model",
                temperature=0.7,
                max_tokens=500,
                api_url="https://example.test",
            )

        sent_request = urlopen.call_args.args[0]
        request_data = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(request_data["model"], "custom-model")
        self.assertEqual(request_data["temperature"], 0.7)
        self.assertEqual(request_data["max_tokens"], 500)

    def test_reports_authentication_failure(self):
        api_error = error.HTTPError(
            "https://example.test",
            401,
            "Unauthorized",
            {},
            io.BytesIO(
                json.dumps(
                    {"error": {"message": "잘못된 인증 정보"}}
                ).encode("utf-8")
            ),
        )

        with patch("main.request.urlopen", side_effect=api_error):
            with self.assertRaisesRegex(main.AIAPIError, "인증 실패"):
                main.call_ai_api(
                    "dummy-secret", "테스트", api_url="https://example.test"
                )

    def test_reports_network_failure(self):
        with patch(
            "main.request.urlopen",
            side_effect=error.URLError("연결할 수 없음"),
        ):
            with self.assertRaisesRegex(main.AIAPIError, "네트워크 오류"):
                main.call_ai_api(
                    "dummy-secret", "테스트", api_url="https://example.test"
                )

    def test_reports_other_http_failure(self):
        api_error = error.HTTPError(
            "https://example.test",
            500,
            "Server Error",
            {},
            io.BytesIO(
                json.dumps(
                    {"error": {"message": "일시적인 서버 오류"}}
                ).encode("utf-8")
            ),
        )

        with patch("main.request.urlopen", side_effect=api_error):
            with self.assertRaisesRegex(
                main.AIAPIError, "HTTP 500.*일시적인 서버 오류"
            ):
                main.call_ai_api(
                    "dummy-secret", "테스트", api_url="https://example.test"
                )

    def test_reports_invalid_response(self):
        with patch(
            "main.request.urlopen",
            return_value=MockResponse(b"not-json"),
        ):
            with self.assertRaisesRegex(main.AIAPIError, "JSON 형식"):
                main.call_ai_api(
                    "dummy-secret", "테스트", api_url="https://example.test"
                )


class CLIOptionsTest(unittest.TestCase):
    def test_uses_default_ai_parameters(self):
        args = main.create_parser().parse_args(["commit"])

        self.assertEqual(main.DEFAULT_MODEL, "gpt-5.4-mini")
        self.assertEqual(args.model, main.DEFAULT_MODEL)
        self.assertEqual(args.temperature, main.DEFAULT_TEMPERATURE)
        self.assertEqual(args.max_tokens, main.DEFAULT_MAX_OUTPUT_TOKENS)
        self.assertFalse(args.safe_mode)

    def test_reads_custom_ai_parameters(self):
        args = main.create_parser().parse_args(
            [
                "pr",
                "--model",
                "custom-model",
                "--temperature",
                "0.7",
                "--max-tokens",
                "500",
            ]
        )

        self.assertEqual(args.model, "custom-model")
        self.assertEqual(args.temperature, 0.7)
        self.assertEqual(args.max_tokens, 500)

    def test_main_passes_cli_parameters_to_api(self):
        with (
            patch(
                "sys.argv",
                [
                    "main.py",
                    "commit",
                    "--model",
                    "custom-model",
                    "--temperature",
                    "0.7",
                    "--max-tokens",
                    "500",
                ],
            ),
            patch(
                "main.collect_git_changes",
                return_value=(["main.py"], "diff 내용"),
            ),
            patch("main.get_api_key", return_value="dummy-secret"),
            patch("main.print_git_changes"),
            patch("main.build_commit_prompt", return_value="테스트 프롬프트"),
            patch("main.call_ai_api", return_value="테스트 응답") as call_api,
            patch("builtins.print"),
        ):
            exit_code = main.main()

        self.assertEqual(exit_code, 0)
        call_api.assert_called_once_with(
            "dummy-secret",
            "테스트 프롬프트",
            model="custom-model",
            temperature=0.7,
            max_tokens=500,
        )

    def test_rejects_out_of_range_values(self):
        parser = main.create_parser()

        with patch("sys.stderr"):
            with self.assertRaises(SystemExit):
                parser.parse_args(["commit", "--temperature", "2.1"])
            with self.assertRaises(SystemExit):
                parser.parse_args(["pr", "--max-tokens", "0"])


class CommitGenerationTest(unittest.TestCase):
    def test_commit_prompt_contains_git_changes_and_title_rules(self):
        prompt = main.build_commit_prompt(
            ["main.py", "README.md"],
            "diff --git a/main.py b/main.py\n+새로운 변경 내용",
        )

        self.assertIn("- main.py", prompt)
        self.assertIn("- README.md", prompt)
        self.assertIn("새로운 변경 내용", prompt)
        self.assertIn("제목 한 줄만", prompt)
        self.assertIn("제공되지 않은 변경 내용을 추측하지 마세요", prompt)

    def test_commit_command_prints_copyable_commit_message(self):
        stdout = io.StringIO()
        with (
            patch("sys.argv", ["main.py", "commit"]),
            patch(
                "main.collect_git_changes",
                return_value=(["main.py"], "diff 내용"),
            ),
            patch("main.get_api_key", return_value="dummy-secret"),
            patch("main.print_git_changes"),
            patch(
                "main.call_ai_api",
                return_value="CLI 옵션을 API 요청에 반영",
            ) as call_api,
            patch("sys.stdout", stdout),
        ):
            exit_code = main.main()

        self.assertEqual(exit_code, 0)
        sent_prompt = call_api.call_args.args[1]
        self.assertIn("main.py", sent_prompt)
        self.assertIn("diff 내용", sent_prompt)
        output = stdout.getvalue()
        self.assertIn("[INFO] 실행 명령: commit", output)
        self.assertIn("[INFO] AI API 요청 중... (1/1)", output)
        self.assertIn("[INFO] AI API 호출 횟수: 1회", output)
        self.assertIn("[DONE] 커밋 메시지 생성 완료", output)
        self.assertIn("--- Commit Message ---", output)
        self.assertIn(
            "--- Commit Message ---\n"
            "CLI 옵션을 API 요청에 반영\n"
            "----------------------",
            output,
        )
        self.assertNotIn("--- AI Response ---", output)


class PRGenerationTest(unittest.TestCase):
    def test_pr_prompt_contains_git_changes_and_required_sections(self):
        prompt = main.build_pr_prompt(
            ["main.py", "tests/test_ai_api.py"],
            "diff --git a/main.py b/main.py\n+PR 생성 기능 추가",
        )

        self.assertIn("- main.py", prompt)
        self.assertIn("- tests/test_ai_api.py", prompt)
        self.assertIn("PR 생성 기능 추가", prompt)
        self.assertIn("## Why", prompt)
        self.assertIn("## What", prompt)
        self.assertIn("## How to Test", prompt)
        self.assertIn("각각 불릿을 한 개 이상", prompt)
        self.assertIn("제공되지 않은 변경 내용이나 테스트 결과를 추측하지 마세요", prompt)

    def test_pr_command_prints_separate_title_and_body(self):
        generated_draft = (
            "PR 초안 생성 기능 추가\n\n"
            "## Why\n- Git 변경 내용을 PR 문서로 정리하기 위해\n\n"
            "## What\n- PR 전용 프롬프트와 출력을 추가\n\n"
            "## How to Test\n- 자동 테스트를 실행"
        )
        stdout = io.StringIO()
        with (
            patch("sys.argv", ["main.py", "pr"]),
            patch(
                "main.collect_git_changes",
                return_value=(["main.py"], "diff 내용"),
            ),
            patch("main.get_api_key", return_value="dummy-secret"),
            patch("main.print_git_changes"),
            patch("main.call_ai_api", return_value=generated_draft) as call_api,
            patch("sys.stdout", stdout),
        ):
            exit_code = main.main()

        self.assertEqual(exit_code, 0)
        sent_prompt = call_api.call_args.args[1]
        self.assertIn("main.py", sent_prompt)
        self.assertIn("diff 내용", sent_prompt)
        output = stdout.getvalue()
        self.assertIn("[INFO] 실행 명령: pr", output)
        self.assertIn("[INFO] AI API 요청 중... (1/1)", output)
        self.assertIn("[INFO] AI API 호출 횟수: 1회", output)
        self.assertIn("[DONE] PR 초안 생성 완료", output)
        self.assertIn("--- PR Title ---\nPR 초안 생성 기능 추가", output)
        self.assertIn("--- PR Body ---\n## Why", output)
        self.assertIn("## What", output)
        self.assertIn("## How to Test", output)
        self.assertTrue(output.rstrip().endswith("----------------------"))
        self.assertNotIn("--- AI Response ---", output)


class ExecutionLogTest(unittest.TestCase):
    def test_reports_zero_api_calls_when_there_are_no_changes(self):
        stdout = io.StringIO()

        with (
            patch("sys.argv", ["main.py", "commit"]),
            patch("main.collect_git_changes", return_value=([], "")),
            patch("main.get_api_key") as get_api_key,
            patch("main.call_ai_api") as call_api,
            patch("sys.stdout", stdout),
        ):
            exit_code = main.main()

        self.assertEqual(exit_code, 0)
        get_api_key.assert_not_called()
        call_api.assert_not_called()
        self.assertIn("[INFO] AI API 호출 횟수: 0회", stdout.getvalue())

    def test_reports_zero_api_calls_when_configuration_fails(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch("sys.argv", ["main.py", "pr"]),
            patch(
                "main.collect_git_changes",
                return_value=(["main.py"], "diff 내용"),
            ),
            patch(
                "main.get_api_key",
                side_effect=main.ConfigurationError("API Key 없음"),
            ),
            patch("main.call_ai_api") as call_api,
            patch("sys.stdout", stdout),
            patch("sys.stderr", stderr),
        ):
            exit_code = main.main()

        self.assertEqual(exit_code, 1)
        call_api.assert_not_called()
        self.assertIn("[INFO] AI API 호출 횟수: 0회", stdout.getvalue())
        self.assertIn("[ERROR] API Key 없음", stderr.getvalue())

    def test_reports_one_api_call_when_request_fails(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch("sys.argv", ["main.py", "commit"]),
            patch(
                "main.collect_git_changes",
                return_value=(["main.py"], "diff 내용"),
            ),
            patch("main.get_api_key", return_value="dummy-secret"),
            patch("main.print_git_changes"),
            patch(
                "main.call_ai_api",
                side_effect=main.AIAPIError("테스트 요청 실패"),
            ) as call_api,
            patch("sys.stdout", stdout),
            patch("sys.stderr", stderr),
        ):
            exit_code = main.main()

        self.assertEqual(exit_code, 1)
        call_api.assert_called_once()
        self.assertIn("[INFO] AI API 요청 중... (1/1)", stdout.getvalue())
        self.assertIn("[INFO] AI API 호출 횟수: 1회", stdout.getvalue())
        self.assertIn("[ERROR] 테스트 요청 실패", stderr.getvalue())


class OutputValidationTest(unittest.TestCase):
    def test_warns_when_commit_title_exceeds_recommended_length(self):
        title = "가" * 51

        validated_title, warnings = main.validate_commit_message(title)

        self.assertEqual(validated_title, title)
        self.assertTrue(any("권장 길이 50자" in warning for warning in warnings))

    def test_shortens_commit_title_over_maximum_length(self):
        validated_title, warnings = main.validate_commit_message("가" * 73)

        self.assertEqual(len(validated_title), 72)
        self.assertTrue(validated_title.endswith("..."))
        self.assertTrue(any("72자를 넘어" in warning for warning in warnings))

    def test_shortens_pr_title_over_maximum_length(self):
        draft = (
            f"{'가' * 81}\n"
            "## Why\n- 변경 필요\n"
            "## What\n- 기능 추가\n"
            "## How to Test\n- 테스트 실행"
        )

        title, body, warnings = main.validate_pr_draft(draft)

        self.assertEqual(len(title), 80)
        self.assertTrue(title.endswith("..."))
        self.assertIn("## Why\n- 변경 필요", body)
        self.assertTrue(any("80자를 넘어" in warning for warning in warnings))

    def test_adds_missing_pr_sections_and_bullets(self):
        draft = "PR 제목\n## Why\n변경이 필요함\n## What\n- 기능 추가"

        title, body, warnings = main.validate_pr_draft(draft)

        self.assertEqual(title, "PR 제목")
        self.assertIn("## Why\n- 변경이 필요함", body)
        self.assertIn("## What\n- 기능 추가", body)
        self.assertIn("## How to Test\n- 사용자 확인 필요", body)
        self.assertTrue(any("Why 내용을 불릿 형식" in warning for warning in warnings))
        self.assertTrue(any("How to Test 섹션을 추가" in warning for warning in warnings))

    def test_rebuilds_all_required_sections_when_body_is_missing(self):
        title, body, warnings = main.validate_pr_draft("PR 제목")

        self.assertEqual(title, "PR 제목")
        for section_name in main.PR_SECTION_NAMES:
            self.assertIn(
                f"## {section_name}\n- 사용자 확인 필요",
                body,
            )
        self.assertGreaterEqual(len(warnings), 3)


class SafeModeTest(unittest.TestCase):
    def test_safe_mode_option_is_available_for_both_commands(self):
        parser = main.create_parser()

        self.assertTrue(parser.parse_args(["commit", "--safe-mode"]).safe_mode)
        self.assertTrue(parser.parse_args(["pr", "--safe-mode"]).safe_mode)

    def test_masks_supported_sensitive_patterns(self):
        sensitive_text = (
            "AI_API_KEY=sk-cody-live-Secret1234\n"
            '"access_token": "token-value-123"\n'
            "Authorization: Bearer header.payload.signature\n"
            "standalone sk-exampleSecret1234\n"
            "owner=user@example.com\n"
            "normal=value"
        )

        masked_text, masked_count = main.mask_sensitive_text(sensitive_text)

        self.assertNotIn("sk-cody-live-Secret1234", masked_text)
        self.assertNotIn("token-value-123", masked_text)
        self.assertNotIn("header.payload.signature", masked_text)
        self.assertNotIn("sk-exampleSecret1234", masked_text)
        self.assertNotIn("user@example.com", masked_text)
        self.assertIn("AI_API_KEY=[MASKED_SECRET]", masked_text)
        self.assertIn('"access_token": "[MASKED_SECRET]"', masked_text)
        self.assertIn("Bearer [MASKED_TOKEN]", masked_text)
        self.assertIn("[MASKED_API_KEY]", masked_text)
        self.assertIn("[MASKED_EMAIL]", masked_text)
        self.assertIn("normal=value", masked_text)
        self.assertEqual(masked_count, 5)

    def test_commit_safe_mode_sends_only_masked_changes(self):
        changed_files = ["reports/user@example.com.txt", "main.py"]
        diff_output = (
            "+AI_API_KEY=sk-cody-live-Secret1234\n"
            "+contact=user@example.com\n"
            "+normal=value"
        )
        stdout = io.StringIO()

        with (
            patch("sys.argv", ["main.py", "commit", "--safe-mode"]),
            patch(
                "main.collect_git_changes",
                return_value=(changed_files, diff_output),
            ),
            patch("main.get_api_key", return_value="dummy-secret"),
            patch("main.print_git_changes") as display,
            patch("main.build_commit_prompt", return_value="제한된 프롬프트") as builder,
            patch("main.call_ai_api", return_value="safe mode 적용"),
            patch("sys.stdout", stdout),
        ):
            exit_code = main.main()

        self.assertEqual(exit_code, 0)
        sent_files, sent_diff = builder.call_args.args
        display.assert_called_once_with(sent_files, sent_diff)
        self.assertEqual(sent_files[0], "reports/[MASKED_EMAIL]")
        self.assertEqual(sent_files[1], "main.py")
        self.assertNotIn("sk-cody-live-Secret1234", sent_diff)
        self.assertNotIn("user@example.com", sent_diff)
        self.assertIn("[MASKED_SECRET]", sent_diff)
        self.assertIn("[MASKED_EMAIL]", sent_diff)
        self.assertIn("+normal=value", sent_diff)
        self.assertIn(
            "[INFO] safe-mode 적용: 민감정보 3건 마스킹",
            stdout.getvalue(),
        )

    def test_commit_without_safe_mode_sends_original_changes(self):
        changed_files = ["reports/user@example.com.txt"]
        diff_output = "+AI_API_KEY=sk-cody-live-Secret1234"

        with (
            patch("sys.argv", ["main.py", "commit"]),
            patch(
                "main.collect_git_changes",
                return_value=(changed_files, diff_output),
            ),
            patch("main.get_api_key", return_value="dummy-secret"),
            patch("main.print_git_changes"),
            patch("main.build_commit_prompt", return_value="원본 프롬프트") as builder,
            patch("main.call_ai_api", return_value="safe mode 미사용"),
            patch("builtins.print"),
        ):
            exit_code = main.main()

        self.assertEqual(exit_code, 0)
        builder.assert_called_once_with(changed_files, diff_output)


if __name__ == "__main__":
    unittest.main()
