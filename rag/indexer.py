"""
RAG Indexer for Spark Documentation
Indexes documentation into Azure AI Search with category and source metadata
"""
import os
import json
from pathlib import Path
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile
)
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

load_dotenv()


# Fabric Spark Documentation URLs for indexing
FABRIC_SPARK_DOCS = [
    # Already indexed
    "https://learn.microsoft.com/en-us/fabric/data-engineering/spark-best-practices-overview",
    "https://learn.microsoft.com/en-us/fabric/data-engineering/configure-resource-profile-configurations",
    "https://learn.microsoft.com/en-us/fabric/data-engineering/driver-mode-snapshot",
    "https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-table-maintenance",
    
    # Additional best practices series
    "https://learn.microsoft.com/en-us/fabric/data-engineering/spark-best-practices-capacity-planning",
    "https://learn.microsoft.com/en-us/fabric/data-engineering/spark-best-practices-security",
    "https://learn.microsoft.com/en-us/fabric/data-engineering/spark-best-practices-development-monitoring",
    "https://learn.microsoft.com/en-us/fabric/data-engineering/spark-best-practices-basics",
    "https://learn.microsoft.com/en-us/fabric/data-engineering/delta-optimization-and-v-order",
    "https://learn.microsoft.com/en-us/fabric/data-engineering/native-execution-engine-overview",
]


class SparkDocIndexer:
    def __init__(self):
        self.endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.key = os.getenv("AZURE_SEARCH_KEY")
        self.index_name = os.getenv("AZURE_SEARCH_INDEX")
        
        self.credential = AzureKeyCredential(self.key)
        self.index_client = SearchIndexClient(self.endpoint, self.credential)
        self.search_client = SearchClient(self.endpoint, self.index_name, self.credential)
    
    def load_metadata(self, docs_path: str) -> dict:
        """Load metadata.json and return as dict keyed by filename"""
        metadata_file = Path(docs_path) / "metadata.json"
        if not metadata_file.exists():
            return {}
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata_list = json.load(f)
        
        # Convert to dict keyed by filename for easy lookup
        return {item['filename']: item for item in metadata_list}
    
    def create_index(self):
        """Create search index for Spark documentation with category and source fields"""
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SearchableField(name="title", type=SearchFieldDataType.String),
            SimpleField(name="category", type=SearchFieldDataType.Collection(SearchFieldDataType.String), filterable=True, facetable=True),
            SimpleField(name="source_url", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="filename", type=SearchFieldDataType.String, filterable=True),
        ]
        
        index = SearchIndex(name=self.index_name, fields=fields)
        self.index_client.create_or_update_index(index)
        print(f"✅ Created/updated index: {self.index_name}")
    
    def index_documents(self, documents: list):
        """Index a batch of documents"""
        if not documents:
            return None
        result = self.search_client.upload_documents(documents=documents)
        return result
    
    def index_from_directory(self, docs_path: str):
        """Index all markdown documents from a directory with metadata"""
        import glob
        import hashlib
        
        # Load metadata
        metadata_map = self.load_metadata(docs_path)
        print(f"📋 Loaded metadata for {len(metadata_map)} documents")
        
        documents = []
        for filepath in glob.glob(f"{docs_path}/**/*.md", recursive=True):
            filename = os.path.basename(filepath)
            
            # Get metadata for this file
            file_metadata = metadata_map.get(filename, {})
            categories = file_metadata.get('category', ['uncategorized'])
            source_url = file_metadata.get('source_url', '')
            description = file_metadata.get('description', '')
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Create valid document key using filename without extension
                # Azure Search keys can only contain letters, digits, _, -, or =
                base_name = filename.replace('.md', '').replace(' ', '_').replace('-', '_')
                # Add short hash to ensure uniqueness
                path_hash = hashlib.md5(filepath.encode()).hexdigest()[:8]
                doc_id = f"{base_name}_{path_hash}"
                
                # Create document with metadata
                doc = {
                    "id": doc_id,
                    "content": content,
                    "title": filename.replace('.md', '').replace('_', ' ').title(),
                    "category": categories,  # List of categories for filtering
                    "source_url": source_url,
                    "filename": filename
                }
                documents.append(doc)
                print(f"  📄 Indexed: {filename} | Categories: {', '.join(categories)}")
        
        if documents:
            result = self.index_documents(documents)
            print(f"✅ Indexed {len(documents)} documents successfully")
            return result
        else:
            print("⚠️ No documents found to index")
            return None
