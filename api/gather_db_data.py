"""Gather and display all data from the aegis_ai_db MongoDB database."""
from pymongo import MongoClient

client = MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=5000)
db = client["aegis_ai_db"]

print("=" * 70)
print("DATABASE: aegis_ai_db")
print("=" * 70)

# --- USERS ---
print("\n[1] USERS")
print("-" * 70)
for u in db.users.find({}, {"password": 0}):
    uname = u.get("username", "?")
    role = u.get("role", "?")
    status = u.get("status", "?")
    print(f"  {uname:<20} role={role:<12} status={status}")

# --- THREAT PREDICTIONS ---
print(f"\n[2] THREAT PREDICTIONS ({db.threat_predictions.count_documents({})} total)")
print("-" * 70)
for p in db.threat_predictions.find().sort("created_at", -1).limit(10):
    tel = p.get("telemetry", {})
    ml = p.get("ml_output", {})
    obj = tel.get("object", "?")
    conf = tel.get("confidence", "?")
    dist = tel.get("distance_km", "?")
    score = ml.get("threat_score", "?")
    level = ml.get("threat_level", "?")
    print(f"  {obj:<15} conf={conf}  dist={dist}km  score={score}  level={level}")

# --- VISION DETECTIONS ---
print(f"\n[3] VISION DETECTIONS ({db.vision_detections.count_documents({})} total)")
print("-" * 70)
for d in db.vision_detections.find().sort("created_at", -1).limit(10):
    fname = d.get("original_filename", "?")
    dets = d.get("detections", [])
    status = d.get("status", "?")
    print(f"  file={fname:<35} objects={len(dets)}  status={status}")

# --- AUDIT LOGS ---
print(f"\n[4] AUDIT LOGS ({db.audit_logs.count_documents({})} total)")
print("-" * 70)
for a in db.audit_logs.find().sort("timestamp", -1).limit(10):
    action = a.get("action", "?")
    details = a.get("details", "?")
    ip = a.get("ip_address", "?")
    print(f"  action={action:<22} details={details:<25} ip={ip}")

# --- INTELLIGENCE REPORTS ---
print(f"\n[5] INTELLIGENCE REPORTS ({db.intelligence_reports.count_documents({})} total)")
print("-" * 70)
for r in db.intelligence_reports.find().sort("created_at", -1):
    online = r.get("online", "?")
    content = str(r.get("content", ""))
    preview = content[:100].replace("\n", " ")
    print(f"  online={online}  chars={len(content)}  preview={preview}...")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
for name in sorted(db.list_collection_names()):
    count = db[name].count_documents({})
    print(f"  {name:<25} {count:>6} documents")
print("=" * 70)

client.close()
