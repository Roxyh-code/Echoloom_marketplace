from uuid import uuid4
from sqlalchemy import select
from echoloom.db import Character, CreatorRequest, Portrait, sessions
from test_marketplace import register_account, login
from test_marketplace_scene import add_other_account
from test_voice_identity import create_valid_character

def test_missing_portrait_recovery_is_idempotent_and_owner_only(setup):
    client, _, _, settings, engine = setup
    owner = register_account(setup)
    cid = create_valid_character(client,"Mira")
    with sessions(engine)() as db:
        c=db.get(Character,cid)
        c.current_image_id=None
        for p in db.scalars(select(Portrait).where(Portrait.character_id==cid)):
            (settings.image_directory/p.file_path).unlink(missing_ok=True)
        db.add(CreatorRequest(id=str(uuid4()),owner_id=owner,scope="character",
            payload={},status="pending",result={"character_id":cid,"phase":"portrait_pending"}))
        db.commit()
    path=f"/api/creator/characters/{cid}/portrait"
    assert client.get(path+"/status").json()["state"]=="interrupted"
    r=client.post(path+"/recover",json={})
    assert r.status_code==200,r.text
    data=r.json()
    assert data["id"]==cid and data["profile_version"]==1 and data["current_image_id"]
    assert client.get(path+"/status").json()["state"]=="ready"
    assert client.post(path+"/recover",json={}).json()["current_image_id"]==data["current_image_id"]
    assert len(client.get("/api/creator/characters").json())==1
    add_other_account(setup)
    login(client,"bob")
    assert client.get(path+"/status").status_code==404
    assert client.post(path+"/recover",json={}).status_code==404
