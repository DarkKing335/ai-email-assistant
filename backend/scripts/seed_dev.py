"""
seed_dev.py — Populate the development database with realistic sample data.

A fresh database makes every panel render its empty state, so "working" and
"broken" look identical while the frontend is being built. This gives the
whitelist, logs, and dashboard panels something to show.

Run from the `backend/` directory so the relative sqlite path in
`database_url` resolves to the same file the API uses:

    uv run python scripts/seed_dev.py
    uv run python scripts/seed_dev.py --reset    # wipe existing rows first

Deliberately covers the cases the UI has to handle:

* all five `ExecutionStatus` values, including `skipped` (sender not matched)
* drafts on both sides of the 0.6 `confidence_threshold`
* one `used_fallback=True` draft (drives FallbackWarning)
* one log with three draft versions (drives the history endpoint)
* an exact-email rule shadowing a domain rule (`minh.tran@fpt.edu.vn` vs
  `@fpt.edu.vn`) — exact always wins
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Allow `python scripts/seed_dev.py` from the backend/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, func, select

from src.auto_reply.infrastructure.models import (
    EntryType,
    ExecutionStatus,
    GeneratedDraft,
    MatchLog,
    WhitelistEntry,
)
from src.database import db_session, init_db

NOW = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------


@dataclass
class DraftSpec:
    template_id: str
    confidence: float
    provider: str
    text: str
    used_fallback: bool = False


@dataclass
class LogSpec:
    hours_ago: float
    sender: str
    sender_name: str
    subject: str
    matched: str | None  # whitelist value that matched; None => skipped
    status: ExecutionStatus
    error_detail: str | None = None
    processing_ms: int | None = None
    retry_count: int = 0
    drafts: list[DraftSpec] = field(default_factory=list)


# value, entry_type, days_ago_created
WHITELIST_SPECS: list[tuple[str, EntryType, int]] = [
    ("ceo@bigclient.vn", EntryType.EMAIL, 30),
    ("minh.tran@fpt.edu.vn", EntryType.EMAIL, 21),
    ("hr@vinagroup.vn", EntryType.EMAIL, 28),
    ("billing@cloudvendor.com", EntryType.EMAIL, 14),
    ("support@techpartner.io", EntryType.EMAIL, 12),
    ("noreply@jira.atlassian.net", EntryType.EMAIL, 9),
    ("@partner.co.jp", EntryType.DOMAIN, 25),
    ("@fpt.edu.vn", EntryType.DOMAIN, 35),
    ("@fpt.com.vn", EntryType.DOMAIN, 35),
    ("@student.fpt.edu.vn", EntryType.DOMAIN, 7),
]


_VI_SUPPORT = (
    "Chào anh/chị,\n\n"
    "Cảm ơn anh/chị đã liên hệ với bộ phận hỗ trợ. Chúng tôi đã tiếp nhận "
    "yêu cầu và đang kiểm tra sự cố được mô tả. Đội kỹ thuật sẽ phản hồi "
    "trong vòng 24 giờ làm việc.\n\nTrân trọng,\nBộ phận Hỗ trợ Kỹ thuật"
)
_VI_PRICING = (
    "Chào anh/chị,\n\n"
    "Cảm ơn anh/chị đã quan tâm đến dịch vụ của chúng tôi. Tôi xin gửi kèm "
    "bảng báo giá cho gói dịch vụ anh/chị đề cập. Rất mong có cơ hội trao "
    "đổi thêm về nhu cầu cụ thể.\n\nTrân trọng,\nPhòng Kinh doanh"
)
_VI_GENERAL = (
    "Chào anh/chị,\n\n"
    "Cảm ơn anh/chị đã gửi email. Chúng tôi đã nhận được thông tin và sẽ "
    "phản hồi trong thời gian sớm nhất.\n\nTrân trọng"
)

LOG_SPECS: list[LogSpec] = [
    # ---- recent, completed, high confidence -------------------------------
    LogSpec(
        1.5, "ceo@bigclient.vn", "Nguyen Van Hung",
        "Re: Q3 contract renewal — revised terms",
        "ceo@bigclient.vn", ExecutionStatus.COMPLETED, processing_ms=2140,
        drafts=[DraftSpec("PRICING_INQUIRY", 0.94, "groq", _VI_PRICING)],
    ),
    LogSpec(
        3.0, "support@techpartner.io", "TechPartner Support",
        "Ticket #4821 — API rate limit increase request",
        "support@techpartner.io", ExecutionStatus.COMPLETED, processing_ms=1780,
        drafts=[DraftSpec("TECH_SUPPORT", 0.88, "groq", _VI_SUPPORT)],
    ),
    LogSpec(
        4.25, "minh.tran@fpt.edu.vn", "Tran Quang Minh",
        "Lịch bảo vệ đồ án tốt nghiệp kỳ Fall 2026",
        # exact-email rule wins over the @fpt.edu.vn domain rule
        "minh.tran@fpt.edu.vn", ExecutionStatus.COMPLETED, processing_ms=3010,
        drafts=[DraftSpec("GENERAL_GREETING", 0.71, "gemini", _VI_GENERAL)],
    ),
    # ---- three draft versions: exercises the history endpoint -------------
    LogSpec(
        6.0, "billing@cloudvendor.com", "CloudVendor Billing",
        "Invoice INV-2026-0714 is now overdue",
        "billing@cloudvendor.com", ExecutionStatus.COMPLETED, processing_ms=4180,
        drafts=[
            DraftSpec("GENERAL_GREETING", 0.42, "mock", _VI_GENERAL, used_fallback=True),
            DraftSpec("PRICING_INQUIRY", 0.63, "gemini", _VI_PRICING),
            DraftSpec("PRICING_INQUIRY", 0.91, "groq", _VI_PRICING),
        ],
    ),
    # ---- below threshold, fell back --------------------------------------
    LogSpec(
        8.5, "hr@vinagroup.vn", "VinaGroup HR",
        "Fwd: Fwd: Fwd: (no subject)",
        "hr@vinagroup.vn", ExecutionStatus.COMPLETED, processing_ms=1520,
        drafts=[
            DraftSpec("GENERAL_GREETING", 0.31, "mock", _VI_GENERAL, used_fallback=True)
        ],
    ),
    LogSpec(
        11.0, "sato@partner.co.jp", "Sato Kenji",
        "Meeting request — integration roadmap",
        "@partner.co.jp", ExecutionStatus.COMPLETED, processing_ms=2670,
        drafts=[DraftSpec("GENERAL_GREETING", 0.58, "gemini", _VI_GENERAL, used_fallback=True)],
    ),
    # ---- failures ---------------------------------------------------------
    LogSpec(
        13.0, "noreply@jira.atlassian.net", "Jira",
        "[JIRA] 14 issues assigned to you",
        "noreply@jira.atlassian.net", ExecutionStatus.FAILED,
        error_detail=(
            "InvalidEmailContentError: email body contains no extractable text "
            "(HTML-only notification)"
        ),
        processing_ms=310,
    ),
    LogSpec(
        16.5, "lan.pham@fpt.com.vn", "Pham Thi Lan",
        "Ảnh chụp màn hình lỗi hệ thống",
        "@fpt.com.vn", ExecutionStatus.FAILED,
        error_detail="InvalidEmailContentError: message contains only inline images",
        processing_ms=280,
    ),
    LogSpec(
        22.0, "duc.nguyen@fpt.edu.vn", "Nguyen Minh Duc",
        "Đăng ký môn học kỳ tới",
        "@fpt.edu.vn", ExecutionStatus.FAILED,
        error_detail="LLMRoutingError: all routing providers failed after 3 attempts",
        processing_ms=31240, retry_count=3,
    ),
    # ---- in flight --------------------------------------------------------
    LogSpec(
        0.15, "ceo@bigclient.vn", "Nguyen Van Hung",
        "Urgent: revised SOW attached",
        "ceo@bigclient.vn", ExecutionStatus.PROCESSING,
    ),
    LogSpec(
        0.05, "support@techpartner.io", "TechPartner Support",
        "Ticket #4830 — webhook delivery failures",
        "support@techpartner.io", ExecutionStatus.PENDING,
    ),
    LogSpec(
        0.02, "thu.le@student.fpt.edu.vn", "Le Anh Thu",
        "Xin phép nghỉ học buổi thực hành",
        "@student.fpt.edu.vn", ExecutionStatus.PENDING,
    ),
    # ---- skipped: sender never matched the whitelist ----------------------
    LogSpec(
        2.0, "newsletter@medium.com", "Medium Daily Digest",
        "Your daily reading list",
        None, ExecutionStatus.SKIPPED,
    ),
    LogSpec(
        5.5, "promo@shopee.vn", "Shopee",
        "🔥 Sale 12.12 — giảm đến 50%",
        None, ExecutionStatus.SKIPPED,
    ),
    LogSpec(
        9.0, "recruiter@randomagency.com", "Talent Solutions",
        "Exciting opportunity for a Senior Engineer",
        None, ExecutionStatus.SKIPPED,
    ),
    LogSpec(
        19.0, "security@github.com", "GitHub",
        "[GitHub] A third-party OAuth application was authorized",
        None, ExecutionStatus.SKIPPED,
    ),
    LogSpec(
        26.0, "no-reply@linkedin.com", "LinkedIn",
        "You appeared in 9 searches this week",
        None, ExecutionStatus.SKIPPED,
    ),
    # ---- older history, spread across the 7-day dashboard window ----------
    LogSpec(
        30.0, "hr@vinagroup.vn", "VinaGroup HR",
        "Onboarding checklist for new hires",
        "hr@vinagroup.vn", ExecutionStatus.COMPLETED, processing_ms=1980,
        drafts=[DraftSpec("GENERAL_GREETING", 0.77, "groq", _VI_GENERAL)],
    ),
    LogSpec(
        38.0, "yamada@partner.co.jp", "Yamada Taro",
        "Re: API specification v2 review",
        "@partner.co.jp", ExecutionStatus.COMPLETED, processing_ms=2440,
        drafts=[DraftSpec("TECH_SUPPORT", 0.85, "groq", _VI_SUPPORT)],
    ),
    LogSpec(
        47.0, "billing@cloudvendor.com", "CloudVendor Billing",
        "Your subscription renews in 7 days",
        "billing@cloudvendor.com", ExecutionStatus.COMPLETED, processing_ms=1650,
        drafts=[DraftSpec("PRICING_INQUIRY", 0.90, "groq", _VI_PRICING)],
    ),
    LogSpec(
        53.0, "huong.vo@fpt.edu.vn", "Vo Thi Huong",
        "Thông báo lịch nghỉ lễ",
        "@fpt.edu.vn", ExecutionStatus.COMPLETED, processing_ms=2210,
        drafts=[DraftSpec("GENERAL_GREETING", 0.68, "gemini", _VI_GENERAL)],
    ),
    LogSpec(
        61.0, "spam@unknown-domain.xyz", "Unknown",
        "Congratulations! You have won",
        None, ExecutionStatus.SKIPPED,
    ),
    LogSpec(
        72.0, "support@techpartner.io", "TechPartner Support",
        "Ticket #4712 — resolved",
        "support@techpartner.io", ExecutionStatus.COMPLETED, processing_ms=1420,
        drafts=[DraftSpec("TECH_SUPPORT", 0.93, "groq", _VI_SUPPORT)],
    ),
    LogSpec(
        88.0, "ceo@bigclient.vn", "Nguyen Van Hung",
        "Partnership proposal — follow up",
        "ceo@bigclient.vn", ExecutionStatus.COMPLETED, processing_ms=3320,
        drafts=[
            DraftSpec("PRICING_INQUIRY", 0.55, "mock", _VI_PRICING, used_fallback=True),
            DraftSpec("PRICING_INQUIRY", 0.87, "groq", _VI_PRICING),
        ],
    ),
    LogSpec(
        104.0, "tuan.hoang@fpt.com.vn", "Hoang Anh Tuan",
        "Báo cáo tiến độ dự án tuần 28",
        "@fpt.com.vn", ExecutionStatus.COMPLETED, processing_ms=2890,
        drafts=[DraftSpec("GENERAL_GREETING", 0.74, "gemini", _VI_GENERAL)],
    ),
    LogSpec(
        126.0, "hr@vinagroup.vn", "VinaGroup HR",
        "Annual performance review scheduling",
        "hr@vinagroup.vn", ExecutionStatus.COMPLETED, processing_ms=2050,
        drafts=[DraftSpec("GENERAL_GREETING", 0.81, "groq", _VI_GENERAL)],
    ),
    LogSpec(
        141.0, "digest@stackoverflow.email", "Stack Overflow",
        "Top questions this week",
        None, ExecutionStatus.SKIPPED,
    ),
    LogSpec(
        158.0, "billing@cloudvendor.com", "CloudVendor Billing",
        "Payment method expiring soon",
        "billing@cloudvendor.com", ExecutionStatus.FAILED,
        error_detail="ProviderTimeout: groq request exceeded 30.0s",
        processing_ms=30120, retry_count=2,
    ),
]


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


async def _existing_counts(session) -> dict[str, int]:
    counts = {}
    for name, model in (
        ("whitelist_entries", WhitelistEntry),
        ("match_logs", MatchLog),
        ("generated_drafts", GeneratedDraft),
    ):
        result = await session.execute(select(func.count()).select_from(model))
        counts[name] = result.scalar_one()
    return counts


async def _wipe(session) -> None:
    # Children first — generated_drafts FKs match_logs, which FKs whitelist_entries.
    await session.execute(delete(GeneratedDraft))
    await session.execute(delete(MatchLog))
    await session.execute(delete(WhitelistEntry))


async def seed(reset: bool) -> int:
    await init_db()

    async with db_session() as session:
        counts = await _existing_counts(session)
        if any(counts.values()):
            if not reset:
                print("Database already has data:")
                for name, n in counts.items():
                    print(f"  {name}: {n}")
                print("\nRe-run with --reset to wipe and reseed.")
                return 1
            await _wipe(session)
            print("Wiped existing rows.")

        # 1. Whitelist entries
        entries: dict[str, WhitelistEntry] = {}
        for value, entry_type, days_ago in WHITELIST_SPECS:
            entry = WhitelistEntry(
                entry_type=entry_type,
                value=value,
                is_active=True,
                created_at=NOW - timedelta(days=days_ago),
                updated_at=NOW - timedelta(days=days_ago),
                created_by="seed_dev",
            )
            entries[value] = entry
            session.add(entry)

        # Need the generated ids before match_logs can reference them.
        await session.flush()

        # 2. Match logs + 3. drafts
        n_drafts = 0
        for i, spec in enumerate(LOG_SPECS):
            received_at = NOW - timedelta(hours=spec.hours_ago)
            terminal = spec.status in (
                ExecutionStatus.COMPLETED,
                ExecutionStatus.FAILED,
                ExecutionStatus.SKIPPED,
            )
            processed_at = (
                received_at + timedelta(milliseconds=spec.processing_ms or 0)
                if terminal
                else None
            )
            entry = entries[spec.matched] if spec.matched else None

            log = MatchLog(
                gmail_message_id=f"seed-msg-{i:04d}",
                gmail_thread_id=f"seed-thread-{i:04d}",
                sender_email=spec.sender,
                sender_name=spec.sender_name,
                subject=spec.subject,
                whitelist_entry_id=entry.id if entry else None,
                matched_rule=spec.matched,
                status=spec.status,
                retry_count=spec.retry_count,
                error_detail=spec.error_detail,
                processing_ms=spec.processing_ms,
                received_at=received_at,
                processed_at=processed_at,
            )
            session.add(log)
            await session.flush()  # need log.id for the drafts

            for version, draft in enumerate(spec.drafts, start=1):
                session.add(
                    GeneratedDraft(
                        match_log_id=log.id,
                        version=version,
                        draft_text=draft.text,
                        template_id=draft.template_id,
                        confidence_score=draft.confidence,
                        extracted_data={
                            "sender_name": spec.sender_name,
                            "subject": spec.subject,
                        },
                        provider_used=draft.provider,
                        used_fallback=draft.used_fallback,
                        # Regenerations happen a few minutes apart, so history
                        # sorts sensibly oldest-first.
                        created_at=(processed_at or received_at)
                        + timedelta(minutes=3 * (version - 1)),
                    )
                )
                n_drafts += 1

    print(
        f"Seeded {len(WHITELIST_SPECS)} whitelist entries, "
        f"{len(LOG_SPECS)} match logs, {n_drafts} drafts."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the dev database.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing whitelist/log/draft rows before seeding.",
    )
    args = parser.parse_args()
    return asyncio.run(seed(reset=args.reset))


if __name__ == "__main__":
    raise SystemExit(main())
