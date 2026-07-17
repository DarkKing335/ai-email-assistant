import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from src.summarization.errors import (
    ProviderConfigurationError,
    ProviderContentRejectedError,
    ProviderError,
    ProviderInvalidOutputError,
    SummarizationConfigurationError,
    SummarizationContentRejectedError,
    SummarizationUnavailableError,
)
from src.summarization.models import (
    GeneratedSummary,
    SummarizationRequest,
    SummarizationResult,
)
from src.summarization.preprocessing import normalize_request
from src.summarization.providers import SYSTEM_PROMPT, SummaryProvider, build_user_prompt

logger = logging.getLogger(__name__)


class SummarizationService:
    def __init__(
        self,
        *,
        primary: SummaryProvider,
        fallback: SummaryProvider,
        max_messages: int = 20,
        max_normalized_chars: int = 100_000,
        retry_delay_seconds: float = 0.25,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.max_messages = max_messages
        self.max_normalized_chars = max_normalized_chars
        self.retry_delay_seconds = retry_delay_seconds
        self._sleep = sleep

    async def summarize(
        self,
        request: SummarizationRequest,
        *,
        request_id: str | None = None,
    ) -> SummarizationResult:
        request_id = request_id or str(uuid4())
        started = time.monotonic()
        normalized = normalize_request(
            request,
            max_messages=self.max_messages,
            max_normalized_chars=self.max_normalized_chars,
        )
        retained_ids = [message.message_id for message in normalized.messages]
        user_prompt = build_user_prompt(normalized.model_dump(mode="json"))

        attempts = 0
        fallback_used = False
        final_error: ProviderError | None = None
        summary: GeneratedSummary | None = None
        provider_used = self.primary.name

        for attempt in range(2):
            attempts += 1
            try:
                candidate = await self.primary.generate(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                )
                self._validate_citations(candidate, retained_ids)
                summary = candidate
                break
            except ProviderConfigurationError as exc:
                raise SummarizationConfigurationError() from exc
            except ProviderContentRejectedError as exc:
                raise SummarizationContentRejectedError() from exc
            except ProviderError as exc:
                final_error = exc
                if not exc.retryable or attempt == 1:
                    break
                if self.retry_delay_seconds:
                    await self._sleep(self.retry_delay_seconds)

        if summary is None and final_error and final_error.allows_fallback:
            attempts += 1
            fallback_used = True
            provider_used = self.fallback.name
            try:
                candidate = await self.fallback.generate(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                )
                self._validate_citations(candidate, retained_ids)
                summary = candidate
            except ProviderConfigurationError as exc:
                raise SummarizationConfigurationError() from exc
            except ProviderContentRejectedError as exc:
                raise SummarizationContentRejectedError() from exc
            except ProviderError as exc:
                final_error = exc

        if summary is None:
            logger.warning(
                "summarization_failed request_id=%s attempts=%d fallback_used=%s duration_ms=%d",
                request_id,
                attempts,
                fallback_used,
                round((time.monotonic() - started) * 1_000),
            )
            raise SummarizationUnavailableError(
                invalid_output=bool(final_error and final_error.invalid_output)
            )

        logger.info(
            "summarization_succeeded request_id=%s provider=%s model=%s "
            "message_count=%d omitted_count=%d attempts=%d fallback_used=%s duration_ms=%d",
            request_id,
            provider_used,
            self.fallback.model if fallback_used else self.primary.model,
            len(normalized.messages),
            len(normalized.omitted_message_ids),
            attempts,
            fallback_used,
            round((time.monotonic() - started) * 1_000),
        )
        return SummarizationResult(
            **summary.model_dump(),
            request_id=request_id,
            source_message_ids=retained_ids,
            omitted_message_ids=normalized.omitted_message_ids,
            truncated=bool(normalized.omitted_message_ids),
        )

    @staticmethod
    def _validate_citations(summary: GeneratedSummary, retained_ids: list[str]) -> None:
        allowed = set(retained_ids)
        cited_groups = [item.source_message_ids for item in summary.key_points]
        cited_groups.extend(item.source_message_ids for item in summary.action_items)
        if any(not set(group).issubset(allowed) for group in cited_groups):
            raise ProviderInvalidOutputError()
