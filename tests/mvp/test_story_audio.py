from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from echoloom.story_audio import SpeechRequest, speech_text


def test_audio_only_revealed_prefix():
    row = SimpleNamespace(owner_id=None, document={"demo":True,"cast":[{"id":"a","slot":0}],
        "versions":{"v":{"head":"n","revealed":1}},"nodes":{"n":{"id":"n","parent":None,
            "blocks":[{"id":"b","type":"dialogue","character_id":"a","text":"First. Second."}]}}})
    assert speech_text(None,row,SpeechRequest(version_id="v",block_id="b",sentence_count=1)) == ("First.",0)
    with pytest.raises(HTTPException) as e:
        speech_text(None,row,SpeechRequest(version_id="v",block_id="b",sentence_count=2))
    assert e.value.status_code == 403
