class JeanClaudeError(Exception):
    """Base exception for Jean-Claude CLI errors."""


class AuthError(JeanClaudeError):
    """Authentication-related errors."""


class LLMError(JeanClaudeError):
    """LLM provider errors."""


class RetryableLLMError(LLMError):
    """A transient LLM error that should be retried."""


class AuthExpiredError(LLMError):
    """The current auth token is expired or invalid."""


class ToolError(JeanClaudeError):
    """Tool execution or policy error."""


class FlowError(JeanClaudeError):
    """Flow/prompt-pack loading or validation error."""
