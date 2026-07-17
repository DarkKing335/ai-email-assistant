import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.auto_reply.tools.whitelist_tool import WhitelistTool


@pytest.mark.asyncio
async def test_create_and_get_whitelist_api(override_get_db, db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create
        payload = {"value": "api@test.com", "priority": 10}
        resp = await client.post("/api/v1/whitelist", json=payload)
        
        assert resp.status_code == 201
        data = resp.json()
        assert data["value"] == "api@test.com"
        assert data["priority"] == 10
        entry_id = data["id"]
        
        # Get
        resp2 = await client.get(f"/api/v1/whitelist/{entry_id}")
        assert resp2.status_code == 200
        assert resp2.json()["value"] == "api@test.com"


@pytest.mark.asyncio
async def test_update_whitelist_api(override_get_db, db_session):
    # Setup
    tool = WhitelistTool(db_session)
    entry = await tool.create_entry("old@test.com")
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Update
        payload = {"value": "new@test.com"}
        resp = await client.put(f"/api/v1/whitelist/{entry.id}", json=payload)
        
        assert resp.status_code == 200
        assert resp.json()["value"] == "new@test.com"


@pytest.mark.asyncio
async def test_list_whitelist_api(override_get_db, db_session):
    tool = WhitelistTool(db_session)
    await tool.create_entry("list1@test.com")
    await tool.create_entry("list2@test.com")
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/whitelist")
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        assert len(data["items"]) >= 2
