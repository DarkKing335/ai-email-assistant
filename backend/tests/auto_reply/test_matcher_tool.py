import pytest

from src.auto_reply.tools.matcher_tool import MatcherTool
from src.auto_reply.tools.whitelist_tool import WhitelistTool


@pytest.mark.asyncio
async def test_matcher_precedence(db_session):
    wl_tool = WhitelistTool(db_session)
    await wl_tool.create_entry("@company.com")
    await wl_tool.create_entry("vip@company.com")
    
    matcher = MatcherTool(db_session)
    
    # 1. Exact match takes precedence over the domain rule
    res1 = await matcher.match("vip@company.com")
    assert res1 is not None
    assert res1.match_type == "exact_email"
    assert res1.matched_rule == "vip@company.com"
    
    # 2. Domain match fallback
    res2 = await matcher.match("other@company.com")
    assert res2 is not None
    assert res2.match_type == "domain"
    assert res2.matched_rule == "@company.com"
    
    # 3. No match
    res3 = await matcher.match("random@other.com")
    assert res3 is None
