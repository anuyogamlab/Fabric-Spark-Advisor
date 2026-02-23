"""MCP server exposing Kusto-backed Spark advisory tools + RAG + LLM Judge.

Auth: Multi-method fallback (Service Principal → Azure CLI → Default Credential)

Config:
    - KUSTO_CLUSTER_URI (optional; defaults to the Fabric endpoint below)
    - KUSTO_DATABASE (optional; defaults to "Spark Monitoring")
    - AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET (for Service Principal auth)
    - AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY, AZURE_SEARCH_INDEX (for RAG)
    - AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT (for Judge)

Run:
    python spark_mcp_server.py
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from azure.kusto.data import KustoClient, KustoConnectionStringBuilder, ClientRequestProperties
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, ClientSecretCredential, AzureCliCredential
from openai import AzureOpenAI
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

mcp_server = FastMCP("SparkAdvisor")


# Defaults can be overridden via env vars KUSTO_URI / KUSTO_DATABASE.
DEFAULT_KUSTO_URI = "https://trd-kx2zn2dzkdksr5r4dj.z0.kusto.fabric.microsoft.com"
DEFAULT_KUSTO_DATABASE = "Spark Monitoring"


def _env_or_default(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value and value.strip() else default


_client: Optional[KustoClient] = None
_database: Optional[str] = None
_search_client: Optional[SearchClient] = None
_openai_client: Optional[AzureOpenAI] = None


def _get_client() -> tuple[KustoClient, str]:
    global _client, _database
    if _client is not None and _database is not None:
        return _client, _database

    kusto_uri = _env_or_default("KUSTO_CLUSTER_URI", DEFAULT_KUSTO_URI)
    database = _env_or_default("KUSTO_DATABASE", DEFAULT_KUSTO_DATABASE)

    # Try multiple authentication methods in order of preference
    
    # Method 1: Client Secret (Service Principal) - Best for production
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    
    if all([tenant_id, client_id, client_secret]):
        try:
            credential = ClientSecretCredential(tenant_id, client_id, client_secret)
            kcsb = KustoConnectionStringBuilder.with_azure_token_credential(kusto_uri, credential)
            _client = KustoClient(kcsb)
            _database = database
            # Test connection
            _client.execute(database, ".show databases | limit 1")
            print(f"✅ Connected to Kusto using Service Principal")
            return _client, _database
        except Exception as e:
            print(f"⚠️ Service Principal auth failed: {e}")
    
    # Method 2: Azure CLI - Good for local development
    try:
        credential = AzureCliCredential()
        kcsb = KustoConnectionStringBuilder.with_azure_token_credential(kusto_uri, credential)
        _client = KustoClient(kcsb)
        _database = database
        # Test connection
        _client.execute(database, ".show databases | limit 1")
        print(f"✅ Connected to Kusto using Azure CLI")
        return _client, _database
    except Exception as cli_error:
        print(f"⚠️ Azure CLI auth failed: {cli_error}")
    
    # Method 3: Default Azure Credential - Last resort (managed identity, etc.)
    try:
        credential = DefaultAzureCredential()
        kcsb = KustoConnectionStringBuilder.with_azure_token_credential(kusto_uri, credential)
        _client = KustoClient(kcsb)
        _database = database
        # Test connection
        _client.execute(database, ".show databases | limit 1")
        print(f"✅ Connected to Kusto using Default Azure Credential")
        return _client, _database
    except Exception as default_error:
        raise ValueError(
            f"All Kusto authentication methods failed.\n\n"
            f"Troubleshooting:\n"
            f"1. Set service principal credentials in .env:\n"
            f"   AZURE_TENANT_ID=your-tenant-id\n"
            f"   AZURE_CLIENT_ID=your-client-id\n"
            f"   AZURE_CLIENT_SECRET=your-client-secret\n\n"
            f"2. Or run 'az login' (if not blocked by admin)\n\n"
            f"Errors:\n"
            f"  - Azure CLI: {str(cli_error)[:100]}\n"
            f"  - Default Credential: {str(default_error)[:100]}"
        )


def _get_search_client() -> SearchClient:
    global _search_client
    if _search_client is not None:
        return _search_client
    
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    key = os.getenv("AZURE_SEARCH_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX")
    
    if not endpoint or not key or not index_name:
        raise ValueError("AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY, and AZURE_SEARCH_INDEX must be set")
    
    credential = AzureKeyCredential(key)
    _search_client = SearchClient(endpoint, index_name, credential)
    return _search_client


def _get_openai_client() -> tuple[AzureOpenAI, str]:
    global _openai_client
    if _openai_client is not None:
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        return _openai_client, deployment
    
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    
    if not api_key or not endpoint:
        raise ValueError("AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT must be set")
    
    _openai_client = AzureOpenAI(
        api_key=api_key,
        api_version="2024-08-01-preview",
        azure_endpoint=endpoint
    )
    return _openai_client, deployment


def read_kusto(query: str, properties: Optional[ClientRequestProperties] = None) -> List[Dict[str, Any]]:
    client, database = _get_client()
    result = client.execute(database, query, properties=properties)
    table = result.primary_results[0]
    columns = [col.column_name for col in table.columns]

    # Each row supports iteration / indexing.
    return [dict(zip(columns, row)) for row in table]


def _props(**params: Any) -> ClientRequestProperties:
    p = ClientRequestProperties()
    for k, v in params.items():
        p.set_parameter(k, v)
    return p


@mcp_server.tool()
def get_spark_recommendations(application_id: str) -> str:
    """Get best practice recommendations for a Spark application ID."""
    if not application_id or not application_id.strip():
        raise ValueError("application_id must be a non-empty string")

    query = """
