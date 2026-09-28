# AI API 파라미터 비교

`--temperature`와 `--max-tokens`가 실제 PR 초안에 미치는 영향을 비교한 기록이다.
한 번에 한 파라미터만 바꾸고 나머지 조건은 고정했다.

## 먼저 보는 결론

| 파라미터 | 실제 확인 결과 |
|---|---|
| `temperature` | `0`과 `1.2` 모두 실행할 때마다 표현이 달라졌다. `1.2`가 일관되게 더 길거나 자세하지는 않았다. |
| `max_tokens` | `60`은 본문이 중간에 끊겼고, `120`은 일부만 완성됐으며, `300`은 모든 섹션이 완성됐다. |

`temperature`는 길이를 조절하는 옵션이 아니며 한두 번의 실행만으로 품질 우위를 판단하기
어렵다. 반면 `max_tokens`는 응답의 상한이므로 값이 너무 작으면 실제로 내용이 잘린다.

## 실험 입력

단순 주석 대신 실제 기능과 테스트가 함께 바뀌는 다음 보안 개선을 임시로 만들었다.

- `gitgen/sanitizer.py`
  - GitHub 토큰(`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`) 마스킹 규칙 추가
  - AWS Access Key(`AKIA`, `ASIA`) 마스킹 규칙 추가
- `tests/test_ai_api.py`
  - 두 신규 패턴이 원문에서 제거되는지 검증
  - 전용 마스킹 문자열로 치환되는지 검증
  - 예상 마스킹 횟수를 5회에서 7회로 변경

임시 변경은 2개 파일에서 15줄 추가, 1줄 수정 규모였으며 관련 단위 테스트를 먼저
통과시켰다. 모든 API 호출에는 `--safe-mode`를 사용했고 입력에서 민감정보 패턴 13건이
마스킹되었다.

## 실험 조건과 호출 횟수

- 실행일: 2026-09-29
- 모델: `gpt-5.4-mini`
- 명령: `python3 main.py pr --safe-mode`
- Temperature 비교: `max_tokens=300` 고정, `0`과 `1.2`를 각각 2회 실행
- Max tokens 비교: `temperature=0` 고정, `60`, `120`, `300` 비교
- 총 실제 API 호출: 6회
- `max_tokens=300`, `temperature=0` 결과는 두 비교에서 재사용해 중복 호출을 줄였다.

아래 문자 수는 모델의 토큰 사용량이 아니라 CLI 후처리까지 끝난 PR 제목과 본문의
문자 수 합계다. 경고는 잘린 응답을 보완하기 위해 프로그램이 출력한 `[WARN]` 개수다.

## Temperature 비교 결과

| 표본 | `temperature` | `max_tokens` | 출력 문자 수 | 본문 불릿 | 경고 |
|---|---:|---:|---:|---:|---:|
| T0-A | `0` | `300` | 635자 | 8개 | 0개 |
| T0-B | `0` | `300` | 549자 | 7개 | 0개 |
| T1.2-A | `1.2` | `300` | 579자 | 7개 | 0개 |
| T1.2-B | `1.2` | `300` | 543자 | 8개 | 0개 |

`temperature=0`도 두 결과의 제목, 문장, 불릿 수가 같지 않았다. 즉 이 API에서는 값을
0으로 설정해도 완전히 동일한 응답이 보장되지 않았다. 두 표본 평균은 `temperature=0`이
592자, `temperature=1.2`가 561자였지만 표본이 두 개뿐이므로 길이 차이를 일반적인 경향으로
해석할 수 없다. 네 결과 모두 필수 섹션을 완성했고 후처리 경고는 없었다.

### T0-A: `temperature=0`, `max_tokens=300`

