from src.summarization.errors import (
    ProviderConfigurationError,
    ProviderContentRejectedError,
)
from src.summarization.providers import classify_provider_exception


class AuthenticationError(Exception):
    status_code = 401


class SafetyBlockedError(Exception):
    pass


def test_authentication_errors_are_non_retryable_configuration_errors():
    error = classify_provider_exception(AuthenticationError("secret provider response"))

    assert isinstance(error, ProviderConfigurationError)
    assert error.retryable is False
    assert error.allows_fallback is False
    assert "secret provider response" not in str(error)


def test_safety_errors_are_non_retryable_and_do_not_fallback():
    error = classify_provider_exception(SafetyBlockedError("blocked"))

    assert isinstance(error, ProviderContentRejectedError)
    assert error.retryable is False
    assert error.allows_fallback is False
