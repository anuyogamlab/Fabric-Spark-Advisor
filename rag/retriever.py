"""
RAG Retriever for Spark Documentation
Retrieves relevant documentation based on queries with category filtering
"""
import os
from typing import List, Optional
from azure.search.documents import SearchClient
from azure.search.documents.models import QueryType
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

load_dotenv()


class SparkDocRetriever:
    def __init__(self):
        self.endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.key = os.getenv("AZURE_SEARCH_KEY")
        self.index_name = os.getenv("AZURE_SEARCH_INDEX")
        
        self.credential = AzureKeyCredential(self.key)
        self.search_client = SearchClient(self.endpoint, self.index_name, self.credential)
    
    def search(self, query: str, top_k: int = 5, category: Optional[str] = None):
        """
        Search for relevant documents with optional category filtering.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            category: Optional category filter (e.g., "performance", "configuration")
        
        Returns:
            List of matching documents
        """
        # Build filter expression if category provided
        filter_expr = None
        if category:
            # Use OData filter syntax - check if category array contains the value
            filter_expr = f"category/any(c: c eq '{category}')"
        
        results = self.search_client.search(
            search_text=query,
            top=top_k,
            filter=filter_expr,
            select=["id", "content", "title", "category", "source_url", "filename"]
        )
        
        documents = []
        for result in results:
            documents.append({
                "id": result.get("id", ""),
                "content": result.get("content", ""),
                "title": result.get("title", ""),
                "category": result.get("category", []),
                "source_url": result.get("source_url", ""),
                "filename": result.get("filename", ""),
                "score": result.get("@search.score", 0.0)
            })
        
        return documents
    
    def get_context(self, query: str, top_k: int = 3, category: Optional[str] = None) -> str:
        """
        Get context string for RAG with optional category filtering.
        
        Args:
            query: Search query
            top_k: Number of documents to retrieve
            category: Optional category to filter by
        
        Returns:
            Formatted context string
        """
        docs = self.search(query, top_k, category=category)
        
        if not docs:
            return "No relevant documentation found."
        
        context_parts = []
        for doc in docs:
            source_info = f"Source: {doc['source_url']}" if doc.get('source_url') else ""
            categories = ", ".join(doc.get('category', [])) if doc.get('category') else "uncategorized"
            
            context_parts.append(
                f"Document: {doc['title']}\n"
                f"Categories: {categories}\n"
                f"{source_info}\n"
                f"{doc['content']}"
            )
        
        return "\n\n---\n\n".join(context_parts)
    
    def search_by_categories(self, query: str, categories: List[str], top_k: int = 5):
        """
        Search across multiple categories.
        
        Args:
            query: Search query
            categories: List of categories to search in
            top_k: Number of results per category
        
        Returns:
            Dict mapping category to results
        """
        results_by_category = {}
        
        for category in categories:
            results = self.search(query, top_k=top_k, category=category)
            if results:
                results_by_category[category] = results
        
        return results_by_category
