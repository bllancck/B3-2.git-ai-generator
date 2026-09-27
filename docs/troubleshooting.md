# 트러블슈팅 가이드

이 문서는 프로그램을 실행하면서 자주 만날 수 있는 문제의 원인과 확인 방법을 정리합니다.
명령은 프로젝트의 Git 저장소 최상위 디렉터리에서 실행하는 것을 기준으로 합니다.

> API Key는 비밀번호와 같은 민감 정보입니다. 오류를 공유할 때도 전체 값을 터미널 출력,
> 화면 캡처, Git 커밋에 포함하지 마세요.

## 빠른 확인

| 증상 | 주로 확인할 항목 |
| --- | --- |
| `python: command not found` | 이 프로젝트에서는 `python3` 명령 사용 |
| `No module named 'dotenv'` | 가상환경 활성화 및 `requirements.txt` 설치 여부 |
| `AI_API_KEY 환경변수가 설정되지 않았습니다.` | 프로젝트 루트의 `.env`와 변수 이름 확인 |
| 입력한 Key 길이가 `0` | `read` 명령 실행 방식과 현재 셸 세션 |
| `Incorrect API key provided` | 기관 Key와 기관 API 엔드포인트 사용 여부 |
| `fatal: not a git repository` | 현재 위치가 Git 저장소 내부인지 확인 |
| 변경 파일은 보이지만 diff가 비어 있음 | 파일이 아직 Git에 추적되지 않았거나 이미 스테이징되었는지 확인 |
| 연결 실패 또는 시간 초과 | 인터넷 연결, DNS, 프록시·방화벽, 기관 API 상태 확인 |

## API Key 설정

### `.env` 파일 사용하기

프로젝트 루트에서 다음 명령으로 예시 파일을 복사합니다.

```bash
cp .env.example .env
```

`.env`를 열어 기관에서 발급받은 Key를 입력합니다.

```dotenv
AI_API_KEY=YOUR_API_KEY
```

프로그램은 프로젝트 루트의 `.env`를 자동으로 읽습니다. `.env`는 `.gitignore`에
등록되어 있으므로 Git 추적 대상에서 제외됩니다. `.env.example`에는 실제 Key를
입력하지 마세요.

이미 터미널에 `AI_API_KEY`가 설정되어 있으면 그 값이 `.env`보다 우선합니다. `.env`를
수정했는데도 이전 Key가 사용된다면 다음 명령으로 터미널 값을 제거한 뒤 다시 실행합니다.

```bash
unset AI_API_KEY
```

### `No module named 'dotenv'`

필요한 패키지가 설치되지 않은 상태입니다. 가상환경을 활성화하고 의존성을 설치합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### 터미널에서 일회성으로 입력하기

