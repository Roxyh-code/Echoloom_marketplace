from echoloom.voice.elevenlabs import ElevenLabsCatalog
from echoloom.voice.schemas import VoiceCatalogResponse, CatalogVoice
from echoloom.voice.matching import recommend
from echoloom.schemas import Profile
from test_marketplace import register_account, seed_character, publish
from test_marketplace_scene import request_scene, listing_ref, private_ref
from uuid import uuid4


def create_valid_character(client, name):
    r = client.post('/api/rehearsal/characters', json={'operation_id': str(uuid4()), 'name': name, 'description': 'A quiet fictional investigator.'})
    assert r.status_code == 201, r.text
    return r.json()['character_id']


def voices():
    return [CatalogVoice(voice_id=x,name=x,preview_url="https://example.com/a.mp3",description=t)
            for x,t in [("a","calm"),("b","warm"),("c","deep")]]


def test_matching_validates_model_ids():
    class Model:
        def rank_voices(self, features, candidates):
            return {"choices":[{"voice_id":x,"reason":"fit"} for x in ["b","a","c"]]}
    result, method = recommend(Profile(name="Mira"), voices(), Model())
    assert method == "ai" and [x["voice_id"] for x in result] == ["b","a","c"]
    class Bad:
        def rank_voices(self,*args):
            return {"choices":[{"voice_id":"invented","reason":"fit"}]*3}
    result, method = recommend(Profile(name="Mira"), voices(), Bad())
    assert method == "metadata" and len({x["voice_id"] for x in result}) == 3


def test_selection_and_immutable_listing_cast(setup, monkeypatch):
    client, _, _, settings, _ = setup
    settings.elevenlabs_enabled = True
    monkeypatch.setattr(ElevenLabsCatalog,"catalog",lambda self:VoiceCatalogResponse(enabled=True,reason="ready",voices=voices()))
    owner = register_account(setup)
    a,b = create_valid_character(client, 'Mira'),create_valid_character(client, 'Rowan')
    path="/api/voice/characters/"+a
    assert len(client.post(path+"/recommend").json()["choices"]) == 3
    assert client.put(path,json={"voice_id":"bad","expected_profile_version":1}).status_code == 422
    assert client.put(path,json={"voice_id":"a","expected_profile_version":99}).status_code == 409
    assert client.put(path,json={"voice_id":"a","expected_profile_version":1}).status_code == 200
    listing = publish(client,a)
    before = request_scene(client,[listing_ref(listing),private_ref(b)]).json()
    assert before["document"]["cast"][0]["voice_identity"]["voice_id"] == "a"
    assert client.put(path,json={"voice_id":"b","expected_profile_version":1}).status_code == 200
    old = request_scene(client,[listing_ref(listing),private_ref(b)]).json()
    assert old["document"]["cast"][0]["voice_identity"]["voice_id"] == "a"
    new = publish(client,a)
    assert new["latest_revision"] == listing["latest_revision"] + 1
    scene = request_scene(client,[listing_ref(new),private_ref(b)]).json()
    assert scene["document"]["cast"][0]["voice_identity"]["voice_id"] == "b"
    assert client.get("/api/rehearsal/scenes/"+before["id"]).json()["document"]["cast"][0]["voice_identity"]["voice_id"] == "a"