```text
Git 민감정보 마스킹 패턴에 GitHub 토큰과 AWS 액세스 키 추가

## Why
- 안전 모드에서 다양한 형태의 민감정보가 로그나 변경 내용에 노출되지 않도록 추가 마스킹이 필요합니다.
- 기존 마스킹 대상에 GitHub 토큰과 AWS 액세스 키 패턴이 포함되어 있지 않았습니다.

## What
- `gitgen/sanitizer.py`에 GitHub 토큰 패턴(`gh[pousr]_...`)을 추가하고 `[MASKED_GITHUB_TOKEN]`으로 치환하도록 했습니다.
- `gitgen/sanitizer.py`에 AWS 액세스 키 패턴(`AKIA...`, `ASIA...`)을 추가하고 `[MASKED_AWS_ACCESS_KEY]`로 치환하도록 했습니다.
- `tests/test_ai_api.py`의 안전 모드 테스트에 GitHub 토큰 및 AWS 액세스 키 마스킹 기대값을 추가했습니다.
- 마스킹 개수 기대값을 5에서 7로 수정했습니다.

## How to Test
- `tests/test_ai_api.py`의 안전 모드 테스트를 실행해 GitHub 토큰과 AWS 액세스 키가 각각 `[MASKED_GITHUB_TOKEN]`, `[MASKED_AWS_ACCESS_KEY]`로 치환되는지 확인합니다.
- 사용자 확인 필요
```

### T0-B: `temperature=0`, `max_tokens=300`

```text
Git 민감 정보 마스킹 패턴 확장 및 테스트 보강

## Why
- Git 변경 내용에 포함될 수 있는 추가 민감 정보(GitHub 토큰, AWS 액세스 키)를 기존 마스킹 대상에 포함해 안전하게 처리하기 위해서입니다.
- 안전 모드에서 민감 정보가 올바르게 마스킹되는지 검증 범위를 넓히기 위해서입니다.

## What
- `gitgen/sanitizer.py`에 GitHub 토큰 패턴(`gh[pousr]_...`)과 AWS 액세스 키 패턴(`AKIA`/`ASIA`로 시작하는 키)을 추가했습니다.
- `tests/test_ai_api.py`의 안전 모드 테스트에 GitHub 토큰 및 AWS 액세스 키 마스킹 기대값을 추가했습니다.
- 마스킹 결과 개수 기대값을 5개에서 7개로 수정했습니다.

## How to Test
- `tests/test_ai_api.py`의 안전 모드 테스트를 실행해 GitHub 토큰과 AWS 액세스 키가 각각 `[MASKED_GITHUB_TOKEN]`, `[MASKED_AWS_ACCESS_KEY]`로 마스킹되는지 확인합니다.
- 사용자 확인 필요
```

### T1.2-A: `temperature=1.2`, `max_tokens=300`

```text
Git 비밀정보 마스킹 패턴 추가

## Why
- 안전 모드에서 GitHub 토큰과 AWS 액세스 키도 함께 마스킹하여 민감 정보 노출을 줄이기 위해 변경되었습니다.
- 기존 마스킹 대상 외의 주요 인증 정보 패턴을 추가로 처리할 필요가 있습니다.

## What
- `gitgen/sanitizer.py`에 GitHub 토큰 패턴(`gh[pousr]_...`)과 AWS Access Key 패턴(`AKIA...`, `ASIA...`)을 새로 추가했습니다.
- `tests/test_ai_api.py`의 안전 모드 테스트에 GitHub 토큰 및 AWS 액세스 키 마스킹 사례를 추가했습니다.
- 마스킹 결과 검증 항목을 새로운 패턴에 맞게 확장하고, 기대 마스킹 개수를 5에서 7로 수정했습니다.

## How to Test
- `tests/test_ai_api.py`의 안전 모드 테스트에서 GitHub 토큰과 AWS 액세스 키가 각각 `[MASKED_GITHUB_TOKEN]`, `[MASKED_AWS_ACCESS_KEY]`로 치환되는지 확인합니다.
- 마스킹 결과에 기존 민감 정보와 새로 추가된 패턴이 모두 포함되는지 확인합니다.
```

### T1.2-B: `temperature=1.2`, `max_tokens=300`

