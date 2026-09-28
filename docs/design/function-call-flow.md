# 함수 호출 관계

함수 호출 관계를 입력 준비, AI 생성, 결과 처리의 세 영역으로 나누어 나타낸다.

다이어그램은 다음과 같이 읽는다.

- 박스는 위에서부터 `파일`, `함수`, `함수가 하는 일`을 표시한다.
- 실선 화살표는 한 함수가 다른 함수를 호출하는 관계다.
- 점선 화살표는 특정 조건에서만 호출하거나 외부 프로그램·API를 사용하는 관계다.

예를 들어 `main()` → `collect_git_changes()`는 `main()`이 Git 변경 사항을 얻기 위해
`collect_git_changes()`를 실행한다는 뜻이다.

## 1. 입력 준비

```mermaid
flowchart LR
    Main["main.py<br/><code>main()</code><br/>전체 실행 순서를 관리"]

    Main --> Parser["cli.py<br/><code>create_parser()</code><br/>commit/pr 명령의 틀을 생성"]
    Parser --> Options["cli.py<br/><code>add_ai_options()</code><br/>모델·토큰 등 공통 옵션을 추가"]
    Main --> ParseArgs["argparse<br/><code>parse_args()</code><br/>사용자가 입력한 명령을 해석"]
    ParseArgs --> Validators["cli.py<br/><code>non_empty_model()</code><br/><code>temperature_value()</code><br/><code>positive_integer()</code><br/>옵션 값의 형식과 범위를 검사"]

    Main --> Collect["gitctx.py<br/><code>collect_git_changes()</code><br/>변경 파일과 diff를 한 번에 수집"]
    Collect --> RunGit["gitctx.py<br/><code>run_git_command()</code><br/>Git 명령을 실행하고 결과를 반환"]
    Collect --> Extract["gitctx.py<br/><code>extract_changed_files()</code><br/>status 결과에서 파일명만 추출"]
    RunGit -. 외부 명령 .-> Git[("Git CLI<br/>status와 diff 제공")]

    Main --> MainKey["main.py<br/><code>get_api_key()</code><br/>설정 모듈에 API Key를 요청"]
    MainKey --> ConfigKey["config.py<br/><code>get_api_key()</code><br/>환경변수나 .env에서 Key를 읽음"]

    Main -. safe-mode .-> Mask["sanitizer.py<br/><code>mask_changes_for_safe_mode()</code><br/>파일명과 diff의 민감정보를 가림"]
    Mask --> MaskText["sanitizer.py<br/><code>mask_sensitive_text()</code><br/>텍스트에서 민감정보 패턴을 치환"]
    Main --> Preview["render.py<br/><code>print_git_changes()</code><br/>수집한 파일과 diff를 화면에 표시"]
```

## 2. AI 생성

```mermaid
flowchart LR
    Main["main.py<br/><code>main()</code><br/>입력한 명령에 맞는 작업을 선택"] --> Command{"commit 또는 pr?"}
    Command -->|commit| CommitPrompt["prompts.py<br/><code>build_commit_prompt()</code><br/>커밋 제목 생성용 요청문을 작성"]
    Command -->|pr| PRPrompt["prompts.py<br/><code>build_pr_prompt()</code><br/>PR 제목·본문 생성용 요청문을 작성"]
    CommitPrompt --> CallAI["ai.py<br/><code>call_ai_api()</code><br/>요청문을 보내고 AI 응답을 받음"]
    PRPrompt --> CallAI

    CallAI -. HTTP 요청 .-> API[("코디세이 AI API<br/>초안 텍스트 생성")]
    CallAI --> Extract["ai.py<br/><code>extract_response_text()</code><br/>JSON 응답에서 생성 문구를 꺼냄"]
    CallAI -. HTTP 오류 .-> ParseError["ai.py<br/><code>parse_api_error()</code><br/>오류 응답에서 원인 메시지를 꺼냄"]
```

## 3. 결과 처리

