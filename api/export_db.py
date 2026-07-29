"""Export all MongoDB collections to JSON files in the Downloads folder."""
import json
import os
from datetime import datetime, timezone
from bson import ObjectId
from pymongo import MongoClient

DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads", "aegis_ai_db_export")
os.makedirs(DOWNLOADS, exist_ok=True)

client = MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=5000)
db = client["aegis_ai_db"]


def serialize(doc):
    """Make a MongoDB document JSON-serializable."""
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            doc[key] = str(value)
        elif isinstance(value, datetime):
            doc[key] = value.isoformat()
        elif isinstance(value, dict):
            doc[key] = serialize(value)
        elif isinstance(value, list):
            doc[key] = [serialize(v) if isinstance(v, dict) else str(v) if isinstance(v, ObjectId) else v.isoformat() if isinstance(v, datetime) else v for v in value]
        elif isinstance(value, bytes):
            doc[key] = "<binary>"
    return doc


print(f"Exporting to: {DOWNLOADS}")
print("=" * 60)

total = 0
for name in sorted(db.list_collection_names()):
    docs = []
    for doc in db[name].find():
        docs.append(serialize(doc))

    filepath = os.path.join(DOWNLOADS, f"{name}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(docs, f, indent=2, ensure_ascii=False, default=str)

    size_kb = os.path.getsize(filepath) / 1024
    print(f"  {name:<25} {len(docs):>6} docs  ->  {name}.json ({size_kb:.1f} KB)")
    total += len(docs)

print("=" * 60)
print(f"Total: {total} documents exported to {DOWNLOADS}")

client.close()
