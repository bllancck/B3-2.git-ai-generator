"""설정, Git, AI API 오류 타입."""


class GitCommandError(RuntimeError):
    """Git 명령을 실행하지 못했을 때 발생하는 오류."""


class ConfigurationError(RuntimeError):
    """프로그램 실행에 필요한 설정이 올바르지 않을 때 발생하는 오류."""


class AIAPIError(RuntimeError):
    """AI API 요청 또는 응답 처리에 실패했을 때 발생하는 오류."""