```text
Git 민감정보 마스킹 패턴 추가 및 관련 테스트 확장

## Why
- Git 변경 내용에서 기존 API 키 외에도 GitHub 토큰과 AWS 액세스 키가 노출될 수 있어, 민감정보 마스킹 범위를 확장할 필요가 있습니다.
- 마스킹 로직 변경에 따라 관련 테스트도 함께 갱신해 동작을 검증해야 합니다.

## What
- `gitgen/sanitizer.py`에 GitHub 토큰 형식(`gh[pousr]_...`)을 마스킹하는 패턴을 추가했습니다.
- `gitgen/sanitizer.py`에 AWS 액세스 키 형식(`AKIA...`, `ASIA...`)을 마스킹하는 패턴을 추가했습니다.
- `tests/test_ai_api.py`의 safe mode 테스트에 GitHub 토큰과 AWS 액세스 키 마스킹 기대값을 추가했습니다.
- 기존 마스킹 개수 기대값을 5에서 7로 수정했습니다.

## How to Test
- `tests/test_ai_api.py`의 safe mode 테스트를 실행해 추가된 마스킹 패턴이 기대대로 반영되는지 확인합니다.
- 사용자 확인 필요
```

## Max tokens 비교 결과

| 표본 | `temperature` | `max_tokens` | 출력 문자 수 | 본문 불릿 | 경고 | 완성 상태 |
|---|---:|---:|---:|---:|---:|---|
| M60 | `0` | `60` | 164자 | 4개 | 4개 | Why 문장이 중간에 끊기고 What·How to Test가 자동 보완됨 |
| M120 | `0` | `120` | 298자 | 4개 | 2개 | What 두 번째 불릿이 중간에 끊기고 How to Test가 자동 보완됨 |
| M300 | `0` | `300` | 635자 | 8개 | 0개 | 모든 섹션과 구체적인 테스트 방법이 완성됨 |

`60 → 120 → 300`으로 상한을 높일수록 실제 정보량과 완성도가 뚜렷하게 증가했다.
이 입력에서는 `60`과 `120`이 부족했고 `300`에서 완전한 초안이 생성됐다. 프로그램의
후처리는 누락된 섹션을 만들어 주지만, 잘린 문장을 복원하거나 구체적인 내용을 새로 생성하지는
못하므로 `- 사용자 확인 필요`가 대신 들어간다.

### 경고의 의미

표의 경고는 AI API나 토큰 제공자가 보낸 경고가 아니다. `postprocess.py`의 결과 검증기가
AI 응답에서 필수 PR 구조가 누락된 것을 발견하고 자동 보완했다는 의미다.

- M60의 경고 4개
  - `What` 섹션이 없어 새로 추가함
  - `What` 내용이 없어 `- 사용자 확인 필요`를 추가함
  - `How to Test` 섹션이 없어 새로 추가함
  - `How to Test` 내용이 없어 `- 사용자 확인 필요`를 추가함
- M120의 경고 2개
  - `How to Test` 섹션이 없어 새로 추가함
  - `How to Test` 내용이 없어 `- 사용자 확인 필요`를 추가함
- M300은 세 필수 섹션과 각 섹션의 불릿이 있어 경고가 발생하지 않음

경고 개수는 응답이 잘린 정도가 아니라 프로그램이 발견해 보완한 **형식 문제의 개수**다.
현재 검증기는 섹션과 불릿의 존재 여부를 확인하지만, M60의 `기존 마스`나 M120의
`tests/test_ai_api.py의 안전`처럼 문장이 중간에 끊긴 상태는 감지하지 못한다.
따라서 경고가 없다는 사실만으로 내용이 완전하다고 판단해서는 안 되며 최종 결과를 사용자가
직접 검토해야 한다.

### M60: `temperature=0`, `max_tokens=60`

