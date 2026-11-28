from uuid import uuid4
from copy import deepcopy
from pydantic import SecretStr
from echoloom.db import sessions, RehearsalScene
from echoloom.voice.audio import AudioService
from echoloom.voice.elevenlabs import ElevenLabsCatalog
from echoloom.voice.schemas import VoiceCatalogResponse
from test_voice_identity import voices
from test_marketplace import register_account, seed_character
from test_marketplace_scene import request_scene, private_ref
from echoloom.rehearsal_domain import add_node, version

def test_audio_authorization_cache_and_budget(setup, monkeypatch, tmp_path):
    client, _, _, settings, engine = setup
    settings.elevenlabs_enabled=True
    settings.elevenlabs_audio_enabled=True
    settings.elevenlabs_api_key=SecretStr("test-key")
    settings.elevenlabs_audio_directory=tmp_path/"audio"
    settings.elevenlabs_audio_daily_chars=11
    settings.elevenlabs_audio_global_daily_chars=20
    monkeypatch.setattr(ElevenLabsCatalog,"catalog",lambda self:VoiceCatalogResponse(enabled=True,reason="ready",voices=voices()))
    calls=[]
    def synth(self,voice,text):
        calls.append((voice,text))
        return b"ID3demo"
    monkeypatch.setattr(AudioService,"synthesize",synth)
    owner=register_account(setup)
    a,b=seed_character(setup,owner),seed_character(setup,owner)
    for cid,voice in [(a,"a"),(b,"b")]:
        assert client.put("/api/voice/characters/"+cid,json={"voice_id":voice,"expected_profile_version":1}).status_code==200
    scene=request_scene(client,[private_ref(a),private_ref(b)]).json()
    sid=scene["id"]
    with sessions(engine)() as db:
        row=db.get(RehearsalScene,sid)
        doc=deepcopy(row.document)
        v=version(doc)
        blocks=[dict(id=str(uuid4()),type="dialogue",character_id=actor["id"],text=text,
            locked=False,user_edited=False,operation_id=str(uuid4())) for actor,text in zip(doc["cast"],["Hello.","Goodbye."])]
        node=add_node(doc,v,blocks,doc["initial_state"],str(uuid4()))
        v["revealed"]=1
        row.document=doc
        db.commit()
        payload=dict(version_id=v["id"],node_id=node["id"],block_id=blocks[0]["id"])
        other=payload|{"block_id":blocks[1]["id"]}
    path="/api/voice/scenes/"+sid+"/audio"
    assert client.post(path,json=other).status_code==404
    r=client.post(path,json=payload)
    assert r.status_code==200 and r.headers["x-audio-cache"]=="miss"
    assert client.post(path,json=payload).headers["x-audio-cache"]=="hit"
    assert calls==[("a","Hello.")]
    with sessions(engine)() as db:
        row=db.get(RehearsalScene,sid)
        doc=deepcopy(row.document)
        version(doc)["revealed"]=2
        row.document=doc
        db.commit()
    assert client.post(path,json=other).status_code==429
    assert len(calls)==1
    client.post("/api/account/logout")
    assert client.post(path,json=payload).status_code==401
