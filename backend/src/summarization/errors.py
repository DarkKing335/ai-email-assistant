class SummarizationError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int,
        retryable: bool,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message
        self.status_code = status_code
        self.retryable = retryable


class InvalidEmailContentError(SummarizationError):
    def __init__(self) -> None:
        super().__init__(
            "invalid_email_content",
            "One or more messages contain no readable email content.",
            status_code=422,
            retryable=False,
        )


class InputTooLargeError(SummarizationError):
    def __init__(self) -> None:
        super().__init__(
            "input_too_large",
            "The retained email content is too large to summarize safely.",
            status_code=413,
            retryable=False,
        )


class ProviderError(Exception):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        allows_fallback: bool,
        invalid_output: bool = False,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.allows_fallback = allows_fallback
        self.invalid_output = invalid_output


class ProviderConfigurationError(ProviderError):
    def __init__(self, message: str = "The summarization provider is not configured.") -> None:
        super().__init__(message, retryable=False, allows_fallback=False)


class ProviderInvalidOutputError(ProviderError):
    def __init__(self) -> None:
        super().__init__(
            "The provider returned an invalid structured summary.",
            retryable=True,
            allows_fallback=True,
            invalid_output=True,
        )


class ProviderContentRejectedError(ProviderError):
    def __init__(self) -> None:
        super().__init__(
            "The provider rejected the email content under its safety policy.",
            retryable=False,
            allows_fallback=False,
        )


class SummarizationUnavailableError(SummarizationError):
    def __init__(self, *, invalid_output: bool = False) -> None:
        if invalid_output:
            super().__init__(
                "invalid_provider_output",
                "The AI providers could not produce a valid summary.",
                status_code=502,
                retryable=True,
            )
        else:
            super().__init__(
                "summarization_unavailable",
                "Email summarization is temporarily unavailable.",
                status_code=503,
                retryable=True,
            )


class SummarizationConfigurationError(SummarizationError):
    def __init__(self) -> None:
        super().__init__(
            "summarization_not_configured",
            "Email summarization is not configured.",
            status_code=503,
            retryable=False,
        )


class SummarizationContentRejectedError(SummarizationError):
    def __init__(self) -> None:
        super().__init__(
            "content_rejected",
            "The email content could not be summarized safely.",
            status_code=422,
            retryable=False,
        )
