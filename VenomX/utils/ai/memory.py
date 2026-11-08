# All rights reserved.
#
# Mongo-backed memory for the AI layer: per-chat conversation history and
# per-chat persona / settings. The kill switch lives here too so it survives
# restarts. History is redacted BEFORE storage, so a leaked database still
# holds nothing sensitive the chat said.

from VenomX.core.mongo import mongodb

aichatdb = mongodb.aichat
aisetdb = mongodb.aisettings
aifacts = mongodb.aifacts


async def get_history(chat_id: int, limit: int = 12) -> list:
    docs = aichatdb.find({"chat_id": chat_id}).sort("_id", -1).limit(limit)
    out = [{"role": d["role"], "content": d["content"]} async for d in docs]
    return list(reversed(out))


async def push(chat_id: int, user_id: int, role: str, content: str) -> None:
    from VenomX.utils.ai.safety import redact

    await aichatdb.insert_one(
        {"chat_id": chat_id, "user_id": user_id, "role": role,
         "content": redact(content)[:4000]}
    )
    # Trim: keep only the most recent pairs (doc per turn).
    ids = [d["_id"] async for d in aichatdb.find(
        {"chat_id": chat_id}, {"_id": 1}
    ).sort("_id", -1).skip(40)]
    if ids:
        await aichatdb.delete_many({"_id": {"$in": ids}})


async def clear(chat_id: int) -> int:
    res = await aichatdb.delete_many({"chat_id": chat_id})
    return res.deleted_count


# ------------------------------------------------------------- persona

async def get_persona(chat_id: int) -> str | None:
    doc = await aisetdb.find_one({"chat_id": chat_id, "key": "persona"})
    if doc:
        return str(doc.get("value") or "")[:400] or None
    return None


async def set_persona(chat_id: int, text: str) -> str:
    value = str(text or "")[:400]
    await aisetdb.update_one(
        {"chat_id": chat_id, "key": "persona"},
        {"$set": {"value": value}},
        upsert=True,
    )
    return value


# ------------------------------------------------------------- settings

_VALID_KEYS = {"autodj", "ai_on"}


async def get_setting(chat_id: int, key: str, default=None):
    if key not in _VALID_KEYS:
        raise ValueError(f"unknown ai setting: {key}")
    doc = await aisetdb.find_one({"chat_id": chat_id, "key": key})
    if doc is None:
        return default
    return doc.get("value", default)


async def set_setting(chat_id: int, key: str, value) -> None:
    if key not in _VALID_KEYS:
        raise ValueError(f"unknown ai setting: {key}")
    await aisetdb.update_one(
        {"chat_id": chat_id, "key": key},
        {"$set": {"value": value}},
        upsert=True,
    )


# ------------------------------------------------------------- fun facts

async def get_fact(title: str) -> str | None:
    doc = await aifacts.find_one({"title": title})
    return doc and str(doc.get("fact") or "") or None


async def save_fact(title: str, fact: str) -> None:
    await aifacts.update_one(
        {"title": title}, {"$set": {"fact": str(fact)[:600]}}, upsert=True
    )
