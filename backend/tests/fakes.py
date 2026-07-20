"""Shared test doubles.

Lives outside ``conftest.py`` on purpose: there are two ``conftest`` modules in
this test tree (``tests/`` and ``tests/auto_reply/``), and pytest puts both
directories on ``sys.path``. ``from conftest import ...`` resolves to whichever
one shadows the other, so shared helpers need a unique module name.
"""
from collections.abc import Sequence

from src.summarization.errors import ProviderError
from src.summarization.models import GeneratedSummary


class FakeProvider:
    """A ``SummaryProvider`` that replays a scripted sequence of outcomes.

    Each call to :meth:`generate` returns (or raises) the next item in
    ``outcomes``; the final item repeats once the sequence is exhausted.
    """

    def __init__(
        self,
        name: str,
        outcomes: Sequence[GeneratedSummary | ProviderError],
    ) -> None:
        self.name = name
        self.model = f"{name}-test-model"
        self.outcomes = list(outcomes)
        self.calls = 0
        self.prompts: list[tuple[str, str]] = []

    async def generate(self, *, system_prompt: str, user_prompt: str) -> GeneratedSummary:
        self.prompts.append((system_prompt, user_prompt))
        outcome = self.outcomes[min(self.calls, len(self.outcomes) - 1)]
        self.calls += 1
        if isinstance(outcome, ProviderError):
            raise outcome
        return outcome
