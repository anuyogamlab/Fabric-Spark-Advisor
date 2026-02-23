"""
Test script for RAG indexer and retriever with category filtering
"""
from rag.indexer import SparkDocIndexer
from rag.retriever import SparkDocRetriever
import os

def test_indexing():
    """Test indexing documents with metadata"""
    print("=" * 60)
    print("TESTING INDEXER")
    print("=" * 60)
    
    indexer = SparkDocIndexer()
    
    # Create index with category fields
    print("\n1. Creating/updating search index...")
    indexer.create_index()
    
    # Index documents from rag/docs with metadata
    print("\n2. Indexing documents with metadata...")
    docs_path = os.path.join(os.path.dirname(__file__), "rag", "docs")
    result = indexer.index_from_directory(docs_path)
    
    if result:
        print(f"\n✅ Indexing complete!")
    else:
        print(f"\n⚠️ No documents indexed")

def test_retrieval():
    """Test retrieving documents with category filtering"""
    print("\n" + "=" * 60)
    print("TESTING RETRIEVER")
    print("=" * 60)
    
    retriever = SparkDocRetriever()
    
    # Test 1: Search without category filter
    print("\n1. Search: 'resource profile configurations' (no filter)")
    print("-" * 60)
    results = retriever.search("resource profile configurations", top_k=3)
    for i, doc in enumerate(results, 1):
        print(f"\n  Result {i}: {doc['title']}")
        print(f"  Categories: {', '.join(doc['category'])}")
        print(f"  Source: {doc['source_url']}")
        print(f"  Score: {doc['score']:.2f}")
    
    # Test 2: Search with performance category filter
    print("\n2. Search: 'optimize Spark' (filter: performance)")
    print("-" * 60)
    results = retriever.search("optimize Spark", top_k=3, category="performance")
    for i, doc in enumerate(results, 1):
        print(f"\n  Result {i}: {doc['title']}")
        print(f"  Categories: {', '.join(doc['category'])}")
        print(f"  Source: {doc['source_url']}")
        print(f"  Score: {doc['score']:.2f}")
    
    # Test 3: Search with configuration category filter
    print("\n3. Search: 'driver mode snapshot' (filter: configuration)")
    print("-" * 60)
    results = retriever.search("driver mode snapshot", top_k=3, category="configuration")
    for i, doc in enumerate(results, 1):
        print(f"\n  Result {i}: {doc['title']}")
        print(f"  Categories: {', '.join(doc['category'])}")
        print(f"  Source: {doc['source_url']}")
        print(f"  Score: {doc['score']:.2f}")
    
    # Test 4: Get formatted context with category
    print("\n4. Get context: 'table maintenance' (filter: maintenance)")
    print("-" * 60)
    context = retriever.get_context("table maintenance", top_k=2, category="maintenance")
    print(context[:500] + "..." if len(context) > 500 else context)
    
    # Test 5: Search across multiple categories
    print("\n5. Search across multiple categories")
    print("-" * 60)
    results_by_cat = retriever.search_by_categories(
        "Spark optimization",
        categories=["performance", "configuration", "best-practices"],
        top_k=2
    )
    for category, docs in results_by_cat.items():
        print(f"\n  Category: {category}")
        for doc in docs:
            print(f"    - {doc['title']} (score: {doc['score']:.2f})")

if __name__ == "__main__":
    # Run tests
    test_indexing()
    test_retrieval()
    
    print("\n" + "=" * 60)
    print("✅ RAG TESTING COMPLETE")
    print("=" * 60)
