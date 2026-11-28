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

def test_research_enriches_profile_and_original_skips_agent(setup,monkeypatch):
    client,text,_,settings,_=setup
    from pydantic import SecretStr
    settings.firecrawl_enabled=True
    settings.firecrawl_api_key=SecretStr("test")
    register_account(setup)
    calls=[]
    def classify(self,description):
        if "Snape" in description:
            return ResearchIdentity(kind="existing_fictional",name="Snape",work="Harry Potter")
        return ResearchIdentity(kind="original_or_unclear")
    def research(self,identity):
        calls.append(identity.name)
        return {"identity":identity.model_dump(),"facts":lore()["facts"],
                "sources":["https://example.com/a","https://example.com/b"],"credits_used":5}
    def synth(self,description,research):
        assert description=="Snape from Harry Potter"
        return Profile(name="Snape",backstory="A researched backstory")
    monkeypatch.setattr(type(text),"identify_research_character",classify,raising=False)
    monkeypatch.setattr(type(text),"generate_researched",synth,raising=False)
    monkeypatch.setattr(CharacterResearch,"research",research)
    def create(desc):
        r=client.post("/api/creator/characters",json={"request_id":str(uuid4()),"description":desc,"research":True})
        assert r.status_code==201,r.text
        return client.get("/api/characters/"+r.json()["character_id"]).json()
    c=create("Snape from Harry Potter")
    assert c["profile"]["backstory"]=="A researched backstory"
    assert len(c["research"]["sources"])==2
    assert create("An original wizard")["research"] is None
    assert calls==["Snape"]