declare query_parameters (application_id:string);

sparklens_recommedations
| where app_id == application_id
| project app_id, recommendation, ingestion_time()
""".strip()

    rows = read_kusto(query, _props(application_id=application_id))
    return json.dumps(rows, default=str)


@mcp_server.tool()
def get_worst_applications(top_n: int = 10) -> str:
    """Get worst performing Spark applications by violation count."""
    if top_n < 1:
        raise ValueError("top_n must be >= 1")
    if top_n > 1000:
        top_n = 1000

    query = """
declare query_parameters (top_n:int);

sparklens_recommedations
| summarize RecommendationCount=count() by app_id
| order by RecommendationCount desc
| take top_n
""".strip()

    rows = read_kusto(query, _props(top_n=int(top_n)))
    return json.dumps(rows, default=str)


@mcp_server.tool()
def get_full_application_report(application_id: str) -> str:
    """Get full health report for a Spark application."""
    if not application_id or not application_id.strip():
        raise ValueError("application_id must be a non-empty string")

    app_props = _props(application_id=application_id)

    def q(table: str) -> str:
        return f"""
declare query_parameters (application_id:string);

{table}
| where app_id == application_id
""".strip()

    recs = read_kusto(q("sparklens_recommedations"), app_props)
    fabric = read_kusto(q("fabric_recommedations"), app_props)
    summary = read_kusto(q("sparklens_summary"), app_props)
    preds = read_kusto(q("sparklens_predictions"), app_props)

    return json.dumps(
        {
            "recommendations": recs,
            "fabric_recommendations": fabric,
            "summary": summary,
            "predictions": preds,
        },
        default=str,
    )


@mcp_server.tool()
def get_common_bad_patterns() -> str:
    """Get most common bad patterns across all Spark applications."""
    query = """
