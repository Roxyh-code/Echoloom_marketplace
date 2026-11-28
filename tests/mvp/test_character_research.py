from uuid import uuid4
import json
import httpx
from echoloom.config import Settings
from echoloom.character_research import CharacterResearch,ResearchIdentity
from echoloom.schemas import Profile
from test_marketplace import register_account

def lore():
    return {"identity_confirmed":True,"facts":[
        {"category":"identity","detail":"A potions professor","source_url":"https://example.com/a"},
        {"category":"speech","detail":"Deliberate speech","source_url":"https://example.com/b"},
        {"category":"personality","detail":"Reserved","source_url":"https://example.com/a"}]}

def test_agent_autonomous_search_and_cache():
    s=Settings(_env_file=None,firecrawl_enabled=True,firecrawl_api_key="test")
    calls=[]
    def respond(r):
        calls.append(r)
        assert r.url.path=="/v2/agent"
        data=json.loads(r.content)
        assert "urls" not in data and data["maxCredits"]==100 and "schema" in data
        return httpx.Response(200,json={"success":True,"status":"completed","data":lore(),"creditsUsed":5})
    a=CharacterResearch(s,transport=httpx.MockTransport(respond))
    i=ResearchIdentity(kind="existing_fictional",name="Snape",work="Harry Potter")
    assert len(a.research(i)["sources"])==2
    assert a.research(i)["credits_used"]==5
    assert len(calls)==1

def test_discovery_search_with_scrape():
    s=Settings(_env_file=None,firecrawl_enabled=True,firecrawl_api_key="test")
    def respond(r):
        assert r.url.path=="/v2/search"
        body=json.loads(r.content)
        assert body["limit"]==3 and body["scrapeOptions"]["formats"]==["markdown"]
        return httpx.Response(200,json={"success":True,"data":{"web":[
            {"url":"https://example.com/a","markdown":"A fictional professor."}]}})
    a=CharacterResearch(s,transport=httpx.MockTransport(respond))
    assert a.discover(ResearchIdentity(kind="existing_fictional",name="Snape",work="Harry Potter"))==[
        {"url":"https://example.com/a","excerpt":"A fictional professor."}]

def test_background_research_does_not_block_and_apply_is_explicit(setup,monkeypatch):
    from threading import Event
    import time
    from pydantic import SecretStr
    client,text,_,settings,_=setup
    settings.firecrawl_enabled=True
    settings.firecrawl_api_key=SecretStr("test")
    register_account(setup)
    entered,release=Event(),Event()
    calls=[]
    def classify(self,description):
        if "Snape" in description:
            return ResearchIdentity(kind="existing_fictional",name="Snape",work="Harry Potter")
        return ResearchIdentity(kind="original_or_unclear")
    def discover(self,identity):
        return [{"url":"https://example.com/a","excerpt":"A fictional professor."}]
    def research(self,identity,discovered=None):
        calls.append(identity.name)
        entered.set()
        assert release.wait(5)
        assert discovered
        return {"identity":identity.model_dump(),"facts":lore()["facts"],
                "sources":["https://example.com/a","https://example.com/b"],"credits_used":5}
    def synth(self,description,research):
        return Profile(name="Snape",backstory="A researched backstory")
    monkeypatch.setattr(type(text),"identify_research_character",classify,raising=False)
    monkeypatch.setattr(type(text),"generate_researched",synth,raising=False)
    monkeypatch.setattr(CharacterResearch,"discover",discover)
    monkeypatch.setattr(CharacterResearch,"research",research)
    def create(desc):
        r=client.post("/api/creator/characters",json={"request_id":str(uuid4()),"description":desc,"research":True})
        assert r.status_code==201,r.text
        return r.json()["character_id"]
    def wait_state(cid,state):
        end=time.monotonic()+5
        while time.monotonic()<end:
            r=client.get(f"/api/creator/characters/{cid}/research")
            assert r.status_code==200,r.text
            if r.json().get("status")==state:return r.json()
            time.sleep(.025)
        raise AssertionError("Research did not reach "+state)
    try:
        cid=create("Snape from Harry Potter")
        assert entered.wait(3)
        c=client.get("/api/characters/"+cid).json()
        assert c["profile_version"]==1 and c["profile"]["backstory"]!="A researched backstory"
    finally:
        release.set()
    data=wait_state(cid,"proposal")
    assert data["proposal"]["backstory"]=="A researched backstory"
    assert len(data["sources"])==2
    path=f"/api/creator/characters/{cid}/research/apply"
    r=client.post(path,json={})
    assert r.status_code==200,r.text
    c=r.json()
    assert c["profile_version"]==2 and c["profile"]["backstory"]=="A researched backstory"
    assert c["profile"]["name"]=="Evelyn"
    assert client.post(path,json={}).json()["profile_version"]==2
    wait_state(create("An original wizard"),"skipped")
    assert calls==["Snape"]
