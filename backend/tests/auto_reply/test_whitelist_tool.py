import pytest

from src.auto_reply.infrastructure.models import EntryType
from src.auto_reply.tools.whitelist_tool import (
    WhitelistDuplicateError,
    WhitelistEntryNotFound,
    WhitelistTool,
    WhitelistValidationError,
)


@pytest.mark.asyncio
async def test_create_valid_email_entry(db_session):
    tool = WhitelistTool(db_session)
    entry = await tool.create_entry("alice@example.com")
    
    assert entry.id is not None
    assert entry.entry_type == EntryType.EMAIL
    assert entry.value == "alice@example.com"
    assert entry.is_active is True


@pytest.mark.asyncio
async def test_create_valid_domain_entry(db_session):
    tool = WhitelistTool(db_session)
    entry = await tool.create_entry("@example.com")
    
    assert entry.entry_type == EntryType.DOMAIN
    assert entry.value == "@example.com"


@pytest.mark.asyncio
async def test_create_duplicate_raises_error(db_session):
    tool = WhitelistTool(db_session)
    await tool.create_entry("bob@example.com")
    
    with pytest.raises(WhitelistDuplicateError):
        await tool.create_entry("BOB@example.com") # case-insensitive


@pytest.mark.asyncio
async def test_create_invalid_email_raises_error(db_session):
    tool = WhitelistTool(db_session)
    with pytest.raises(WhitelistValidationError):
        await tool.create_entry("not-an-email")


@pytest.mark.asyncio
async def test_soft_delete_and_reactivate(db_session):
    tool = WhitelistTool(db_session)
    entry = await tool.create_entry("charlie@example.com")
    
    await tool.delete_entry(entry.id)
    
    # Should not be found after soft delete
    with pytest.raises(WhitelistEntryNotFound):
        await tool.get_entry(entry.id)
        
    # Re-creating should reactivate
    reactivated = await tool.create_entry("charlie@example.com", priority=10)
    assert reactivated.id == entry.id
    assert reactivated.is_active is True
    assert reactivated.priority == 10