sparklens_recommedations
| summarize AffectedApps=dcount(app_id), SampleRec=any(recommendation) by recommendation
| order by AffectedApps desc
| take 20
""".strip()

    rows = read_kusto(query)
    return json.dumps(rows, default=str)


@mcp_server.tool()
def search_spark_docs(query: str, top_k: int = 5, category: Optional[str] = None) -> str:
    """
    Search Spark documentation using RAG.
    
    Args:
        query: Search query text
        top_k: Number of results to return (default: 5, max: 20)
        category: Optional category filter (e.g., "performance", "configuration")
    
    Returns:
        JSON array of matching documents with content, title, category, source_url, and score
    """
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")
    
    if top_k < 1:
        top_k = 1
    if top_k > 20:
        top_k = 20
    
    try:
        search_client = _get_search_client()
        
        # Build filter expression if category provided
        filter_expr = None
        if category:
            filter_expr = f"category/any(c: c eq '{category}')"
        
        results = search_client.search(
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
        
        return json.dumps(documents, default=str)
    
    except Exception as e:
        return json.dumps({"error": str(e)}, default=str)


@mcp_server.tool()
def execute_kql_query(query: str) -> str:
    """
    Execute a generic KQL (Kusto Query Language) query.
    
    Args:
        query: KQL query string to execute
    
    Returns:
        JSON array of query results as list of dictionaries
    """
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")
    
    try:
        rows = read_kusto(query)
        return json.dumps(rows, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, default=str)


@mcp_server.tool()
def validate_recommendations(
    application_id: str,
    recommendations: str,
    application_context: Optional[str] = None
) -> str:
    """
    Validate and prioritize Spark recommendations using LLM judge.
    
    Args:
        application_id: Spark application ID
        recommendations: JSON string of list of dicts with keys: {text, source, metadata}
                        where source is "kusto" | "rag" | "llm"
        application_context: Optional JSON string of dict with app metrics
    
    Returns:
        JSON object with validated_recommendations, summary, health scores, contradictions
    """
    if not application_id or not application_id.strip():
        raise ValueError("application_id must be a non-empty string")
    
    if not recommendations or not recommendations.strip():
        raise ValueError("recommendations must be a non-empty JSON string")
    
    try:
        # Parse inputs
        recs_list = json.loads(recommendations)
        context_dict = json.loads(application_context) if application_context else None
        
        # Get OpenAI client
        client, deployment = _get_openai_client()
        
        # Build validation prompt
        prompt = _build_judge_prompt(application_id, recs_list, context_dict)
        
        # Define response schema
        response_schema = {
            "type": "object",
            "properties": {
                "validated_recommendations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "recommendation": {"type": "string"},
                            "source": {"type": "string", "enum": ["kusto", "rag", "llm", "combined"]},
                            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                            "priority": {"type": "integer"},
                            "reasoning": {"type": "string"},
                            "action": {"type": "string"},
                            "is_generic": {"type": "boolean"},
                            "contradicts": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["recommendation", "source", "confidence", "priority", "reasoning", "action", "is_generic", "contradicts"],
                        "additionalProperties": False
                    }
                },
                "summary": {"type": "string"},
                "critical_count": {"type": "integer"},
                "warning_count": {"type": "integer"},
                "info_count": {"type": "integer"},
                "overall_health": {"type": "string", "enum": ["critical", "warning", "healthy", "excellent"]},
                "detected_contradictions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "recommendation_1": {"type": "string"},
                            "recommendation_2": {"type": "string"},
                            "explanation": {"type": "string"}
                        },
                        "required": ["recommendation_1", "recommendation_2", "explanation"],
                        "additionalProperties": False
                    }
                }
            },
            "required": [
                "validated_recommendations",
                "summary",
                "critical_count",
                "warning_count",
                "info_count",
                "overall_health",
                "detected_contradictions"
            ],
            "additionalProperties": False
        }
        
        # Call Azure OpenAI
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": _get_judge_system_prompt()},
                {"role": "user", "content": prompt}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "recommendation_validation",
                    "strict": True,
                    "schema": response_schema
                }
            },
            temperature=0.3,
            max_tokens=4000
        )
        
        # Parse and enhance result
        result = json.loads(response.choices[0].message.content)
        
        # CRITICAL: Restore metadata for all recommendations (Judge doesn't include it in schema)
        # Build mapping from source+index to metadata (since Judge preserves source and order)
        kusto_inputs = [r for r in recs_list if r.get("source") == "kusto"]
        rag_inputs = [r for r in recs_list if r.get("source") == "rag"]
        llm_inputs = [r for r in recs_list if r.get("source") == "llm"]
        
        kusto_outputs = [r for r in result["validated_recommendations"] if r.get("source") == "kusto"]
        rag_outputs = [r for r in result["validated_recommendations"] if r.get("source") == "rag"]
        llm_outputs = [r for r in result["validated_recommendations"] if r.get("source") == "llm"]
        
        # Restore metadata by matching index within each source group
        for i, validated_rec in enumerate(kusto_outputs):
            if i < len(kusto_inputs):
                validated_rec["metadata"] = kusto_inputs[i].get("metadata", {})
        
        for i, validated_rec in enumerate(rag_outputs):
            if i < len(rag_inputs):
                validated_rec["metadata"] = rag_inputs[i].get("metadata", {})
        
        for i, validated_rec in enumerate(llm_outputs):
            if i < len(llm_inputs):
                validated_rec["metadata"] = llm_inputs[i].get("metadata", {})
        
        # CRITICAL VALIDATION: Ensure ALL Kusto recommendations are preserved
        input_kusto_count = len(kusto_inputs)
        output_kusto_count = len(kusto_outputs)
        
        if output_kusto_count < input_kusto_count:
            # Judge dropped some Kusto recs - add them back
            for i in range(output_kusto_count, input_kusto_count):
                input_rec = kusto_inputs[i]
                result["validated_recommendations"].append({
                    "recommendation": input_rec.get("text", ""),
                    "source": "kusto",
                    "confidence": "high",
                    "priority": 15,  # Default to MEDIUM
                    "reasoning": "Auto-restored - Judge incorrectly filtered this Kusto recommendation",
                    "action": "Review this recommendation from Kusto telemetry",
                    "is_generic": False,
                    "contradicts": [],
                    "metadata": input_rec.get("metadata", {})
                })
        
        result["application_id"] = application_id
        result["total_recommendations"] = len(result["validated_recommendations"])
        result["sources_used"] = list(set(r["source"] for r in result["validated_recommendations"]))
        
        return json.dumps(result, default=str)
    
    except Exception as e:
        # Fallback response
        error_result = {
            "application_id": application_id,
            "validated_recommendations": [],
            "summary": f"Judge validation failed: {str(e)}",
            "critical_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "overall_health": "healthy",
            "detected_contradictions": [],
            "error": str(e)
        }
        return json.dumps(error_result, default=str)


def _build_judge_prompt(
    application_id: str,
    recommendations: List[Dict[str, Any]],
    context: Optional[Dict[str, Any]]
) -> str:
    """Build validation prompt for the LLM judge."""
    prompt_parts = [
        f"# Spark Application Analysis: {application_id}\n",
        "## Task",
        "Validate and prioritize the following Spark optimization recommendations from multiple sources.",
        "Detect contradictions, assess confidence, and provide actionable guidance.\n",
    ]
    
    if context:
        prompt_parts.append("## Application Metrics")
        for key, value in context.items():
            prompt_parts.append(f"- {key}: {value}")
        prompt_parts.append("")
    
    # Group by source
    kusto_recs = [r for r in recommendations if r.get("source") == "kusto"]
    rag_recs = [r for r in recommendations if r.get("source") == "rag"]
    llm_recs = [r for r in recommendations if r.get("source") == "llm"]
    
    prompt_parts.append("## Recommendations by Source\n")
    
    if kusto_recs:
        prompt_parts.append("### Kusto Telemetry (High Priority - Data-Driven)")
        for i, rec in enumerate(kusto_recs, 1):
            prompt_parts.append(f"{i}. {rec.get('text', rec.get('recommendation', 'No text'))}")
            if rec.get('metadata'):
                prompt_parts.append(f"   Metadata: {json.dumps(rec['metadata'])}")
        prompt_parts.append("")
    
    if rag_recs:
        prompt_parts.append("### RAG Documentation (Medium Priority - Best Practices)")
        prompt_parts.append("IMPORTANT: Preserve the full content from RAG docs, do NOT summarize into titles only")
        for i, rec in enumerate(rag_recs, 1):
            text = rec.get('text', rec.get('recommendation', 'No text'))
            metadata = rec.get('metadata', {})
            title = metadata.get('title', f'Doc {i}')
            prompt_parts.append(f"{i}. Title: {title}")
            prompt_parts.append(f"   Content: {text}")
            if metadata.get('source_url'):
                prompt_parts.append(f"   Source: {metadata['source_url']}")
        prompt_parts.append("")
    
    if llm_recs:
        prompt_parts.append("### LLM Generated (Lower Priority - General Guidance)")
        for i, rec in enumerate(llm_recs, 1):
            prompt_parts.append(f"{i}. {rec.get('text', rec.get('recommendation', 'No text'))}")
        prompt_parts.append("")
    
    kusto_count = len(kusto_recs)
    
    prompt_parts.extend([
        "## Validation Criteria",
        "",
        f"1. **MANDATORY: Output ALL {kusto_count} Kusto Recommendations:**",
        "   - NEVER skip, filter, combine, or reduce Kusto recommendations",
        f"   - Your output MUST contain exactly {kusto_count} items with source='kusto'",
        "   - DO NOT split, rephrase, or re-score",
        "   - PRESERVE the metadata field exactly as provided",
        "   - Extract severity from text (⚫ LOW, 🟡 MEDIUM, 🔴 HIGH, 🔴 CRITICAL)",
        "   - Map to priority: CRITICAL→1-9, HIGH→10-19, MEDIUM→20-29, LOW→30-39",
        "",
        "2. **CRITICAL: RAG Documentation Handling:**",
        "   - Include FULL content from RAG docs, not just titles",
        "   - The 'recommendation' field must contain the complete guidance text",
        "   - Format as: '[Title] - [Full Content]'",
        "",
        "3. **LLM Recommendations:**",
        "   - Only include if they provide SPECIFIC, ACTIONABLE guidance",
        "   - Mark as 'is_generic: true' and low priority if too vague",
        "   - Generic advice like 'optimize performance' should be filtered out",
        "",
        "4. **Prioritization:** Kusto > RAG > LLM, Specific > Generic",
        "5. **Confidence:** HIGH (data/docs), MEDIUM (best practice), LOW (generic)",
        "6. **Detect contradictions and explain resolution**",
    ])
    
    return "\n".join(prompt_parts)


def _get_judge_system_prompt() -> str:
    """System prompt for the LLM judge."""
    return """You are an expert Spark performance consultant and recommendation validator.

CRITICAL RULES:
1. MANDATORY: Include EVERY SINGLE Kusto recommendation in your output - NO EXCEPTIONS
   - If you receive N Kusto recs, you MUST output exactly N items with source='kusto'
   - NEVER skip, filter, combine, or reduce Kusto recommendations
   - PRESERVE the metadata field exactly as provided for each Kusto rec
2. ONLY validate and format the provided recommendations - DO NOT generate new ones
3. Kusto recommendations are GROUND TRUTH - never modify severity or split them
4. RAG recommendations must preserve FULL CONTENT - never summarize into titles only
5. Prioritize: Kusto telemetry > RAG docs > LLM generic advice
6. Detect contradictions and explain which recommendation to follow
7. Filter out generic LLM advice that lacks specific, actionable guidance
8. Mark generic advice vs. application-specific recommendations

Extract severity markers from Kusto text and preserve them exactly.
For RAG docs, include the complete content in the 'recommendation' field, not just titles.

⚠️ CRITICAL: Count the Kusto recommendations in the input and ensure your output has the SAME count."""


if __name__ == "__main__":
    # stdio transport: no port, no web server
    mcp_server.run(transport="stdio")