```text
[WARN] PR 본문에 What 섹션을 추가했습니다.
[WARN] PR 본문의 What 섹션에 확인용 불릿을 추가했습니다.
[WARN] PR 본문에 How to Test 섹션을 추가했습니다.
[WARN] PR 본문의 How to Test 섹션에 확인용 불릿을 추가했습니다.

Git sanitizer에 GitHub/AWS 토큰 마스킹 추가

## Why
- 안전 모드에서 민감한 값이 로그나 변경 내용에 노출되지 않도록 추가적인 비밀 키 패턴을 마스킹할 필요가 있습니다.
- 기존 마스

## What
- 사용자 확인 필요

## How to Test
- 사용자 확인 필요
```

### M120: `temperature=0`, `max_tokens=120`

```text
[WARN] PR 본문에 How to Test 섹션을 추가했습니다.
[WARN] PR 본문의 How to Test 섹션에 확인용 불릿을 추가했습니다.

Git sanitizer에 GitHub/AWS 토큰 마스킹 추가

## Why
- 민감 정보 마스킹 대상에 GitHub 토큰과 AWS Access Key를 포함해, 안전 모드에서 추가 자격 증명이 노출되지 않도록 하기 위함입니다.

## What
- `gitgen/sanitizer.py`에 GitHub 토큰 패턴(`gh[pousr]_...`)과 AWS Access Key 패턴(`AKIA`/`ASIA`로 시작하는 키)을 추가했습니다.
- `tests/test_ai_api.py`의 안전

## How to Test
- 사용자 확인 필요
```

### M300: `temperature=0`, `max_tokens=300`

```text
Git 민감정보 마스킹 패턴에 GitHub 토큰과 AWS 액세스 키 추가

## Why
- 안전 모드에서 다양한 형태의 민감정보가 로그나 변경 내용에 노출되지 않도록 추가 마스킹이 필요합니다.
- 기존 마스킹 대상에 GitHub 토큰과 AWS 액세스 키 패턴이 포함되어 있지 않았습니다.

## What
- `gitgen/sanitizer.py`에 GitHub 토큰 패턴(`gh[pousr]_...`)을 추가하고 `[MASKED_GITHUB_TOKEN]`으로 치환하도록 했습니다.
- `gitgen/sanitizer.py`에 AWS 액세스 키 패턴(`AKIA...`, `ASIA...`)을 추가하고 `[MASKED_AWS_ACCESS_KEY]`로 치환하도록 했습니다.
- `tests/test_ai_api.py`의 안전 모드 테스트에 GitHub 토큰 및 AWS 액세스 키 마스킹 기대값을 추가했습니다.
- 마스킹 개수 기대값을 5에서 7로 수정했습니다.

## How to Test
- `tests/test_ai_api.py`의 안전 모드 테스트를 실행해 GitHub 토큰과 AWS 액세스 키가 각각 `[MASKED_GITHUB_TOKEN]`, `[MASKED_AWS_ACCESS_KEY]`로 치환되는지 확인합니다.
- 사용자 확인 필요
```

## 해석과 한계

- Temperature 비교는 조건별 2회만 실행했으므로 통계적 결론이 아니라 관찰 사례다.
- `temperature=0`도 완전한 재현성을 보장하지 않았다. 서버나 모델 구현의 비결정적 요소가
  있을 수 있지만, 이번 실험만으로 원인을 특정할 수는 없다.
- `max_tokens`는 목표 길이가 아니라 상한이다. 충분한 값 이상에서는 더 높여도 자동으로
  길어지지 않지만, 필요한 값보다 낮으면 문장과 섹션이 잘릴 수 있다.
- 필요한 토큰 수는 변경 규모, 언어, 프롬프트 형식에 따라 달라진다. 이번 입력에서 `300`이
  충분했다는 결과를 모든 작업에 그대로 적용할 수는 없다.

실험은 격리된 임시 복제본에서 수행했다. 실험 후 복제본을 제거했으므로 원본 저장소의
`gitgen/sanitizer.py`와 `tests/test_ai_api.py`에는 임시 보안 변경이 남지 않는다.
