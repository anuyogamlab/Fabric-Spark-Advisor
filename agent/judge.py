"""
Judge Agent - LLM-based Recommendation Validator
Validates and prioritizes Spark recommendations from multiple sources (Kusto, RAG, LLM)
"""
import os
import json
from typing import List, Dict, Any, Optional
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()


class RecommendationJudge:
    """
    LLM Judge that validates and prioritizes Spark optimization recommendations
    from multiple sources (Kusto telemetry, RAG docs, LLM fallback).
    """
    
    def __init__(self):
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2024-08-01-preview",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    
    def validate_recommendations(
        self,
        application_id: str,
        recommendations: List[Dict[str, Any]],
        application_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate and prioritize recommendations from multiple sources.
        
        Args:
            application_id: Spark application ID
            recommendations: List of dicts with keys: {text, source, metadata}
                source: "kusto" | "rag" | "llm"
            application_context: Optional dict with app metrics (duration, executor_efficiency, etc.)
        
        Returns:
            Structured validation result with prioritized, validated recommendations
        """
        
        # Build the validation prompt
        prompt = self._build_validation_prompt(
            application_id=application_id,
            recommendations=recommendations,
            context=application_context
        )
        
        # Define the response schema for structured output
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
        
        try:
            # Call Azure OpenAI with structured output
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
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
            
            # Parse the JSON response
            result = json.loads(response.choices[0].message.content)
            
            # Add metadata
            result["application_id"] = application_id
            result["total_recommendations"] = len(result["validated_recommendations"])
            result["sources_used"] = list(set(r["source"] for r in result["validated_recommendations"]))
            
            return result
            
        except Exception as e:
            # Fallback response if LLM fails
            return self._create_fallback_response(application_id, recommendations, str(e))
    
    def _build_validation_prompt(
        self,
        application_id: str,
        recommendations: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build the validation prompt for the LLM judge."""
        
        prompt_parts = [
            f"# Spark Application Analysis: {application_id}\n",
            "## Task",
            "Validate and prioritize the following Spark optimization recommendations from multiple sources.",
            "Detect contradictions, assess confidence, and provide actionable guidance.\n",
        ]
        
        # Add application context if available
        if context:
            prompt_parts.append("## Application Metrics")
            for key, value in context.items():
                prompt_parts.append(f"- {key}: {value}")
            prompt_parts.append("")
        
        # Add recommendations grouped by source
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
            for i, rec in enumerate(rag_recs, 1):
                prompt_parts.append(f"{i}. {rec.get('text', rec.get('recommendation', 'No text'))}")
                if rec.get('source_url'):
                    prompt_parts.append(f"   Source: {rec['source_url']}")
            prompt_parts.append("")
        
        if llm_recs:
            prompt_parts.append("### LLM Generated (Lower Priority - General Guidance)")
            for i, rec in enumerate(llm_recs, 1):
                prompt_parts.append(f"{i}. {rec.get('text', rec.get('recommendation', 'No text'))}")
            prompt_parts.append("")
        
        prompt_parts.extend([
            "## Validation Criteria",
            "",
            "1. **CRITICAL: Kusto Recommendation Handling:**",
            "   - Kusto recommendations are ALREADY formatted and scored by the analyzer",
            "   - DO NOT split them into multiple items",
            "   - DO NOT change severity (⚫ LOW, 🟡 MEDIUM, 🔴 HIGH, 🔴 CRITICAL)",
            "   - Extract severity from the text (look for ⚫ LOW, 🟡 MEDIUM, etc.)",
            "   - Map severity to priority:",
            "     * ⚫ LOW → priority 30-39",
            "     * 🟡 MEDIUM → priority 20-29",
            "     * 🔴 HIGH → priority 10-19",
            "     * 🔴 CRITICAL → priority 1-9",
            "   - Keep the full text including all sections (ROOT CAUSE, IMPACT, FIXES, PERFORMANCE SUMMARY)",
            "",
            "2. **Prioritization Rules:**",
            "   - Kusto telemetry > RAG documentation > LLM generated",
            "   - Within Kusto: use the severity marker to determine priority",
            "   - Application-specific > Generic recommendations",
            "   - Actionable > Observational",
            "",
            "3. **Confidence Scoring:**",
            "   - HIGH: Backed by telemetry data or official docs, no contradictions",
            "   - MEDIUM: Based on best practices, minor uncertainties",
            "   - LOW: Generic advice, potential conflicts, or speculative",
            "",
            "4. **Contradiction Detection:**",
            "   - Flag recommendations that conflict (e.g., 'add executors' vs 'reduce executors')",
            "   - Explain why they conflict and which to prioritize",
            "",
            "5. **Generic vs Specific:**",
            "   - Mark recommendations that apply to any Spark job as generic",
            "   - Kusto recommendations are usually specific (based on actual metrics)",
            "",
            "6. **Actionability:**",
            "   - Each recommendation must have a clear, concrete action",
            "   - Keep existing actions from Kusto (e.g., 'No action required' is valid)",
            "   - Include configuration keys, commands, or steps where applicable"
        ])
        
        return "\n".join(prompt_parts)
    
    def _get_system_prompt(self) -> str:
        """System prompt defining the judge's role and expertise."""
        return """You are an expert Spark performance consultant and recommendation validator.

CRITICAL RULES FOR KUSTO RECOMMENDATIONS:

1. **sparklens_recommedations and fabric_recommedations are GROUND TRUTH**
   - These come from the analyzer pipeline and are already scored/formatted
   - DO NOT rephrase, re-interpret, or re-score them
   - DO NOT change severity labels (LOW/MEDIUM/HIGH/CRITICAL)
   - DO NOT break them into multiple recommendations
   - Show them EXACTLY as provided - preserve all formatting, emojis, scores

2. **Severity Mapping (DO NOT OVERRIDE):**
   - ⚫ LOW → priority 30-39 (Info)
   - 🟡 MEDIUM → priority 20-29 (Warning)
   - 🔴 HIGH → priority 10-19 (Warning)
   - 🔴 CRITICAL → priority 1-9 (Critical)
   
3. **If Kusto says "No critical issues" with LOW severity:**
   - DO NOT escalate it to Critical or High priority
   - Assign priority 30+ (Info level)
   - Keep the exact text including "No action required"

4. **Your Job:**
   - Pass through Kusto/Fabric recommendations verbatim (assign correct priority based on severity)
   - Add RAG documentation that supports the Kusto findings
   - Add LLM observations ONLY if physical plan data is available
   - Write a brief summary that agrees with Kusto scores

5. **Do NOT:**
   - Invent recommendations not backed by data
   - Change "No action required" to something else
   - Split one Kusto recommendation into multiple items
   - Override the analyzer's performance scores

Guidelines:
- Kusto telemetry data is the most reliable (actual performance metrics)
- RAG documentation represents best practices (official Microsoft Fabric docs)
- LLM-generated recommendations should be validated against the other sources
- Always prefer specific, measurable actions over vague advice
- Flag contradictions clearly and explain resolution
- Consider the application context when assessing relevance

Output format: Structured JSON with validated, prioritized recommendations."""
    
    def _create_fallback_response(
        self,
        application_id: str,
        recommendations: List[Dict[str, Any]],
        error: str
    ) -> Dict[str, Any]:
        """Create a fallback response if LLM validation fails."""
        
        # Simple prioritization: kusto > rag > llm
        priority_map = {"kusto": 1, "rag": 2, "llm": 3}
        
        validated_recs = []
        for i, rec in enumerate(recommendations):
            source = rec.get("source", "llm")
            validated_recs.append({
                "recommendation": rec.get("text", rec.get("recommendation", "No recommendation text")),
                "source": source,
                "confidence": "medium" if source == "kusto" else "low",
                "priority": priority_map.get(source, 3) * 10 + i,
                "reasoning": f"Fallback validation - LLM judge unavailable",
                "action": "Review recommendation manually",
                "is_generic": False,
                "contradicts": []
            })
        
        # Sort by priority
        validated_recs.sort(key=lambda x: x["priority"])
        
        return {
            "application_id": application_id,
            "validated_recommendations": validated_recs,
            "summary": f"Fallback validation completed. LLM judge error: {error}",
            "critical_count": 0,
            "warning_count": len(recommendations),
            "info_count": 0,
            "overall_health": "warning",
            "detected_contradictions": [],
            "total_recommendations": len(validated_recs),
            "sources_used": list(set(r["source"] for r in validated_recs)),
            "error": error
        }


# Convenience function for quick validation
def validate_recommendations(
    application_id: str,
    recommendations: List[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Validate recommendations using the LLM judge.
    
    Args:
        application_id: Spark application ID
        recommendations: List of {text/recommendation, source, metadata}
        context: Optional application metrics
    
    Returns:
        Validated recommendations with confidence scores and priorities
    """
    judge = RecommendationJudge()
    return judge.validate_recommendations(application_id, recommendations, context)

