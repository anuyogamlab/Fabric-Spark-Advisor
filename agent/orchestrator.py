"""
Agent Orchestrator
Coordinates the AI agent workflow for Spark recommendations using Semantic Kernel
ALL data access goes through MCP server to avoid m×n integration problem
"""
import os
import json
from typing import List, Dict, Any, Optional
from collections import defaultdict
from datetime import datetime, timedelta
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion, AzureChatPromptExecutionSettings
from semantic_kernel.connectors.ai.prompt_execution_settings import PromptExecutionSettings
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.contents import ChatHistory
from semantic_kernel.functions import kernel_function
from dotenv import load_dotenv

from agent.mcp_client_wrapper import get_mcp_client
from agent.plugin import SparkAdvisorPlugin
from agent.prompts import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    CHAT_SYSTEM_PROMPT,
    SKILL_LAYER_SYSTEM_PROMPT,
    LLM_RECOMMENDATION_PROMPT,
    ANALYSIS_SUMMARY_PROMPT,
    BAD_PRACTICES_PROMPT,
    BROAD_QUESTION_PROMPT,
    SKEW_ANALYSIS_PROMPT,
    SCALING_ANALYSIS_PROMPT,
    AI_WARNING_BLOCK,
    AI_WARNING_BLOCK_CLOSE,
    FEEDBACK_REQUEST_BLOCK
)

load_dotenv()