```mermaid
flowchart LR
    Main["main.py<br/><code>main()</code><br/>명령에 맞는 출력 함수를 선택"] --> Result{"commit 또는 pr?"}

    Result -->|commit| PrintCommit["render.py<br/><code>print_commit_result()</code><br/>커밋 제목과 경고를 화면에 출력"]
    PrintCommit --> ValidateCommit["postprocess.py<br/><code>validate_commit_message()</code><br/>커밋 제목 길이를 검사"]
    ValidateCommit -. 제목 초과 .-> Shorten["postprocess.py<br/><code>shorten_title()</code><br/>긴 제목을 최대 길이에 맞게 줄임"]

    Result -->|pr| PrintPR["render.py<br/><code>print_pr_result()</code><br/>PR 제목·본문과 경고를 화면에 출력"]
    PrintPR --> ValidatePR["postprocess.py<br/><code>validate_pr_draft()</code><br/>PR 제목과 필수 본문 구조를 검사"]
    ValidatePR --> Split["postprocess.py<br/><code>split_pr_draft()</code><br/>첫 줄은 제목, 나머지는 본문으로 분리"]
    ValidatePR --> Normalize["postprocess.py<br/><code>normalize_section_heading()</code><br/>PR 섹션 이름을 표준 형식으로 맞춤"]
    ValidatePR -. 제목 초과 .-> Shorten
```

실행 순서와 종료 분기는 [상세 실행 흐름](execution-flow.md)을 참고한다.

## 4. 전체 함수 호출 관계

아래 다이어그램은 앞에서 나눈 세 영역의 호출 관계를 한 번에 보여 준다.

```mermaid
flowchart TB
    Main["main.py<br/><code>main()</code>"]

    CreateParser["gitgen/cli.py<br/><code>create_parser()</code>"]
    ParseArgs["argparse.ArgumentParser<br/><code>parse_args()</code>"]
    AddOptions["<code>add_ai_options()</code>"]
    Validators["argparse 검증 함수<br/><code>non_empty_model()</code><br/><code>temperature_value()</code><br/><code>positive_integer()</code>"]

    Collect["gitgen/gitctx.py<br/><code>collect_git_changes()</code>"]
    RunGit["<code>run_git_command()</code>"]
    ExtractFiles["<code>extract_changed_files()</code>"]
    Git[("Git CLI")]

    MainKey["main.py<br/><code>get_api_key()</code>"]
    ConfigKey["gitgen/config.py<br/><code>get_api_key()</code>"]

    MaskChanges["gitgen/sanitizer.py<br/><code>mask_changes_for_safe_mode()</code>"]
    MaskText["<code>mask_sensitive_text()</code>"]

    PrintChanges["gitgen/render.py<br/><code>print_git_changes()</code>"]
    CommitPrompt["gitgen/prompts.py<br/><code>build_commit_prompt()</code>"]
    PRPrompt["gitgen/prompts.py<br/><code>build_pr_prompt()</code>"]

    CallAI["gitgen/ai.py<br/><code>call_ai_api()</code>"]
    ExtractResponse["<code>extract_response_text()</code>"]
    ParseError["<code>parse_api_error()</code>"]
    API[("코디세이 AI API")]

    PrintCommit["gitgen/render.py<br/><code>print_commit_result()</code>"]
    PrintPR["gitgen/render.py<br/><code>print_pr_result()</code>"]
    ValidateCommit["gitgen/postprocess.py<br/><code>validate_commit_message()</code>"]
    ValidatePR["gitgen/postprocess.py<br/><code>validate_pr_draft()</code>"]
    SplitPR["<code>split_pr_draft()</code>"]
    NormalizeHeading["<code>normalize_section_heading()</code>"]
    ShortenTitle["<code>shorten_title()</code>"]

    Main --> CreateParser
    Main --> ParseArgs
    CreateParser --> AddOptions
    CreateParser -. parser 구성 .-> ParseArgs
    ParseArgs --> Validators

    Main --> Collect
    Collect --> RunGit
    Collect --> ExtractFiles
    RunGit -. 외부 명령 .-> Git

    Main --> MainKey --> ConfigKey
    Main -. safe-mode일 때 .-> MaskChanges --> MaskText
    Main --> PrintChanges

    Main -->|commit| CommitPrompt
    Main -->|pr| PRPrompt
    Main --> CallAI
    CallAI --> ExtractResponse
    CallAI -. HTTP 오류일 때 .-> ParseError
    CallAI -. HTTP 요청 .-> API

    Main -->|commit| PrintCommit --> ValidateCommit
    Main -->|pr| PrintPR --> ValidatePR
    ValidateCommit -. 제목 초과 시 .-> ShortenTitle
    ValidatePR --> SplitPR
    ValidatePR --> NormalizeHeading
    ValidatePR -. 제목 초과 시 .-> ShortenTitle
```
