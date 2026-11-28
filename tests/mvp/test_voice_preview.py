from pydantic import SecretStr
from echoloom.voice.audio import AudioService
from echoloom.voice.elevenlabs import ElevenLabsCatalog
from echoloom.voice.schemas import VoiceCatalogResponse
from test_voice_identity import voices, create_valid_character
from test_marketplace import register_account, login
from test_marketplace_scene import add_other_account

def test_dialogue_preview_is_authorized_same_line_and_cached(setup,monkeypatch,tmp_path):
    client,text,_,settings,_=setup
    settings.elevenlabs_enabled=True
    settings.elevenlabs_audio_enabled=True
    settings.elevenlabs_api_key=SecretStr("test-key")
    settings.elevenlabs_audio_directory=tmp_path/"audio"
    monkeypatch.setattr(ElevenLabsCatalog,"catalog",lambda self:VoiceCatalogResponse(enabled=True,reason="ready",voices=voices()))
    line="Stay close. Whatever waits beyond that door, I will not let it take you."
    calls=[]
    monkeypatch.setattr(AudioService,"synthesize",lambda self,voice,text: (calls.append((voice,text)) or b"ID3test"))
    monkeypatch.setattr(type(text),"rank_voices",lambda self,features,candidates: {"choices":[{"voice_id":x,"reason":"fit"} for x in ["a","b","c"]],"sample_text":line},raising=False)
    owner=register_account(setup)
    cid=create_valid_character(client,"Lucien")
    path="/api/voice/characters/"+cid
    r=client.post(path+"/recommend")
    assert r.status_code==200,r.text
    rec=r.json()
    assert rec["sample_text"]==line and not calls
    payload={"voice_id":"a","expected_profile_version":rec["profile_version"],"sample_id":rec["sample_id"]}
    assert client.post(path+"/preview",json=payload|{"text":"arbitrary"}).status_code==422
    assert client.post(path+"/preview",json=payload|{"voice_id":"unknown"}).status_code==422
    assert client.post(path+"/preview",json=payload|{"sample_id":"0"*64}).status_code==409
    assert client.post(path+"/preview",json=payload).headers["x-audio-cache"]=="miss"
    assert client.post(path+"/preview",json=payload).headers["x-audio-cache"]=="hit"
    assert client.post(path+"/preview",json=payload|{"voice_id":"b"}).status_code==200
    assert calls==[("a",line),("b",line)]
    add_other_account(setup)
    login(client,"bob")
    assert client.post(path+"/preview",json=payload).status_code==404