class SparkAdvisorOrchestrator:
    """
    Main orchestration agent for Spark optimization recommendations.
    Uses MCP server for ALL data access (Kusto, RAG, Judge) to avoid m×n problem.
    """
    
    def __init__(self):
        # Initialize Semantic Kernel
        self.kernel = Kernel()
        
        # Add Azure OpenAI service
        self.chat_service = AzureChatCompletion(
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY")
        )
        self.kernel.add_service(self.chat_service)
        
        # Initialize MCP client for ALL data access (Kusto, RAG, Judge)
        # This solves the m×n problem: one client → one MCP server → multiple backends
        self.mcp_client = get_mcp_client()

        # Register the SparkAdvisor plugin so FunctionChoiceBehavior.Auto() can route
        # user queries to the correct skill without any if/elif routing logic.
        self.kernel.add_plugin(
            SparkAdvisorPlugin(self.mcp_client),
            plugin_name="SparkAdvisor"
        )

        # Chat history for conversational interactions
        # Uses the skill-layer system prompt so the LLM knows how to interpret
        # the JSON data returned by each @kernel_function.
        self.chat_history = ChatHistory()
        self.chat_history.add_system_message(SKILL_LAYER_SYSTEM_PROMPT)
        
        # Session management for conversational context
        self.sessions = defaultdict(lambda: {
            "messages": [],
            "current_app_id": None,
            "last_recommendations": [],
            "analyzed_apps": {},
            "last_updated": None
        })
        
        # Ambiguous reference triggers
        self._ref_triggers = [
            "it", "that", "this", "those", "same",
            "the app", "above", "previous", "the issue",
            "the problem", "the recommendation"
        ]
        
        # Database schema cache for LLM-powered queries
        self._schema_cache = None
        self._schema_cache_time = None
        self._schema_cache_ttl = timedelta(hours=1)  # Refresh every hour
    
    def _split_recommendations(self, text: str) -> List[str]:
        """
        Split concatenated recommendations into individual items.
        
        Recommendations are separated by:
        - Numbered markers: (1), (2), (3), etc.
        - Category prefixes: 'Best Practice:', 'Performance Optimization:', etc.
        
        Args:
            text: Concatenated recommendation text
            
        Returns:
            List of individual recommendation strings
        """
        import re
        
        if not text or not text.strip():
            return []
        
        # First try splitting by numbered markers: (1), (2), (3)
        parts = re.split(r'\s*\(\d+\)\s*', text)
        # Remove empty strings and strip whitespace
        parts = [p.strip() for p in parts if p.strip()]
        
        # If we got multiple parts, return them
        if len(parts) > 1:
            return parts
        
        # Otherwise, try splitting by category prefixes
        # Common patterns in Spark recommendations
        category_pattern = r'(?=(?:Performance Optimization|Best Practice|Validated|Resource Profile|Metrics|Warning|Error|Info):)'
        parts = re.split(category_pattern, text)
        parts = [p.strip() for p in parts if p.strip()]
        
        # If still only one part, return it as-is
        if len(parts) <= 1:
            return [text.strip()]
        
        return parts
        
    async def analyze_application(self, application_id: str, session_id: str = "default") -> Dict[str, Any]:
        """
        Full 7-step pipeline analysis for direct/API callers.

        NOTE: This is NOT the same as the plugin's analyze_app() skill.

        - This method: fetches → RAG-augments → LLM-judges → returns a validated Dict
          with structured recommendations, source tags, and confidence scores.
        - Plugin skill (analyze_app): fetches raw Kusto data → returns a flat JSON
          blob for the LLM to format inside the chat turn.

        Use THIS method when calling from outside the chat loop, e.g.:
          - Batch processing pipelines
          - Chainlit on_message handler for /analyze slash-commands
          - External API endpoints that need the fully-validated recommendation Dict

        Use the plugin skill for all conversational chat() interactions.

        Steps:
        1. Get Sparklens recommendations from Kusto
        2. Get application summary from Kusto
        3. Query RAG for relevant documentation based on issues
        4. If RAG returns < 3 results, ask LLM for recommendations
        5. Combine all results with source tags
        6. Pass to LLM judge for validation
        7. Return final validated recommendations

        Args:
            application_id: Spark application ID to analyze

        Returns:
            Dict with validated recommendations, summary, and metadata
        """
        print(f"\n🔍 Analyzing application: {application_id}")
        
        # Step 1: Get Sparklens recommendations from Kusto
        print("  ├─ Fetching Sparklens recommendations...")
        sparklens_recs = []
        try:
            sparklens_data = self.mcp_client.get_sparklens_recommendations(application_id)
            if sparklens_data and len(sparklens_data) > 0:
                for row in sparklens_data:
                    # Split concatenated recommendations into individual items
                    recommendation_text = row.get("recommendation", "")
                    individual_recs = self._split_recommendations(recommendation_text)
                    
                    for rec_text in individual_recs:
                        sparklens_recs.append({
                            "text": rec_text,
                            "source": "kusto",
                            "metadata": {
                                "from_kusto": True,
                                "table": "sparklens_recommedations",
                            }
                        })
                print(f"    ✓ Found {len(sparklens_recs)} Sparklens recommendations")
        except Exception as e:
            print(f"    ⚠️  Sparklens fetch failed: {e}")
        
        # Also get Fabric recommendations
        print("  ├─ Fetching Fabric recommendations...")
        fabric_recs = []
        try:
            fabric_data = self.mcp_client.get_fabric_recommendations(application_id)
            if fabric_data and len(fabric_data) > 0:
                for row in fabric_data:
                    # Split concatenated recommendations into individual items
                    recommendation_text = row.get("recommendation", "")
                    individual_recs = self._split_recommendations(recommendation_text)
                    
                    for rec_text in individual_recs:
                        fabric_recs.append({
                            "text": rec_text,
                            "source": "kusto",
                            "metadata": {
                                "from_kusto": True,
                                "table": "fabric_recommedations",
                                "category": "fabric"
                            }
                        })
                print(f"    ✓ Found {len(fabric_recs)} Fabric recommendations")
        except Exception as e:
            print(f"    ⚠️  Fabric fetch failed: {e}")
        
        # Step 2: Get application summary
        print("  ├─ Fetching application summary...")
        app_summary = {}
        try:
            summary_data = self.mcp_client.get_application_summary(application_id)
            # get_application_summary returns a single dict, not a list
            if summary_data and "error" not in summary_data:
                app_summary = summary_data
                duration_min = app_summary.get('duration_sec', 0) / 60.0
                print(f"    ✓ Got summary (duration: {duration_min:.1f} min, health: {app_summary.get('health_status', 'unknown')})") 
        except Exception as e:
            print(f"    ⚠️  Summary fetch failed: {e}")
        
        # Step 3: Query RAG for relevant documentation
        print("  ├─ Querying RAG for relevant documentation...")
        rag_recs = []
        
        # Build RAG query from identified issues
        issues = []
        for rec in sparklens_recs + fabric_recs:
            category = rec.get("metadata", {}).get("category", "")
            if category:
                issues.append(category)
        
        if issues:
            # Search for each unique issue category
            unique_issues = list(set(issues))
            for issue in unique_issues[:3]:  # Limit to top 3 categories
                try:
                    rag_results = self.mcp_client.search(issue, top_k=2, category=None)
                    for result in rag_results:
                        rag_recs.append({
                            "text": result.get("content", ""),
                            "source": "rag",
                            "metadata": {
                                "title": result.get("title", ""),
                                "source_url": result.get("source_url", ""),
                                "score": result.get("@search.score", 0)
                            }
                        })
                except Exception as e:
                    print(f"    ⚠️  RAG search for '{issue}' failed: {e}")
        
        print(f"    ✓ Retrieved {len(rag_recs)} documentation snippets")
        
        # Step 4: Only call LLM if NO Kusto recommendations exist
        llm_recs = []
        kusto_rec_count = len(sparklens_recs) + len(fabric_recs)
        if kusto_rec_count == 0 and len(rag_recs) < 3:
            print("  ├─ No Kusto data and RAG < 3, querying LLM as fallback...")
            try:
                llm_response = await self._generate_llm_recommendations(
                    application_id=application_id,
                    app_summary=app_summary,
                    issues=[r["text"] for r in sparklens_recs + fabric_recs]
                )
                
                # Parse LLM response into recommendations
                if llm_response:
                    # Post-process to ensure proper formatting
                    formatted_response = self._format_llm_response(llm_response)
                    
                    llm_recs.append({
                        "text": formatted_response,
                        "source": "llm",
                        "metadata": {"generated": True}
                    })
                    print(f"    ✓ Generated LLM recommendations")
            except Exception as e:
                print(f"    ⚠️  LLM generation failed: {e}")
        
        # Step 5: Separate Kusto (ground truth) from supplemental (RAG/LLM)
        non_kusto_recs = rag_recs + llm_recs
        print(f"  ├─ Kusto recs (ground truth): {len(sparklens_recs + fabric_recs)}, "
              f"non-Kusto (Judge input): {len(non_kusto_recs)}")

        # Step 6: Judge validates ONLY RAG/LLM recs; Kusto is passed as read-only reference
        print("  ├─ Validating with LLM judge (RAG/LLM only — Kusto is source of truth)...")
        validated_result = {}
        non_kusto_validated = []
        try:
            # Build judge context: app metrics + Kusto texts as reference (not to validate)
            judge_context = dict(app_summary)
            kusto_texts = [r["text"] for r in sparklens_recs + fabric_recs if r.get("text")]
            if kusto_texts:
                judge_context["kusto_recs_for_reference"] = kusto_texts

            if non_kusto_recs:
                validated_result = self.mcp_client.validate_recommendations(
                    application_id=application_id,
                    recommendations=non_kusto_recs,
                    application_context=judge_context if judge_context else None
                )
                non_kusto_validated = validated_result.get("validated_recommendations", non_kusto_recs)
                print(f"    ✓ Validation complete ({validated_result.get('overall_health', 'unknown')} health)")
            else:
                validated_result = {
                    "validated_recommendations": [],
                    "overall_health": app_summary.get("health_status", "unknown"),
                    "summary": "No supplemental recommendations to validate."
                }
                print("    ✓ No RAG/LLM recs to validate — skipping Judge")
        except Exception as e:
            print(f"    ⚠️  Judge validation failed: {e}")
            validated_result = {
                "validated_recommendations": [],
                "overall_health": "unknown",
                "summary": "Validation failed, returning raw supplemental recommendations.",
                "application_id": application_id
            }
            non_kusto_validated = non_kusto_recs

        # Kusto recs are ground truth — prepend verbatim (Judge never touched them)
        kusto_passthrough = [
            {
                "recommendation": rec["text"],
                "source": "kusto",
                "confidence": "high",
                "priority": 1,
                "reasoning": "Verbatim from Kusto telemetry — source of truth, not modified by Judge",
                "action": "",
                "is_generic": False,
                "contradicts": []
            }
            for rec in sparklens_recs + fabric_recs
        ]
        validated_result["validated_recommendations"] = kusto_passthrough + non_kusto_validated

        # Step 7: Return final result
        validated_result["application_summary"] = app_summary
        validated_result["source_counts"] = {
            "kusto": len(sparklens_recs) + len(fabric_recs),
            "rag": len(rag_recs),
            "llm": len(llm_recs)
        }
        
        # Update session context after successful analysis
        session = self.sessions[session_id]
        session["current_app_id"] = application_id
        session["analyzed_apps"][application_id] = validated_result
        session["last_recommendations"] = validated_result.get("validated_recommendations", [])
        session["last_updated"] = datetime.utcnow().isoformat()
        
        print("  └─ ✅ Analysis complete!\n")
        return validated_result
    
    def _format_llm_response(self, text: str) -> str:
        """
        Post-process LLM response to ensure proper markdown formatting.
        Converts plain paragraphs to bullet points if needed.
        """
        import re
        
        # Split into lines
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                formatted_lines.append('')
                continue
            
            # Keep lines that are already bullets or numbered lists
            if stripped.startswith('-') or stripped.startswith('•') or stripped.startswith('*'):
                formatted_lines.append(line)
            elif re.match(r'^\d+\.', stripped):
                formatted_lines.append(line)
            # Keep headers (lines starting with **)
            elif stripped.startswith('**') and stripped.endswith('**'):
                formatted_lines.append(line)
            # Convert questions or section headers to bold
            elif stripped.endswith('?') or stripped.endswith(':'):
                if not stripped.startswith('**'):
                    formatted_lines.append(f"**{stripped}**")
                else:
                    formatted_lines.append(line)
            # Convert key terms to bullet points
            elif any(term in stripped.lower() for term in [
                'issue:', 'fix:', 'impact:', 'validation:',
                'task distribution', 'executor utilization', 'data skew',
                'cpu', 'memory', 'pool', 'executor', 'driver'
            ]):
                # If it doesn't start with a bullet, add one
                if not stripped.startswith('-'):
                    formatted_lines.append(f"- {stripped}")
                else:
                    formatted_lines.append(line)
            else:
                # Regular text - leave as is (might be part of a bullet continuation)
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    
    async def _generate_llm_recommendations(
        self,
        application_id: str,
        app_summary: Dict[str, Any],
        issues: List[str]
    ) -> str:
        """
        Generate recommendations using LLM when telemetry/RAG insufficient.
        """
        # Format metrics for prompt
        metrics_text = json.dumps(app_summary, indent=2) if app_summary else "No metrics available"
        issues_text = "\n".join(f"- {issue}" for issue in issues[:5]) if issues else "No specific issues detected"
        
        prompt = LLM_RECOMMENDATION_PROMPT.format(
            application_id=application_id,
            metrics=metrics_text,
            issues=issues_text,
            ai_warning_block=AI_WARNING_BLOCK.format(confidence="MEDIUM"),
            ai_warning_close=AI_WARNING_BLOCK_CLOSE
        )
        
        # Use Semantic Kernel to generate
        chat_history = ChatHistory()
        chat_history.add_system_message(ORCHESTRATOR_SYSTEM_PROMPT)
        chat_history.add_user_message(prompt)
        
        settings = PromptExecutionSettings(
            max_tokens=2000,
            temperature=0.7
        )
        
        response = await self.chat_service.get_chat_message_content(
            chat_history=chat_history,
            settings=settings
        )
        
        return str(response)
    
    def find_bad_applications(self, min_violations: int = 3) -> List[Dict[str, Any]]:
        """
        Find Spark applications with bad practices.
        
        Args:
            min_violations: Minimum number of violations to include
            
        Returns:
            List of apps with violations, ranked by severity
        """
        print(f"\n🔍 Finding applications with ≥{min_violations} bad practices...")
        
        try:
            bad_apps = self.mcp_client.get_bad_practice_applications(min_violations)
            
            if not bad_apps or len(bad_apps) == 0:
                print("  └─ No applications found")
                return []
            
            # Rank by violation count (descending)
            ranked = sorted(
                bad_apps,
                key=lambda x: x.get("violation_count", 0),
                reverse=True
            )
            
            print(f"  ✓ Found {len(ranked)} applications")
            
            # Add brief explanations
            for app in ranked:
                violations = app.get("violation_count", 0)
                severity = "🔴 CRITICAL" if violations >= 10 else "🟡 WARNING" if violations >= 5 else "⚠️  ATTENTION"
                app["severity_label"] = severity
                app["brief_explanation"] = (
                    f"{severity}: {violations} bad practices detected. "
                    f"Review configuration and resource allocation."
                )
            
            print("  └─ ✅ Ranking complete!\n")
            return ranked
            
        except Exception as e:
            print(f"  └─ ❌ Error: {e}\n")
            return []
    
    def find_recent_applications(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Find Spark applications that ran recently.
        
        Args:
            hours: Number of hours to look back (default 24 for today)
            
        Returns:
            List of recent apps with basic info and health status
        """
        print(f"\n🔍 Finding applications from last {hours} hours...")
        
        try:
            recent_apps = self.mcp_client.get_recent_applications(hours)
            
            if not recent_apps or len(recent_apps) == 0:
                print("  └─ No applications found")
                return []
            
            print(f"  ✓ Found {len(recent_apps)} applications")
            print("  └─ ✅ Query complete!\n")
            return recent_apps
            
        except Exception as e:
            print(f"  └─ ❌ Error: {e}\n")
            return []
    
    async def analyze_skew(self, application_id: str, session_id: str = "default") -> Dict[str, Any]:
        """
        Analyze stage-level data for skew patterns and provide LLM-powered remediation.
        
        Args:
            application_id: Spark application ID
            session_id: Session identifier for context tracking
            
        Returns:
            Dict with skew analysis, problematic stages, and recommendations
        """
        print(f"\n🔍 Analyzing skew for application: {application_id}")
        
        try:
            # Step 1: Get stage summary data
            print("  ├─ Fetching stage summary data...")
            stage_data = self.mcp_client.get_stage_summary(application_id)
            
            if not stage_data or len(stage_data) == 0:
                print("  └─ ⚠️  No stage data found")
                return {
                    "application_id": application_id,
                    "status": "no_data",
                    "message": "No stage summary data found for this application.",
                    "stages_analyzed": 0,
                    "problematic_stages": [],
                    "recommendations": []
                }
            
            print(f"    ✓ Found {len(stage_data)} stages")
            
            # Step 2: Format stage data for LLM analysis
            stage_text = json.dumps(stage_data, indent=2, default=str)
            
            # Step 3: Generate LLM analysis using the skew prompt
            print("  ├─ Analyzing skew patterns with LLM...")
            from .prompts import SKEW_ANALYSIS_PROMPT
            
            prompt = SKEW_ANALYSIS_PROMPT.format(
                application_id=application_id,
                stage_data=stage_text
            )
            
            chat_history = ChatHistory()
            chat_history.add_system_message(
                "You are an expert Spark performance engineer specializing in skew detection and remediation."
            )
            chat_history.add_user_message(prompt)
            
            settings = PromptExecutionSettings(
                max_tokens=3000,
                temperature=0.3  # Lower temp for more deterministic analysis
            )
            
            response = await self.chat_service.get_chat_message_content(
                chat_history=chat_history,
                settings=settings
            )
            
            analysis_text = str(response)
            print("    ✓ LLM analysis complete")
            
            # Step 4: Identify problematic stages (those with high imbalance)
            problematic_stages = []
            for stage in stage_data:
                task_imbalance = stage.get("task_imbalance", 1.0)
                shuffle_imbalance = stage.get("shuffle_imbalance", 1.0)
                
                if task_imbalance > 2.0 or shuffle_imbalance > 2.0:
                    severity = "CRITICAL" if (task_imbalance > 10 or shuffle_imbalance > 10) else \
                               "HIGH" if (task_imbalance > 5 or shuffle_imbalance > 5) else \
                               "MEDIUM" if (task_imbalance > 3 or shuffle_imbalance > 3) else "LOW"
                    
                    problematic_stages.append({
                        "stage_id": stage.get("stage_id"),
                        "task_imbalance": round(task_imbalance, 2),
                        "shuffle_imbalance": round(shuffle_imbalance, 2),
                        "severity": severity,
                        "stage_duration_sec": stage.get("stage_execution_time_sec", 0)
                    })
            
            # Sort by severity and duration
            severity_order = {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 4}
            problematic_stages.sort(
                key=lambda x: (severity_order.get(x["severity"], 99), -x["stage_duration_sec"])
            )
            
            print(f"    ✓ Identified {len(problematic_stages)} stages with skew")
            print("  └─ ✅ Skew analysis complete!\n")
            
            return {
                "application_id": application_id,
                "status": "success",
                "stages_analyzed": len(stage_data),
                "stages_with_skew": len(problematic_stages),
                "problematic_stages": problematic_stages,
                "llm_analysis": analysis_text,
                "source": "kusto_stage_data + llm_analysis"
            }
            
        except Exception as e:
            print(f"  └─ ❌ Error analyzing skew: {e}\n")
            return {
                "application_id": application_id,
                "status": "error",
                "error": str(e),
                "stages_analyzed": 0,
                "problematic_stages": []
            }
    
    async def analyze_scaling_impact(self, application_id: str, session_id: str = "default") -> Dict[str, Any]:
        """
        Analyze whether scaling up/down will improve performance and cost efficiency.
        
        Args:
            application_id: Spark application ID
            session_id: Session identifier for context tracking
            
        Returns:
            Dict with scaling recommendation, predictions analysis, and cost-benefit
        """
        print(f"\n📈 Analyzing scaling impact for: {application_id}")
        
        try:
            # Step 1: Get existing recommendations about scaling
            print("  ├─ Checking existing scaling recommendations...")
            existing_recs = []
            try:
                sparklens_recs = self.mcp_client.get_sparklens_recommendations(application_id)
                for rec in sparklens_recs:
                    rec_text = rec.get("recommendation", "")
                    # Look for scaling-related keywords
                    if any(keyword in rec_text.lower() for keyword in 
                          ["executor", "scale", "driver", "resource", "parallelism"]):
                        existing_recs.append(rec_text)
            except Exception as e:
                print(f"    ⚠️  Could not fetch existing recommendations: {e}")
            
            existing_recs_text = "\n".join(existing_recs) if existing_recs else "No existing scaling recommendations found."
            print(f"    ✓ Found {len(existing_recs)} scaling-related recommendations")
            
            # Step 2: Get scaling predictions from SparkLens
            print("  ├─ Fetching SparkLens scaling predictions...")
            predictions = []
            try:
                predictions = self.mcp_client.get_scaling_predictions(application_id)
                print(f"    ✓ Found {len(predictions)} prediction data points")
            except Exception as e:
                print(f"    ⚠️  Predictions fetch failed: {e}")
            
            predictions_text = json.dumps(predictions, indent=2, default=str) if predictions else \
                              "No scaling predictions available in database."
            
            # Step 3: Get current application metrics
            print("  ├─ Fetching current application metrics...")
            metrics = {}
            try:
                metrics = self.mcp_client.get_application_metrics(application_id)
            except Exception as e:
                print(f"    ⚠️  Metrics fetch failed: {e}")
            
            # Use the ACTUAL measured Application Duration from sparklens_metrics as source of truth.
            # SparkLens predictions (estimated_duration at 1.0x) are a theoretical model estimate
            # and can diverge significantly from the real wall-clock time — do NOT use them as baseline.
            current_executors = metrics.get("executor_count", 0)
            current_duration = metrics.get("duration_sec", 0)
            
            if predictions:
                # Pull executor count from the 1.0x prediction row (more reliable than metrics)
                for pred in predictions:
                    multiplier_str = str(pred.get('executor_multiplier', ''))
                    if '1.0x' in multiplier_str or 'Current' in multiplier_str:
                        current_executors = pred.get('executor_count', current_executors)
                        break
            
            # Final fallback: if metrics had no duration, parse from predictions 1.0x row
            if current_duration == 0 and predictions:
                for pred in predictions:
                    multiplier_str = str(pred.get('executor_multiplier', ''))
                    if '1.0x' in multiplier_str or 'Current' in multiplier_str:
                        duration_str = pred.get('estimated_duration', '')
                        if duration_str:
                            parts = duration_str.replace('m', '').replace('s', '').strip().split()
                            if len(parts) == 2:
                                current_duration = int(parts[0]) * 60 + int(parts[1])
                            elif 'm' in duration_str and 's' not in duration_str:
                                current_duration = int(parts[0]) * 60
                        break
            
            driver_time_pct = metrics.get("driver_time_pct", 0)
            executor_efficiency = metrics.get("executor_efficiency", 0) * 100  # Convert to %
            executor_wall_clock_sec = metrics.get("executor_wall_clock_sec", 0)
            driver_wall_clock_sec = metrics.get("driver_wall_clock_sec", 0)
            
            print(f"    ✓ Current state: {current_duration}s ({current_duration/60:.1f}m), {current_executors} executors, {driver_time_pct:.1f}% driver time")
            
            # Step 4: Generate LLM analysis
            print("  ├─ Generating scaling recommendations with LLM...")
            
            # Human-readable form of the actual duration for the prompt
            _dur_m = int(current_duration) // 60
            _dur_s = int(current_duration) % 60
            actual_duration_display = f"{_dur_m}m {_dur_s}s" if _dur_m > 0 else f"{_dur_s}s"
            
            prompt = SCALING_ANALYSIS_PROMPT.format(
                application_id=application_id,
                existing_recommendations=existing_recs_text,
                predictions_data=predictions_text,
                current_duration_sec=current_duration,
                actual_duration_display=actual_duration_display,
                executor_wall_clock_sec=round(executor_wall_clock_sec, 1),
                driver_wall_clock_sec=round(driver_wall_clock_sec, 1),
                current_executor_count=current_executors,
                driver_time_pct=driver_time_pct,
                executor_efficiency=executor_efficiency
            )
            
            chat_history = ChatHistory()
            chat_history.add_system_message(
                "You are an expert Spark performance engineer specializing in resource optimization and cost-benefit analysis."
            )
            chat_history.add_user_message(prompt)
            
            settings = PromptExecutionSettings(
                max_tokens=3000,
                temperature=0.3  # Lower temp for more deterministic recommendations
            )
            
            response = await self.chat_service.get_chat_message_content(
                chat_history=chat_history,
                settings=settings
            )
            
            analysis_text = str(response)
            print("    ✓ LLM analysis complete")
            
            # Step 5: Extract recommendation from analysis
            recommendation = "ANALYZE_NEEDED"
            if "DON'T SCALE" in analysis_text.upper() or "NO SCALE" in analysis_text.upper():
                recommendation = "DON'T_SCALE"
            elif "SCALE DOWN" in analysis_text.upper():
                recommendation = "SCALE_DOWN"
            elif "SCALE UP" in analysis_text.upper():
                recommendation = "SCALE_UP"
            elif "OPTIMIZE FIRST" in analysis_text.upper():
                recommendation = "OPTIMIZE_FIRST"
            
            print(f"    ✓ Recommendation: {recommendation}")
            print("  └─ ✅ Scaling analysis complete!\n")
            
            return {
                "application_id": application_id,
                "status": "success",
                "recommendation": recommendation,
                "llm_analysis": analysis_text,
                "current_metrics": {
                    "duration_sec": current_duration,
                    "executor_wall_clock_sec": executor_wall_clock_sec,
                    "driver_wall_clock_sec": driver_wall_clock_sec,
                    "executor_count": current_executors,
                    "driver_time_pct": driver_time_pct,
                    "executor_efficiency": executor_efficiency
                },
                "predictions_count": len(predictions),
                "existing_recommendations_count": len(existing_recs),
                "source": "kusto_predictions + kusto_metrics + llm_analysis"
            }
            
        except Exception as e:
            print(f"  └─ ❌ Error analyzing scaling impact: {e}\n")
            return {
                "application_id": application_id,
                "status": "error",
                "error": str(e),
                "recommendation": "ERROR"
            }
    
    def get_cached_schema(self) -> Dict[str, Any]:
        """
        Get database schema with caching (1-hour TTL).
        
        Returns:
            Dictionary of table schemas
        """
        now = datetime.utcnow()
        
        # Check if cache is valid
        if (self._schema_cache is not None and 
            self._schema_cache_time is not None and 
            (now - self._schema_cache_time) < self._schema_cache_ttl):
            print("  ✓ Using cached schema")
            return self._schema_cache
        
        # Fetch fresh schema
        print("  🔍 Fetching database schema...")
        try:
            self._schema_cache = self.mcp_client.get_database_schema()
            self._schema_cache_time = now
            print(f"  ✓ Schema cached ({len(self._schema_cache)} tables)")
            return self._schema_cache
        except Exception as e:
            print(f"  ⚠️ Schema fetch failed: {e}")
            return {}
    
    async def chat(self, user_message: str, session_id: str = "default", context: Optional[Dict[str, Any]] = None) -> str:
        """
        Free-form conversational interface with full pipeline access and session context.
        
        Args:
            user_message: User's message/question
            session_id: Session identifier for maintaining context across turns
            context: Optional context dict (previous analysis results, etc.)
            
        Returns:
            Agent's response as string
        """
        session = self.sessions[session_id]
        
        # Append user message to session
        session["messages"].append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Normalize typos/spelling before routing so skill descriptions match cleanly
        user_message = await self._normalize_input(user_message)

        # Resolve ambiguous references if needed
        resolved = await self._resolve_references(user_message, session)
        resolved_message = resolved.get("resolved_message", user_message)
        resolved_app_id = resolved.get("app_id")
        is_followup = resolved.get("is_followup", False)
        
        # Update context if we resolved an app_id
        if resolved_app_id and resolved_app_id != session.get("current_app_id"):
            session["current_app_id"] = resolved_app_id
        
        # Add context to message if provided
        enhanced_message = resolved_message
        if context:
            context_summary = f"\n\nContext:\n{json.dumps(context, indent=2)}"
            enhanced_message = f"{resolved_message}{context_summary}"
        elif is_followup and session.get("current_app_id"):
            # Add session context for follow-ups
            context_summary = f"\n\nCurrent app: {session['current_app_id']}"
            if session.get("last_recommendations"):
                context_summary += f"\nLast {len(session['last_recommendations'])} recommendations available"
            enhanced_message = f"{resolved_message}{context_summary}"
        
        # Add to chat history
        self.chat_history.add_user_message(enhanced_message)

        # ── Auto-invoke the correct plugin skill via FunctionChoiceBehavior.Auto() ──
        # The LLM reads @kernel_function descriptions to decide which skill(s) to call.
        # No if/elif routing needed — the model handles intent detection.
        try:
            settings = AzureChatPromptExecutionSettings(
                max_tokens=4000,
                temperature=0.3,
                function_choice_behavior=FunctionChoiceBehavior.Auto()
            )
            response = await self.chat_service.get_chat_message_content(
                chat_history=self.chat_history,
                settings=settings,
                kernel=self.kernel
            )
            response_text = str(response)
        except Exception as e:
            print(f"  ⚠️ Plugin auto-invoke failed ({e}), falling back to plain LLM")
            fallback_settings = PromptExecutionSettings(max_tokens=2000, temperature=0.7)
            response = await self.chat_service.get_chat_message_content(
                chat_history=self.chat_history,
                settings=fallback_settings
            )
            response_text = str(response)

        # ── Fallback chain: RAG → LLM → Judge ───────────────────────────────────────
        # ONLY triggers when:
        #   - Plugin returned DATA_NOT_FOUND (explicit sentinel from analyze_app), AND
        #   - The user message references a specific application ID.
        # Fleet / listing queries ("show top 5 slowest apps", "show bad apps") that
        # return zero rows should surface as "no apps found" — never escalate to RAG.
        if self._is_app_not_found(response_text, user_message):
            print("  ℹ️ App-specific Kusto lookup returned no data — triggering RAG/LLM/Judge fallback")
            response_text = await self._rag_llm_fallback(user_message, session)
        elif self._is_knowledge_question(user_message):
            print("  ℹ️ Knowledge/documentation question detected — searching RAG docs...")
            response_text = await self._rag_llm_fallback(user_message, session)

        # ── Update session app_id from any application ID mentioned in the response ──
        import re as _re
        _app_match = _re.search(r'application_\d+_\d+', response_text, _re.IGNORECASE)
        if _app_match and _app_match.group(0) != session.get("current_app_id"):
            session["current_app_id"] = _app_match.group(0)
            print(f"  📱 Session app_id → {session['current_app_id']}")

        self.chat_history.add_assistant_message(response_text)
        session["messages"].append({
            "role": "assistant",
            "content": response_text,
            "timestamp": datetime.utcnow().isoformat()
        })
        session["last_updated"] = datetime.utcnow().isoformat()
        await self._cleanup_old_sessions()
        return response_text

    # ──────────────────────────────────────────────────────────────────────────
    # Fallback chain helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _is_app_not_found(self, response_text: str, user_message: str) -> bool:
        """
        Return True ONLY when an app-specific lookup failed to find the requested
        application ID in Kusto.

        Rules:
        - The user message must contain an application_XXXX_XXXX pattern, OR the
          plugin must have set the DATA_NOT_FOUND sentinel explicitly.
        - Fleet / listing queries ("show top 5 slowest apps", "show bad apps") always
          return False, even if the result set is empty — they should display
          "no apps found" rather than escalating to RAG.
        """
        import re as _re2

        # The plugin's analyze_app skill sets this JSON key explicitly when all
        # three primary Kusto tables return empty for a given app ID.
        if "DATA_NOT_FOUND" in (response_text or ""):
            return True

        # Only consider other no-data phrases when the message itself asked about
        # a specific application (prevents fleet-query false positives).
        has_app_id = bool(_re2.search(r'application_\d+_\d+', user_message, _re2.IGNORECASE))
        if not has_app_id:
            return False

        app_not_found_phrases = [
            "no records found",
            "no data found",
            "not found in any kusto",
            "no data in kusto",
            "application id does not exist",
            "verify the application id",
        ]
        low = (response_text or "").lower()
        return any(p in low for p in app_not_found_phrases)

    def _is_kusto_empty(self, response_text: str) -> bool:
        """Deprecated — use _is_app_not_found. Kept for any external callers."""
        return self._is_app_not_found(response_text, "")

    def _is_knowledge_question(self, message: str) -> bool:
        """
        Returns True for conceptual/documentation questions that should be answered
        from RAG docs rather than LLM training knowledge.
        Matches: "what is X", "what are X", "how does X work", "explain X",
                 "tell me about X", "describe X", "how to X", "why does X".
        Excludes fleet/listing commands ("show", "list", "get", "analyze").
        """
        low = message.lower().strip()
        # Exclude fleet queries and commands that should hit Kusto
        command_prefixes = ("show ", "list ", "get ", "analyze ", "find ", "fetch ", "run ")
        if any(low.startswith(p) for p in command_prefixes):
            return False
        knowledge_patterns = (
            "what is ", "what are ", "what does ", "what's ",
            "how does ", "how do ", "how to ", "how can ",
            "explain ", "describe ", "tell me about ",
            "why does ", "why is ", "when should ", "when to ",
            "difference between", "compare ", "vs ", "versus ",
        )
        return any(p in low for p in knowledge_patterns)

    async def _rag_llm_fallback(self, user_message: str, session: dict) -> str:
        """
        Tier-2/3/4 fallback: RAG → LLM (with context or pure) → Judge → formatted output.

        Called when:
          - A plugin skill detected no Kusto data (DATA_NOT_FOUND / no-data phrase)
          - The user asked a knowledge question and RAG has relevant docs

        Returns a formatted response wrapped in AI_WARNING_BLOCK with Judge validation.
        """
        print("  ├─ [Fallback] Searching RAG docs...")
        rag_docs = self.mcp_client.search_spark_docs(user_message, top_k=3)

        if rag_docs:
            # ── TIER 2: RAG-grounded LLM response ──────────────────────────────
            print(f"  ├─ [Fallback] RAG returned {len(rag_docs)} doc(s) — building grounded response")
            context_parts = []
            for doc in rag_docs:
                title = doc.get("title", "Documentation")
                url = doc.get("source_url", "")
                content = doc.get("content", "")
                src_line = f"Source: {url}" if url else ""
                context_parts.append(f"**{title}**\n{src_line}\n{content}")
            rag_context = "\n\n---\n\n".join(context_parts)

            doc_titles = [doc.get("title", "doc") for doc in rag_docs]
            source_note = f"> Source: RAG — {', '.join(doc_titles)} | OFFICIAL DOCS"
            confidence = "HIGH"

            fallback_history = ChatHistory()
            fallback_history.add_system_message(
                "You are an expert Apache Spark and Microsoft Fabric engineer. "
                "Answer the user's question using ONLY the provided documentation context. "
                "Be specific and actionable. Cite the source document title when referring to it."
            )
            fallback_history.add_user_message(
                f"Documentation context:\n\n{rag_context}\n\n"
                f"User question: {user_message}"
            )
        else:
            # ── TIER 3: Pure LLM fallback ───────────────────────────────────────
            print("  ├─ [Fallback] No RAG results — using pure LLM fallback")
            source_note = "> Source: LLM training knowledge"
            confidence = "MEDIUM"

            fallback_history = ChatHistory()
            fallback_history.add_system_message(
                "You are an expert Apache Spark and Microsoft Fabric engineer. "
                "Answer based on your training knowledge. Be specific and precise."
            )
            fallback_history.add_user_message(user_message)

        fallback_settings = PromptExecutionSettings(max_tokens=2000, temperature=0.4)
        fallback_response = await self.chat_service.get_chat_message_content(
            chat_history=fallback_history,
            settings=fallback_settings,
        )
        llm_answer = str(fallback_response)

        # Build initial response wrapped in AI warning
        warning_header = AI_WARNING_BLOCK.format(confidence=confidence)
        full_response = f"{warning_header}\n{source_note}\n\n{llm_answer}\n{AI_WARNING_BLOCK_CLOSE}"

        # ── TIER 4: Judge validation ─────────────────────────────────────────────
        # Kusto session recs (if any) are passed as read-only reference — Judge
        # contextualises against them but cannot modify or override Kusto output.
        print("  ├─ [Fallback] Running Judge validation...")
        try:
            app_id = session.get("current_app_id") or "general_knowledge"
            recs = [
                {
                    "text": llm_answer,
                    "source": "rag" if rag_docs else "llm",
                    "metadata": {"generated": True, "query": user_message},
                }
            ]
            # Build read-only Kusto reference context from session (never sent as recs to Judge)
            kusto_context = None
            session_kusto_recs = session.get("last_recommendations", [])
            if session_kusto_recs:
                kusto_context = {
                    "kusto_recommendations_reference": [
                        r.get("text", r.get("recommendation", ""))
                        for r in session_kusto_recs
                        if r.get("source") == "kusto" or r.get("metadata", {}).get("from_kusto")
                    ],
                    "note": "Kusto recommendations are source-of-truth — do not modify or override them.",
                }
            judged = self.mcp_client.validate_recommendations(
                application_id=app_id,
                recommendations=recs,
                application_context=kusto_context,
            )
            validated_recs = judged.get("validated_recommendations", [])
            judge_summary = judged.get("summary", "")

            if validated_recs:
                top_rec = validated_recs[0]
                rec_text = top_rec.get("recommendation", llm_answer)
                action = top_rec.get("action", "")
                reasoning = top_rec.get("reasoning", "")

                judge_details = ""
                if reasoning:
                    judge_details += f"\n\n**Validation:** {reasoning}"
                if action:
                    judge_details += f"\n\n**Recommended Actions:** {action}"

                full_response = (
                    f"{warning_header}\n{source_note}\n\n"
                    f"{rec_text}{judge_details}\n"
                    f"{AI_WARNING_BLOCK_CLOSE}"
                )
                if judge_summary:
                    full_response += f"\n\n**Summary:** {judge_summary}"

            print("  └─ [Fallback] ✅ Judge validation complete")
        except Exception as e:
            print(f"  └─ [Fallback] ⚠️ Judge validation skipped: {e}")
            # full_response already set before judge call — keep it as-is

        return full_response

    def _format_analysis_for_chat(self, analysis: Dict[str, Any]) -> str:
        """Format analysis results for chat conversation."""
        app_id = analysis.get("application_id", "unknown")
        health = analysis.get("overall_health", "unknown")
        summary = analysis.get("summary", "")
        recs = analysis.get("validated_recommendations", [])
        
        # Get top 3 recommendations
        top_recs = sorted(recs, key=lambda x: x.get("priority", 999))[:3]
        
        response = f"""
📊 **Analysis Complete for {app_id}**

**Overall Health:** {health.upper()}

**Summary:** {summary}

**Top 3 Recommendations:**
"""
        for i, rec in enumerate(top_recs, 1):
            conf = rec.get("confidence", "unknown")
            text = rec.get("recommendation", rec.get("text", ""))[:150]
            source = rec.get("source", "unknown").upper()
            response += f"\n{i}. [{conf}] [{source}] {text}...\n"
        
        response += f"\n**Total Recommendations:** {len(recs)}"
        response += f"\n**Sources:** Kusto: {analysis.get('source_counts', {}).get('kusto', 0)}, RAG: {analysis.get('source_counts', {}).get('rag', 0)}, LLM: {analysis.get('source_counts', {}).get('llm', 0)}"
        
        return response
    
    def _format_bad_apps_for_chat(self, bad_apps: List[Dict[str, Any]]) -> str:
        """Format bad applications list for chat."""
        if not bad_apps:
            return "✅ Great news! No applications found with significant bad practices."
        
        response = f"🔍 **Found {len(bad_apps)} applications with bad practices:**\n\n"
        
        for i, app in enumerate(bad_apps[:10], 1):  # Limit to top 10
            app_id = app.get("application_id", "unknown")
            violations = app.get("violation_count", 0)
            severity = app.get("severity_label", "")
            explanation = app.get("brief_explanation", "")
            
            response += f"{i}. **{app_id}**\n"
            response += f"   {explanation}\n\n"
        
        if len(bad_apps) > 10:
            response += f"\n... and {len(bad_apps) - 10} more applications.\n"
        
        return response
    
    def _format_recent_apps_for_chat(self, recent_apps: List[Dict[str, Any]], hours: int) -> str:
        """Format recent applications list for chat."""
        if not recent_apps:
            time_desc = "today" if hours == 24 else f"in the last {hours} hours"
            return f"ℹ️ No applications found that ran {time_desc}."
        
        time_desc = "today" if hours == 24 else f"in the last {hours} hours"
        response = f"📊 **Found {len(recent_apps)} applications that ran {time_desc}:**\n\n"
        
        # Group by health status
        critical = [app for app in recent_apps if app.get("health_status") == "CRITICAL"]
        warning = [app for app in recent_apps if app.get("health_status") == "WARNING"]
        healthy = [app for app in recent_apps if app.get("health_status") == "HEALTHY"]
        unknown = [app for app in recent_apps if app.get("health_status") == "UNKNOWN"]
        
        def format_app_line(app):
            app_id = app.get("app_id", "unknown")
            app_name = app.get("app_name", "Unknown")
            duration = app.get("duration_min", 0)
            eff = app.get("executor_efficiency", 0)
            gc = app.get("gc_overhead_pct", 0)
            return f"   • **{app_id}** ({app_name}) - {duration:.1f} min | Executor Eff: {eff:.1%} | GC: {gc:.1f}%"
        
        if critical:
            response += f"\n🔴 **CRITICAL ({len(critical)}):**\n"
            for app in critical[:5]:
                response += format_app_line(app) + "\n"
            if len(critical) > 5:
                response += f"   ... and {len(critical) - 5} more critical apps\n"
        
        if warning:
            response += f"\n🟡 **WARNING ({len(warning)}):**\n"
            for app in warning[:5]:
                response += format_app_line(app) + "\n"
            if len(warning) > 5:
                response += f"   ... and {len(warning) - 5} more warning apps\n"
        
        if healthy:
            response += f"\n✅ **HEALTHY ({len(healthy)}):**\n"
            for app in healthy[:3]:
                response += format_app_line(app) + "\n"
            if len(healthy) > 3:
                response += f"   ... and {len(healthy) - 3} more healthy apps\n"
        
        if unknown:
            response += f"\n❓ **UNKNOWN STATUS ({len(unknown)}):**\n"
            for app in unknown[:2]:
                app_id = app.get("app_id", "unknown")
                response += f"   • **{app_id}**\n"
        
        response += f"\n💡 **Tip:** Use `analyze <app_id>` to get detailed recommendations for any application.\n"
        
        return response
    
    def _format_dynamic_query_results(self, results: List[Dict[str, Any]], query: str, user_question: str) -> str:
        """Format results from dynamically generated KQL query."""
        
        if not results:
            return f"No results found for your query: \"{user_question}\""
        
        response = f"📊 **Query Results** ({len(results)} records)\n\n"
        response += f"*Your question:* {user_question}\n\n"
        
        # Show first 10 results as a table
        if len(results) > 0:
            # Get column names from first result
            columns = list(results[0].keys())
            
            # Limit columns to first 5 for readability
            display_columns = columns[:5]
            
            # Build table header
            response += "| " + " | ".join(display_columns) + " |\n"
            response += "| " + " | ".join(["---"] * len(display_columns)) + " |\n"
            
            # Add rows (limit to 10)
            for row in results[:10]:
                values = []
                for col in display_columns:
                    val = row.get(col, "")
                    # Format value based on type
                    if isinstance(val, float):
                        val_str = f"{val:.2f}"
                    elif isinstance(val, str) and len(val) > 50:
                        val_str = val[:47] + "..."
                    else:
                        val_str = str(val)
                    values.append(val_str)
                response += "| " + " | ".join(values) + " |\n"
            
            if len(results) > 10:
                response += f"\n*Showing first 10 of {len(results)} results*\n"
            
            if len(columns) > 5:
                response += f"\n*Note: Only showing {len(display_columns)} of {len(columns)} columns*\n"
        
        # Add the query for reference (always visible)
        response += f"\n---\n\n### 🔍 Generated KQL Query\n\n```kql\n{query}\n```\n"
        
        response += f"\n💡 **Tip:** You can ask follow-up questions or request analysis of specific applications.\n"
        
        return response
    
    def find_applications_by_pattern(self, pattern: str) -> List[Dict[str, Any]]:
        """
        Find Spark applications matching specific performance patterns.
        
        Args:
            pattern: Pattern to search for:
                - "driver_heavy": High driver time percentage (>80%)
                - "memory_intensive": High GC overhead (>20%)
                - "shuffle_heavy": High shuffle read/write activity
        
        Returns:
            List of applications matching the pattern with metrics
        """
        print(f"\n🔍 Finding applications with pattern: {pattern}...")
        
        try:
            if pattern == "driver_heavy":
                # Query for driver-heavy applications using sparklens_metrics
                # Driver Time % > 80 indicates driver bottleneck
                query = """
                sparklens_metrics
                | where metric == "Driver Time %"
                | where value > 80.0
                | join kind=leftouter (
                    sparklens_metrics
                    | where metric == "Application Duration (sec)"
                    | project app_id, duration = value
                ) on app_id
                | join kind=leftouter (
                    sparklens_metadata
                    | project applicationId, applicationName
                ) on $left.app_id == $right.applicationId
                | project app_id, driver_time_pct = value, duration, 
                          app_name = coalesce(applicationName, "Unknown")
                | order by driver_time_pct desc
                """
            elif pattern == "memory_intensive":
                # Query for memory-intensive applications using GC overhead
                # GC Overhead > 20% indicates memory pressure
                query = """
                sparklens_metrics
                | where metric == "GC Overhead"
                | where value > 0.20
                | join kind=leftouter (
                    sparklens_metrics
                    | where metric == "Application Duration (sec)"
                    | project app_id, duration = value
                ) on app_id
                | join kind=leftouter (
                    sparklens_metadata
                    | project applicationId, applicationName
                ) on $left.app_id == $right.applicationId
                | project app_id, gc_overhead_pct = value * 100, duration,
                          app_name = coalesce(applicationName, "Unknown")
                | order by gc_overhead_pct desc
                """
            elif pattern == "shuffle_heavy":
                # Query for shuffle-heavy applications using stage summaries
                # Check for high shuffle read/write volumes
                query = """
                sparklens_summary
                | where avg_shuffle_read_mb > 100 or avg_shuffle_write_mb > 100
                | summarize total_shuffle_read = sum(avg_shuffle_read_mb * num_tasks),
                            total_shuffle_write = sum(avg_shuffle_write_mb * num_tasks),
                            stage_count = count() by app_id
                | join kind=leftouter (
                    sparklens_metadata
                    | project applicationId, applicationName
                ) on $left.app_id == $right.applicationId
                | project app_id, total_shuffle_read, total_shuffle_write, stage_count,
                          app_name = coalesce(applicationName, "Unknown")
                | order by total_shuffle_read desc
                """
            else:
                print(f"  └─ ❌ Unknown pattern: {pattern}")
                return []
            
            # Execute query
            results = self.mcp_client.query_to_dict_list(query)
            
            if not results or len(results) == 0:
                print(f"  └─ No applications found for pattern: {pattern}")
                return []
            
            print(f"  ✓ Found {len(results)} applications")
            print(f"  └─ ✅ Query complete!\n")
            
            return results
            
        except Exception as e:
            print(f"  └─ ❌ Error: {e}\n")
            return []
    
    def find_healthy_applications(self, min_score: int = 80) -> List[Dict[str, Any]]:
        """
        Find Spark applications that follow best practices.
        
        Args:
            min_score: Minimum health score (0-100) to include
        
        Returns:
            List of healthy applications with health scores
        """
        print(f"\n🔍 Finding healthy applications (min score: {min_score})...")
        
        try:
            # Query for healthy applications using the canonical performance score formula
            # perf_score = (exec_eff*30) + (parallelism*30) + ((1-gc)*20) + ((1/skew)*20)
            query = f"""
sparklens_metrics
| where metric in ("Executor Efficiency","Parallelism Score","GC Overhead","Task Skew Ratio")
| summarize
    exec_eff    = maxif(value, metric == "Executor Efficiency"),
    parallelism = maxif(value, metric == "Parallelism Score"),
    gc          = maxif(value, metric == "GC Overhead"),
    skew        = maxif(value, metric == "Task Skew Ratio")
  by app_id
| extend perf_score = round(
    (exec_eff * 30.0)
    + (parallelism * 30.0)
    + ((1.0 - min_of(gc, 1.0)) * 20.0)
    + ((1.0 / max_of(skew, 1.0)) * 20.0), 1)
| where perf_score >= {min_score}
| order by perf_score desc
| join kind=leftouter (
    sparklens_metadata
    | project applicationId, applicationName, artifactId
  ) on $left.app_id == $right.applicationId
| take 100
"""

            # Execute query
            results = self.mcp_client.query_to_dict_list(query)

            if not results or len(results) == 0:
                print(f"  └─ No healthy applications found (min score: {min_score})")
                return []

            # Add grade labels based on perf_score
            for app in results:
                score = app.get("perf_score", 0)
                if score >= 80:
                    app["Grade"] = "EXCELLENT"
                elif score >= 65:
                    app["Grade"] = "GOOD"
                elif score >= 50:
                    app["Grade"] = "FAIR"
                else:
                    app["Grade"] = "POOR"

            print(f"  ✓ Found {len(results)} healthy applications")
            print(f"  └─ ✅ Query complete!\n")

            return results

        except Exception as e:
            print(f"  └─ ❌ Error: {e}\n")
            return []
    
    async def _normalize_input(self, message: str) -> str:
        """
        Fix typos and misspellings in user input before routing to plugin skills.
        Uses a minimal LLM call (max_tokens=60, temperature=0) — no session context needed.
        Preserves app IDs (application_XXXX_XXXX), metric names, and numbers exactly.
        Returns the original message unchanged if the call fails.
        """
        # Skip normalization for very short messages or messages that are already clean
        # (no non-ASCII, no obvious typo patterns) to save latency
        if len(message.strip()) <= 3:
            return message

        try:
            from semantic_kernel.contents import ChatHistory as _CH
            _hist = _CH()
            _hist.add_system_message(
                "You are a spell-checker. Fix only typos and misspellings in the user's text. "
                "Do NOT rephrase, reorder, or change meaning. "
                "Preserve application IDs (e.g. application_1771441543262_0001), "
                "metric names, numbers, and code snippets exactly as-is. "
                "Reply with ONLY the corrected text — no explanation, no quotes."
            )
            _hist.add_user_message(message)
            _settings = PromptExecutionSettings(max_tokens=150, temperature=0)
            _resp = await self.chat_service.get_chat_message_content(
                chat_history=_hist,
                settings=_settings
            )
            normalized = str(_resp).strip()
            if normalized and normalized != message:
                print(f"  ✏️  Normalized: '{message}' → '{normalized}'")
            return normalized if normalized else message
        except Exception:
            return message

    async def _resolve_references(self, message: str, session: dict) -> dict:
        """
        Resolve ambiguous references in user messages using session context.
        Only calls LLM when message contains ambiguous references.
        
        Args:
            message: User's message
            session: Session context dict
            
        Returns:
            Resolved message with app_id and context
        """
        needs_resolution = (
            len(session["messages"]) > 0 and
            any(t in message.lower() for t in self._ref_triggers)
        )
        
        if not needs_resolution:
            return {
                "message": message,
                "app_id": session.get("current_app_id"),
                "is_followup": False,
                "resolved_message": message
            }
        
        # Build resolution prompt with recent conversation history
        history_text = self._format_history(session['messages'][-6:])
        current_app = session.get("current_app_id", "None")
        last_recs_count = len(session.get("last_recommendations", []))
        
        resolution_prompt = f"""
Conversation history (last 6 turns):
{history_text}

Current context:
- Current application being discussed: {current_app}
- Number of recommendations from last analysis: {last_recs_count}

New user message: "{message}"

Resolve any ambiguous references ("it", "that", "the issue", etc.) in this message.

Return JSON only:
{{
    "app_id": "resolved app ID or null if not app-specific",
    "topic": "specific issue/topic being asked about",
    "is_followup": true/false,
    "resolved_message": "rewritten message with references resolved to be standalone"
}}
"""
        
        try:
            chat_history = ChatHistory()
            chat_history.add_system_message("You are a reference resolution assistant. Return only valid JSON.")
            chat_history.add_user_message(resolution_prompt)
            
            settings = PromptExecutionSettings(
                max_tokens=500,
                temperature=0.1  # Very low temp for deterministic resolution
            )
            
            response = await self.chat_service.get_chat_message_content(
                chat_history=chat_history,
                settings=settings
            )
            
            resolved = json.loads(str(response))
            print(f"  🔗 Resolved reference: '{message}' → '{resolved.get('resolved_message', message)}'")
            return resolved
            
        except Exception as e:
            print(f"  ⚠️ Reference resolution failed: {e}, using original message")
            # Fallback gracefully if resolution fails
            return {
                "message": message,
                "app_id": session.get("current_app_id"),
                "is_followup": True,
                "resolved_message": message
            }
    
    def _format_history(self, messages: List[Dict[str, Any]]) -> str:
        """Format conversation history for prompts."""
        if not messages:
            return "(No previous messages)"
        
        formatted = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:200]  # Truncate long messages
            formatted.append(f"{role.upper()}: {content}")
        
        return "\n".join(formatted)
    
    async def _cleanup_old_sessions(self):
        """Remove sessions inactive for more than 2 hours."""
        try:
            cutoff = datetime.utcnow() - timedelta(hours=2)
            expired = [
                sid for sid, data in self.sessions.items()
                if data.get("last_updated") and
                datetime.fromisoformat(data["last_updated"]) < cutoff
            ]
            
            for sid in expired:
                del self.sessions[sid]
                
            if expired:
                print(f"  🧹 Cleaned up {len(expired)} expired session(s)")
        except Exception as e:
            print(f"  ⚠️ Session cleanup failed: {e}")


# Convenience function for direct usage
async def analyze_spark_application(application_id: str) -> Dict[str, Any]:
    """
    Convenience function to analyze a Spark application.
    
    Args:
        application_id: Spark application ID
        
    Returns:
        Validated recommendations and analysis
    """
    orchestrator = SparkAdvisorOrchestrator()
    return await orchestrator.analyze_application(application_id)