`.env`를 사용하지 않고 현재 터미널에서만 Key를 사용하려면 다음 명령을 순서대로
실행합니다. 변수 이름에는 역슬래시(`\`)를 넣지 않습니다.

```bash
read -rsp "코디세이 API Key: " AI_API_KEY
echo
printf '입력된 Key 길이: %s\n' "${#AI_API_KEY}"
export AI_API_KEY
python3 main.py commit
```

`read`의 `-s` 옵션은 입력 문자를 화면에 표시하지 않습니다. 따라서 Key를 입력하는 동안
글자가 보이지 않는 것이 정상입니다. 입력을 마친 뒤 Enter를 누르세요.

길이만 확인하는 명령은 Key 자체를 출력하지 않으므로 비교적 안전합니다. 길이가 `0`이라면
다시 입력하고, `read`와 프로그램 실행을 같은 터미널 창에서 진행했는지 확인합니다.

실행을 마친 뒤 현재 터미널 세션에서 Key를 제거하려면 다음 명령을 사용합니다.

```bash
unset AI_API_KEY
```

## API 인증 실패

이 프로젝트는 코디세이 기관 API를 사용합니다.

- Base URL: `https://copa.codyssey.kr`
- 요청 엔드포인트: `https://copa.codyssey.kr/v1/chat/completions`
- 현재 기본 모델: `gpt-5.4-mini`
- 인증 헤더: `Authorization: Bearer <기관 API Key>`

기관에서 발급한 Key는 OpenAI 공식 엔드포인트인 `https://api.openai.com`에서 인증되지 않을 수
있습니다. 오류 메시지에 공식 OpenAI 주소가 나타난다면 이전 코드나 설정이 사용되고 있지 않은지
확인하세요.

기관 엔드포인트에서도 인증 오류가 발생하면 다음을 확인합니다.

1. API 콘솔에서 Key 상태가 `활성`인지 확인합니다.
2. Key를 복사할 때 앞뒤 공백이나 따옴표가 포함되지 않았는지 확인합니다.
3. 환경변수 길이가 `0`이 아닌지 확인합니다.
4. Key를 다시 입력하고 프로그램을 다시 실행합니다.

Key 전체를 출력하는 `echo "$AI_API_KEY"` 같은 명령은 사용하지 마세요.

## Git 저장소 오류

### `fatal: not a git repository`

프로그램은 Git의 변경 정보를 사용하므로 Git 저장소 안에서 실행해야 합니다. 현재 위치를 확인한 뒤
프로젝트 디렉터리로 이동합니다.

```bash
pwd
git rev-parse --show-toplevel
```

두 번째 명령이 실패한다면 현재 위치는 Git 저장소가 아닙니다. 올바른 저장소로 이동하거나, 새
프로젝트라면 필요한 경우에만 `git init`으로 저장소를 초기화합니다.

### 변경 파일은 표시되지만 diff 내용이 없음

`git status`에는 새 파일도 표시되지만, 기본 `git diff`에는 아직 Git이 추적하지 않는 새 파일이나
이미 스테이징된 변경이 포함되지 않을 수 있습니다.

현재 상태를 다음 명령으로 확인합니다.

```bash
git status --short
git diff
git diff --cached
```

- 줄 앞에 `??`가 있으면 아직 추적되지 않은 새 파일입니다.
- `git diff --cached`에만 내용이 보이면 변경 사항이 스테이징된 상태입니다.
- 최초 커밋이 없는 저장소에서는 비교 기준이 부족해 diff가 비어 보일 수 있습니다.

이 경우 AI 응답에도 "제공된 diff가 없다"는 내용이 나타날 수 있습니다. 실제 코드 변경을 분석하려면
먼저 기준이 되는 커밋이 있고, 분석할 변경 내용이 `git diff`에 나타나는 상태인지 확인하세요.

### 변경 사항이 없다고 표시됨

작업 트리에 변경 사항이 없으면 분석할 내용도 없습니다. 다음 명령으로 확인합니다.

```bash
git status --short
```

출력이 없다면 파일을 실제로 변경한 뒤 다시 실행하세요.

## 네트워크 및 API 응답 오류

### 연결 실패 또는 시간 초과

인터넷 연결과 `copa.codyssey.kr` 접속 가능 여부를 확인합니다. 회사나 학교 네트워크에서는 프록시,
VPN 또는 방화벽이 연결을 제한할 수도 있습니다. 잠시 뒤 다시 실행해도 계속 실패하면 기관 API의
상태를 확인하세요.

### HTTP 상태 코드별 확인 사항

- `401`, `403`: Key가 잘못되었거나 비활성 상태이거나 접근 권한이 부족할 수 있습니다.
- `404`: 엔드포인트 주소나 모델 이름이 잘못되었을 수 있습니다.
- `429`: 사용량 한도 또는 요청 빈도 제한에 도달했을 수 있습니다. 기관 API 콘솔에서 사용량을 확인하세요.
- `500`, `502`, `503`: 서버의 일시적인 문제일 수 있습니다. 잠시 뒤 다시 시도하세요.

`gpt-5-mini`에 `temperature`를 함께 보내면 상위 제공자 오류가 발생하고, 기관
게이트웨이에서는 이를 `HTTP 502: Provider returned an error`로 표시할 수 있습니다.
현재 기본 모델은 `temperature` 요청이 실제로 성공한 `gpt-5.4-mini`입니다.

### JSON 응답을 해석하지 못함 또는 응답 본문이 비어 있음

현재 프로그램은 OpenAI 호환 Chat Completions 응답에서
`choices[0].message.content`의 텍스트를 읽습니다. 엔드포인트나 모델이 바뀌었거나 서버가 오류 페이지를
반환하면 이 형식과 달라질 수 있습니다. 기관 API 문서에서 엔드포인트와 지원 모델을 다시 확인하세요.

## 문제를 공유할 때 포함할 정보

다음 정보는 원인 파악에 도움이 됩니다.

- 실행한 명령어(단, API Key는 제거)
- 오류 메시지 전체(오류에 Key 일부가 표시됐다면 가린 뒤 공유)
- `python3 --version`
- `git status --short` 결과
- 사용한 운영체제와 터미널 종류

API Key 원문, 인증 헤더, Key가 저장된 파일은 공유하지 마세요.
