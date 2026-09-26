"""MongoDB product catalog access. Screen 1 and Screen 5 read/write here only."""
from datetime import datetime, timezone

from bson import ObjectId


def _to_out(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


def list_products(db, category: str | None = None, q: str | None = None,
                  active: bool = True) -> list[dict]:
    filt: dict = {"active": active}
    if category:
        filt["category"] = category
    if q:
        filt["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"tags": {"$regex": q, "$options": "i"}},
        ]
    return [_to_out(d) for d in db.products.find(filt).sort("title", 1)]


def get_product(db, product_id: str) -> dict | None:
    try:
        oid = ObjectId(product_id)
    except Exception:
        return None
    doc = db.products.find_one({"_id": oid})
    return _to_out(doc) if doc else None


def get_products_by_ids(db, product_ids: list[str]) -> dict[str, dict]:
    """Map of str(id) -> product doc for the given ids (any active flag)."""
    oids = []
    for pid in product_ids:
        try:
            oids.append(ObjectId(pid))
        except Exception:
            continue
    docs = db.products.find({"_id": {"$in": oids}})
    return {str(d["_id"]): _to_out(d) for d in docs}


def create_product(db, data: dict) -> dict:
    doc = dict(data)
    doc["updated_at"] = datetime.now(timezone.utc)
    result = db.products.insert_one(doc)
    return get_product(db, str(result.inserted_id))


def update_product(db, product_id: str, data: dict) -> dict | None:
    try:
        oid = ObjectId(product_id)
    except Exception:
        return None
    data = {k: v for k, v in data.items() if k not in ("id", "_id")}
    data["updated_at"] = datetime.now(timezone.utc)
    res = db.products.update_one({"_id": oid}, {"$set": data})
    if res.matched_count == 0:
        return None
    return get_product(db, product_id)


def distinct_categories(db) -> list[str]:
    return sorted(db.products.distinct("category", {"active": True}))
