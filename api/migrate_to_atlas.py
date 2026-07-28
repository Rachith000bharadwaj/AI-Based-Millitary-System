"""Database migration script: Local MongoDB -> MongoDB Atlas Cloud."""
import os
import sys
import logging
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

LOCAL_URI = "mongodb://127.0.0.1:27017/"
DB_NAME = "aegis_ai_db"

def migrate(atlas_uri: str):
    logger.info("Connecting to Local MongoDB...")
    local_client = MongoClient(LOCAL_URI, serverSelectionTimeoutMS=5000)
    local_db = local_client[DB_NAME]
    
    logger.info("Connecting to MongoDB Atlas Cloud...")
    atlas_client = MongoClient(atlas_uri, serverSelectionTimeoutMS=10000)
    atlas_client.admin.command('ping')
    logger.info("Successfully connected to MongoDB Atlas!")
    
    atlas_db = atlas_client[DB_NAME]
    
    collections = local_db.list_collection_names()
    logger.info("Found local collections: %s", collections)
    
    total_docs = 0
    for coll_name in collections:
        if coll_name.startswith("system."):
            continue
        docs = list(local_db[coll_name].find())
        if docs:
            atlas_db[coll_name].delete_many({}) # Clear existing
            atlas_db[coll_name].insert_many(docs)
            logger.info("Uploaded %d documents to '%s' on Atlas.", len(docs), coll_name)
            total_docs += len(docs)
            
    logger.info("Migration complete! Total documents uploaded to Cloud: %d", total_docs)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_uri = sys.argv[1]
    else:
        target_uri = os.getenv("MONGO_URI", "")
        
    if not target_uri or "mongodb" not in target_uri:
        print("Usage: python api/migrate_to_atlas.py <ATLAS_MONGO_URI>")
        sys.exit(1)
        
    migrate(target_uri)
