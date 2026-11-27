"""Offline demo fixture helpers. Never registered as HTTP routes."""
from uuid import NAMESPACE_URL, uuid5
from secrets import token_urlsafe

from sqlalchemy import select
from ..companion_models import Account
from ..db import Character, Conversation, ProfileRevision, RehearsalScene, uid
from ..local_accounts import password_hash
from ..marketplace_models import CharacterListing, MarketplaceCreator
from ..marketplace_schemas import ListingPublishRequest
from ..marketplace_service import publish_listing
from ..schemas import Profile, Personality
from ..rehearsal_schema import Setup, CastSource
from ..scene_casting import resolve_cast_sources, rebind_marketplace_avatars
from ..rehearsal_domain import new_document, add_node, version, line_count
from ..scene_access import mark_generated, status
from .quote import creator_wallet

ACCOUNTS = ("demo_mira", "demo_rowan", "demo_buyer")
CHARACTERS = (
    ("Mira", "An observant archivist who investigates the disappearance of an ancient map.", ["Curious", "Measured", "Resolute"]),
    ("Rowan", "A lighthouse keeper guarding a secret about a ship that vanished in the fog.", ["Reserved", "Loyal", "Protective"]),
)
# Authored sample text, not an AI-provider result; only for disposable demo DBs.
PASSAGES = (
    "Rain drifted across the abandoned platform. Mira held a folded map beneath her coat. The last train had departed hours ago. A lantern glimmered at the far end of the tracks. Rowan stepped into its light.",
    "You came after all. I thought the letter might frighten you away. The lighthouse has been dark for three nights. Someone removed the lens before the storm arrived. I need to know what you found.",
    "The map was hidden inside an old ledger. Its markings lead beneath the lighthouse. Someone scratched out the final coordinates. I recognized the handwriting on the margin. It belonged to the missing captain.",
    "Rowan looked toward the empty signal tower. He set the lantern on a bench. A gust rattled the glass. He drew a small brass key from his pocket. Mira watched his hand.",
    "The captain left this with me. He said not to open the lower chamber until the tide turned. I kept my promise for seven years. Last night someone tried to take the key. I cannot guard it alone anymore.",
    "Mira unfolded the map across the bench. A thin red line connected the railway to the sea. She pointed to a symbol beside the lighthouse. Rowan recognized the shape of the old service tunnel. The rain began to ease.",
    "We should go before dawn. If the tunnel is flooded we can return. I will not take the key without your permission. But the map suggests someone is already inside. We need to decide together.",
    "A distant bell sounded from the coast. Rowan picked up the lantern. Mira folded the map and waited. The brass key caught the last of the light. Neither of them moved toward the exit yet.",
)


def demo_id(label):
    return str(uuid5(NAMESPACE_URL, "echoloom:disposable-demo-v1:" + label))


def seed_accounts(db):
    if db.scalar(select(Account.id).limit(1)) or db.scalar(select(Character.id).limit(1)) or db.scalar(select(RehearsalScene.id).limit(1)):
        raise ValueError("Seed requires an empty, dedicated demo database.")
    credentials = []
    for username in ACCOUNTS:
        password = token_urlsafe(18)
        db.add(Account(id=demo_id(username), username=username, password_hash=password_hash(password)))
        credentials.append({"username": username, "password": password})
    db.flush()
    for username, (name, description, traits) in zip(ACCOUNTS, CHARACTERS):
        cid = demo_id(name)
        db.add(Character(id=cid, owner_id=demo_id(username), original_description=description))
        db.flush()
        profile = Profile(name=name, short_description=description, backstory=description,
                          personality=Personality(core_traits=traits))
        db.add(ProfileRevision(character_id=cid, version=1, profile_json=profile.model_dump(),
                              change_summary="Prepared fictional demo character"))
        db.add(Conversation(character_id=cid))
        db.flush()
        publish_listing(db, ListingPublishRequest(character_id=cid, name=name,
            short_description=description, tags=["Mystery", "Fantasy"],
            public_personality=traits, rights_basis="original", rights_confirmed=True),
            account_id=demo_id(username))
    db.commit()
    return credentials


def prepare_scene(db):
    for username in ACCOUNTS:
        account = db.get(Account, demo_id(username))
        if not account or account.username != username:
            raise ValueError("Not a seeded demo database.")
    buyer = demo_id(ACCOUNTS[2])
    listings = []
    for username, (name, _, _) in zip(ACCOUNTS, CHARACTERS):
        creator = db.scalar(select(MarketplaceCreator).where(MarketplaceCreator.account_id == demo_id(username)))
        listing = db.scalar(select(CharacterListing).where(CharacterListing.character_id == demo_id(name)))
        if not creator or not listing or listing.creator_id != creator.id or listing.status != "published" or not listing.monetization_enabled:
            raise ValueError("Both creators must verify payout wallets and enable earnings first.")
        listings.append(listing)
    cast = resolve_cast_sources(db, [CastSource(source="listing", listing_id=l.id,
        expected_revision=l.latest_revision) for l in listings], buyer)
    wallets = [creator_wallet(db, actor, buyer) for actor in cast]
    if len(set(wallets)) != 2:
        raise ValueError("Use distinct creator wallets.")
    sid = uid()
    rebind_marketplace_avatars(cast, sid)
    setup = Setup(premise="Two investigators meet at an abandoned railway station to solve a lighthouse mystery.",
                  location="Abandoned coastal railway station", goal="Decide whether to investigate the lighthouse together.")
    doc = new_document(setup.model_dump(), cast, demo=False)
    doc.update(title="The Lighthouse Key · Prepared demo", status="draft")
    v = version(doc)
    speakers = (None, 1, 0, None, 1, None, 0, None)
    for text, speaker in zip(PASSAGES, speakers):
        operation = uid()
        block = dict(id=uid(), type="narration" if speaker is None else "dialogue",
            character_id=None if speaker is None else cast[speaker]["id"], text=text,
            locked=False, user_edited=False, operation_id=operation)
        mark_generated(doc, block)
        add_node(doc, v, [block], doc["initial_state"], operation, "Prepared demo passage", "ai")
    v["revealed"] = line_count(doc, v["head"])
    if v["revealed"] != 40 or doc["free_generated_sentences"] != 40:
        raise ValueError("Prepared scene must contain exactly 40 sentences.")
    row = RehearsalScene(id=sid, owner_id=buyer, document=doc)
    db.add(row)
    db.flush()
    assert status(db, row)["payment_required"]
    db.commit()
    return {"scene_id": sid, "title": doc["title"], "generated_sentences": 40,
            "listing_revisions": [l.latest_revision for l in listings]}
