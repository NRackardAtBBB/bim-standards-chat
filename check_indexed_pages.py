#! python3
"""Check what pages are indexed in the vector database"""
import sys
import os

sys.path.insert(0, 'BBB.extension/lib')

from standards_chat.config_manager import ConfigManager
from standards_chat.vector_db_client import VectorDBClient

config = ConfigManager()
vdb = VectorDBClient(config)
collection = vdb.collection

print('Total documents in collection:', collection.count())
print()

# Get all documents
results = collection.get(limit=100)
titles = [(meta.get('title', 'No title'), meta.get('url', '')) for meta in results['metadatas']]

print('Indexed page titles:')
for title, url in sorted(set(titles), key=lambda x: x[0]):
    print('  - {}'.format(title))
