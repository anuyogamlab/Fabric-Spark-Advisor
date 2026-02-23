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
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.connectors.ai.prompt_execution_settings import PromptExecutionSettings
from semantic_kernel.contents import ChatHistory
from semantic_kernel.functions import kernel_function
from dotenv import load_dotenv

from agent.mcp_client_wrapper import get_mcp_client
from agent.prompts import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    CHAT_SYSTEM_PROMPT,
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
        
        # Chat history for conversational interactions
        self.chat_history = ChatHistory()
        self.chat_history.add_system_message(CHAT_SYSTEM_PROMPT)
        
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
        Full pipeline analysis of a Spark application.
        
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
        
        # Step 5: Combine all results with source tags
        all_recommendations = sparklens_recs + fabric_recs + rag_recs + llm_recs
        print(f"  ├─ Combined {len(all_recommendations)} total recommendations")
        
        # Step 6: Pass to LLM judge for validation
        print("  ├─ Validating with LLM judge...")
        validated_result = {}
        try:
            validated_result = self.mcp_client.validate_recommendations(
                application_id=application_id,
                recommendations=all_recommendations,
                application_context=app_summary
            )
            print(f"    ✓ Validation complete ({validated_result.get('overall_health', 'unknown')} health)")
        except Exception as e:
            print(f"    ⚠️  Judge validation failed: {e}")
            # Fallback to unvalidated recommendations
            validated_result = {
                "validated_recommendations": all_recommendations,
                "overall_health": "unknown",
                "summary": "Validation failed, returning raw recommendations",
                "application_id": application_id
            }
        
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
            
            # Extract current duration from predictions (1.0x baseline) instead of metrics table
            # because SparkLens predictions use a different duration calculation
            current_duration = 0
            current_executors = metrics.get("executor_count", 0)
            
            if predictions:
                # Find the baseline (1.0x or current) prediction
                for pred in predictions:
                    multiplier_str = str(pred.get('executor_multiplier', ''))
                    if '1.0x' in multiplier_str or 'Current' in multiplier_str:
                        # Parse duration from estimated_duration field
                        duration_str = pred.get('estimated_duration', '')
                        if duration_str:
                            # Convert "16m 52s" format to seconds
                            parts = duration_str.replace('m', '').replace('s', '').strip().split()
                            if len(parts) == 2:
                                current_duration = int(parts[0]) * 60 + int(parts[1])
                            elif 'm' in duration_str and 's' not in duration_str:
                                current_duration = int(parts[0]) * 60
                        current_executors = pred.get('executor_count', current_executors)
                        break
            
            # Fallback to metrics table if not found in predictions
            if current_duration == 0:
                current_duration = metrics.get("duration_sec", 0)
            
            driver_time_pct = metrics.get("driver_time_pct", 0)
            executor_efficiency = metrics.get("executor_efficiency", 0) * 100  # Convert to %
            
            print(f"    ✓ Current state: {current_duration}s ({current_duration/60:.1f}m), {current_executors} executors, {driver_time_pct:.1f}% driver time")
            
            # Step 4: Generate LLM analysis
            print("  ├─ Generating scaling recommendations with LLM...")
            
            prompt = SCALING_ANALYSIS_PROMPT.format(
                application_id=application_id,
                existing_recommendations=existing_recs_text,
                predictions_data=predictions_text,
                current_duration_sec=current_duration,
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
    
    async def generate_dynamic_kql_query(self, user_question: str) -> Optional[str]:
        """
        Use LLM to generate a KQL query based on user question and database schema.
        Uses few-shot learning with curated examples for better accuracy.
        
        Args:
            user_question: The user's natural language question
            
        Returns:
            Generated KQL query string or None if generation fails
        """
        # Simplified, focused prompt with key tables only
        prompt = f"""You are a KQL expert. Generate a valid Kusto query for Microsoft Fabric Spark telemetry.

**KEY TABLES (use these only):**

1. **sparklens_metrics** - Performance metrics (columns: app_id, metric, value)
   Key metrics: 'Application Duration (sec)', 'Total Executor Time (sec)', 'Executor Efficiency', 'GC Overhead', 'Task Skew Ratio', 'Parallelism Score', 'Driver Time %', 'Job Type'

2. **sparklens_recommedations** - SparkLens recommendations (columns: app_id, recommendation, severity, category)

3. **fabric_recommedations** - Fabric-specific recommendations (columns: app_id, recommendation, severity, category)

4. **sparklens_metadata** - Spark config properties (columns: app_id, property_name, property_value)

5. **SparkEventLogs** - Spark configurations (columns: AppId, PropertiesJson [JSON blob])
   ⚠️ PropertiesJson field is LARGE (>1000 tokens) - Use parse_json(PropertiesJson) to extract specific properties only
   Common properties: spark.executor.cores, spark.executor.memory, spark.driver.cores, spark.sql.shuffle.partitions

**User Question:** {user_question}

**EXAMPLES (learn from these):**

Q: "show 5 apps"
A: sparklens_metrics | where metric == "Total Executor Time (sec)" | top 5 by value desc | project app_id, executor_time_sec = value

Q: "list all apps"
A: sparklens_metrics | where metric == "Total Executor Time (sec)" | project app_id, executor_time_sec = value | take 100

Q: "show recent apps"
A: sparklens_metrics | where metric == "Total Executor Time (sec)" | top 20 by value desc | project app_id, executor_time_sec = value

Q: "show top 5 slowest apps"
A: sparklens_metrics | where metric == "Application Duration (sec)" | top 5 by value desc | project app_id, duration_sec = value

Q: "share 5 applications that take most amount of time"
A: sparklens_metrics | where metric == "Total Executor Time (sec)" | top 5 by value desc | project app_id, executor_time_sec = value

Q: "which apps took the longest time?"
A: sparklens_metrics | where metric == "Total Executor Time (sec)" | top 10 by value desc | project app_id, executor_time_sec = value

Q: "find streaming jobs"
A: sparklens_metrics | where metric == "Job Type" and value == 1.0 | join kind=inner (sparklens_metrics | where metric == "Total Executor Time (sec)" | project app_id, executor_time_sec = value) on app_id | project app_id, executor_time_sec

Q: "which apps have high GC overhead?"
A: sparklens_metrics | where metric == "GC Overhead" and value > 0.25 | project app_id, gc_overhead = value | order by gc_overhead desc | take 100

Q: "show apps with low executor efficiency"
A: sparklens_metrics | where metric == "Executor Efficiency" and value < 0.4 | project app_id, efficiency = value | order by efficiency asc | take 100

Q: "count how many apps exist"
A: sparklens_metrics | where metric == "Total Executor Time (sec)" | distinct app_id | count

Q: "group apps by severity"
A: sparklens_recommedations | summarize count() by severity

Q: "find apps with critical issues"
A: sparklens_recommedations | where severity == "CRITICAL" | distinct app_id | take 100

Q: "show apps using more than 10GB memory"
A: sparklens_metadata | where property_name == "spark.executor.memory" and property_value contains "g" | project app_id, memory = property_value | take 100

Q: "which apps have driver bottleneck?"
A: sparklens_metrics | where metric == "Driver Time %" and value > 80.0 | project app_id, driver_pct = value | order by driver_pct desc | take 100

Q: "show top 3 apps by executor time"
A: sparklens_metrics | where metric == "Total Executor Time (sec)" | top 3 by value desc | project app_id, executor_time_sec = value

Q: "how many cores per executor for application_XXX?"
A: SparkEventLogs | where ApplicationId == "application_XXX" | extend properties = parse_json(jsn) | extend executor_cores = tostring(properties["spark.executor.cores"]) | where isnotempty(executor_cores) | summarize executor_cores = max(executor_cores) by ApplicationId | project app_id = ApplicationId, executor_cores

Q: "what are the spark configurations for application_XXX?"
A: SparkEventLogs | where ApplicationId == "application_XXX" | extend properties = parse_json(jsn) | extend driver_cores = tostring(properties["spark.driver.cores"]), executor_cores = tostring(properties["spark.executor.cores"]), executor_memory = tostring(properties["spark.executor.memory"]), shuffle_partitions = tostring(properties["spark.sql.shuffle.partitions"]) | where isnotempty(executor_cores) | summarize driver_cores = max(driver_cores), executor_cores = max(executor_cores), executor_memory = max(executor_memory), shuffle_partitions = max(shuffle_partitions) by ApplicationId | project ApplicationId, driver_cores, executor_cores, executor_memory, shuffle_partitions

**RULES:**
1. For "most time" / "took time" / "consumed time" queries: Use `metric == "Total Executor Time (sec)"` (total compute time consumed)
2. For "slowest" / "longest duration" / "wall clock" queries: Use `metric == "Application Duration (sec)"` (end-to-end runtime)
3. For Spark configuration properties: Use `SparkEventLogs` table with `parse_json(jsn)` to extract specific fields (e.g., spark.executor.cores, spark.executor.memory)
4. **IMPORTANT for SparkEventLogs**: Each application has MULTIPLE rows - use `summarize` with `max()` or `any()` to get configuration values after filtering with `where isnotempty()`
5. ALWAYS use `| take 100` at the end to limit results (or use `top N` for rankings)
6. Use descriptive column names in project: `executor_time_sec` for total executor time, `duration_sec` for application duration
7. For metrics queries: filter on EXACT metric name (case-sensitive): "Total Executor Time (sec)", "Application Duration (sec)", "Executor Efficiency", etc.
8. Add ordering for better UX: `| order by value desc` for rankings or `| top N by value desc` for top-N queries
9. For recommendations: severity values are CRITICAL, HIGH, MEDIUM, LOW (all caps)
10. When extracting JSON properties from SparkEventLogs: Use `parse_json(PropertiesJson)` and `tostring(properties["property.name"])` to avoid retrieving large blobs
11. Return ONLY the KQL query, no explanation, no markdown code blocks

Generate query:"""
        
        try:
            chat_history = ChatHistory()
            chat_history.add_system_message("You are a KQL query generation expert. Return only valid KQL queries without markdown, explanations, or code blocks.")
            chat_history.add_user_message(prompt)
            
            settings = PromptExecutionSettings(
                max_tokens=800,  # Reduced - queries should be concise
                temperature=0.2  # Slightly higher for better generalization
            )
            
            response = await self.chat_service.get_chat_message_content(
                chat_history=chat_history,
                settings=settings
            )
            
            query = str(response).strip()
            
            # Clean up query
            # Remove markdown code blocks
            if query.startswith("```"):
                lines = query.split("\n")
                # Find first and last code fence
                start = 1 if lines[0].startswith("```") else 0
                end = -1 if len(lines) > 1 and lines[-1].startswith("```") else len(lines)
                query = "\n".join(lines[start:end])
            
            # Remove "A:" prefix if present
            query = query.removeprefix("A:").strip()
            
            # Validate basic query structure
            query_lower = query.lower()
            if not any(table in query_lower for table in ["sparklens_metrics", "sparklens_recommedations", "fabric_recommedations", "sparklens_metadata"]):
                print(f"  ⚠️ Query validation failed: No valid table name found")
                return None
            
            # Check for dangerous operations
            dangerous_ops = [".drop", ".create", ".alter", ".delete", ".set", "database", "cluster"]
            if any(op in query_lower for op in dangerous_ops):
                print(f"  ⚠️ Query validation failed: Contains dangerous operation")
                return None
            
            print(f"  ✓ Generated query:\n{query[:200]}...")
            return query
            
        except Exception as e:
            print(f"  ⚠️ Query generation failed: {e}")
            return None
    
    async def execute_dynamic_query(self, user_question: str) -> tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Generate and execute a dynamic KQL query based on user question.
        
        Args:
            user_question: The user's natural language question
            
        Returns:
            Tuple of (results, generated_query) or (None, None) if failed
        """
        print(f"\n🤖 Generating dynamic query for: {user_question}")
        
        # Generate query
        query = await self.generate_dynamic_kql_query(user_question)
        
        if not query:
            return None, None
        
        # Execute with safety checks
        try:
            results = self.mcp_client.execute_dynamic_query(query, max_results=100)
            print(f"  ✓ Query executed successfully ({len(results)} results)")
            return results, query
        except Exception as e:
            print(f"  ❌ Query execution failed: {e}")
            return None, query
    
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
        
        # Check if user is asking to analyze an application (fuzzy match for typos)
        if ("analyz" in user_message.lower() or "check" in user_message.lower() or "review" in user_message.lower()) and ("application" in user_message.lower() or "app" in user_message.lower()):
            # Try to extract application ID
            import re
            match = re.search(r'application[_\s]+([a-zA-Z0-9_]+)', user_message)
            if match:
                app_id = match.group(1)
                # Run analysis
                result = await self.analyze_application(app_id)
                
                # Format response
                response_text = self._format_analysis_for_chat(result)
                self.chat_history.add_assistant_message(response_text)
                return response_text
        
        # Check if user wants bad applications
        if "bad" in user_message.lower() and ("application" in user_message.lower() or "practice" in user_message.lower()):
            bad_apps = self.find_bad_applications()
            response_text = self._format_bad_apps_for_chat(bad_apps)
            self.chat_history.add_assistant_message(response_text)
            return response_text
        
        # Check if user wants top applications by time/duration (slowest/fastest)
        is_top_apps_query = any([
            ("top" in user_message.lower() or "slowest" in user_message.lower() or "fastest" in user_message.lower()) and ("app" in user_message.lower() or "application" in user_message.lower()),
            ("longest" in user_message.lower() or "shortest" in user_message.lower()) and ("app" in user_message.lower() or "application" in user_message.lower()),
            ("took" in user_message.lower() or "take" in user_message.lower() or "takes" in user_message.lower()) and ("most" in user_message.lower() or "time" in user_message.lower()) and ("app" in user_message.lower() or "application" in user_message.lower()),
        ])
        if is_top_apps_query:
            print(f"  📊 Detected top applications query - querying Kusto predictions...")
            
            # Extract limit (default to 5)
            import re
            limit_match = re.search(r'\b(\d+)\b', user_message)
            limit = int(limit_match.group(1)) if limit_match else 5
            
            # Determine if slowest (desc) or fastest (asc)
            is_fastest = "fastest" in user_message.lower() or "shortest" in user_message.lower()
            order = "asc" if is_fastest else "desc"
            
            # Query predictions table for current state (contains "Current")
            # Convert duration from "Xm Ys" format to seconds for proper numeric sorting
            query = f'''
                sparklens_predictions
                | where ["Executor Multiplier"] contains "Current"
                | project 
                    app_id,
                    executor_count = tolong(["Executor Count"]),
                    duration = ["Estimated Total Duration"]
                | extend duration_seconds = 
                    tolong(extract(@"(\\d+)m", 1, duration)) * 60 + 
                    tolong(extract(@"(\\d+)s", 1, duration))
                | top {limit} by duration_seconds {order}
                | project app_id, executor_count, duration
            '''
            
            try:
                results = self.mcp_client.query_to_dict_list(query)
                
                if results and len(results) > 0:
                    direction = "fastest" if is_fastest else "slowest"
                    response_text = f"📊 **Top {limit} {direction} applications:**\n\n"
                    
                    # Table header
                    response_text += "| # | Application ID | Executors | Duration |\n"
                    response_text += "|---|---|---|---|\n"
                    
                    for i, row in enumerate(results, 1):
                        app_id = row.get('app_id', 'N/A')
                        executor_count = row.get('executor_count', 'N/A')
                        duration = row.get('duration', 'N/A')
                        response_text += f"| {i} | `{app_id}` | {executor_count} | {duration} |\n"
                    
                    response_text += f"\n💡 Reply with `analyze {results[0].get('app_id')}` to get detailed recommendations."
                    
                    self.chat_history.add_assistant_message(response_text)
                    
                    # Store in session
                    session["messages"].append({
                        "role": "assistant",
                        "content": response_text,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    session["last_updated"] = datetime.utcnow().isoformat()
                    
                    print(f"  ✅ Returned {len(results)} applications from Kusto")
                    return response_text
                else:
                    response_text = "❌ No application predictions found in Kusto. The `sparklens_predictions` table may be empty."
                    self.chat_history.add_assistant_message(response_text)
                    return response_text
            except Exception as e:
                print(f"  ❌ Error querying Kusto: {e}")
                response_text = f"❌ Error querying Kusto: {str(e)}\n\nPlease verify the table `sparklens_predictions` exists and contains data."
                self.chat_history.add_assistant_message(response_text)
                return response_text
        
        # Check if user wants executor count for an application
        is_executor_count_query = any([
            ("how many executor" in user_message.lower() or "number of executor" in user_message.lower()) and ("application" in user_message.lower() or "app" in user_message.lower()),
            ("executor count" in user_message.lower() or "executors did" in user_message.lower()) and ("application" in user_message.lower() or "app" in user_message.lower()),
            "ran with" in user_message.lower() and "executor" in user_message.lower(),
            ("how many cores" in user_message.lower() or "cores per executor" in user_message.lower() or "executor cores" in user_message.lower()),
        ])
        if is_executor_count_query:
            print(f"  🔢 Detected executor configuration query...")
            
            # Try to extract application ID from query
            import re
            app_id_match = re.search(r'application_\d+_\d+', user_message, re.IGNORECASE)
            
            if app_id_match:
                app_id = app_id_match.group(0)
                print(f"  📊 Found app ID in query: {app_id}")
            else:
                # Check if there's a current app in session
                app_id = session.get("current_app_id")
                if not app_id:
                    response_text = "❌ Please specify an application ID in your query, or analyze an application first.\n\n**Example:** `how many executors did application_1771441543262_0001 run with?`"
                    self.chat_history.add_assistant_message(response_text)
                    return response_text
                print(f"  📊 Using current app from session: {app_id}")
            
            # Query for executor count AND configuration from both tables
            # First get executor count from metrics
            metrics_query = f'''
                sparklens_metrics
                | where app_id == '{app_id}' and metric == "Executor Count"
                | project app_id, executor_count = tolong(value)
            '''
            
            # Then get executor cores/memory from SparkEventLogs (parse JSON efficiently)
            # Note: Each app may have multiple rows, so we search for rows with config properties
            config_query = f'''
                SparkEventLogs
                | where AppId == '{app_id}'
                | extend properties = parse_json(PropertiesJson)
                | extend 
                    executor_cores = tostring(properties["spark.executor.cores"]),
                    executor_memory = tostring(properties["spark.executor.memory"]),
                    driver_cores = tostring(properties["spark.driver.cores"]),
                    driver_memory = tostring(properties["spark.driver.memory"])
                | where isnotempty(executor_cores) or isnotempty(executor_memory)
                | summarize 
                    executor_cores = max(executor_cores),
                    executor_memory = max(executor_memory),
                    driver_cores = max(driver_cores),
                    driver_memory = max(driver_memory)
                    by AppId
                | project 
                    app_id = AppId,
                    executor_cores,
                    executor_memory,
                    driver_cores,
                    driver_memory
            '''
            
            try:
                # Get executor count
                metrics_result = self.mcp_client.query_to_dict_list(metrics_query)
                executor_count = metrics_result[0].get('executor_count', 'N/A') if metrics_result else 'N/A'
                
                # Get configuration (cores/memory) - this might fail if SparkEventLogs doesn't exist
                config_result = []
                executor_cores = 'N/A'
                executor_memory = 'N/A'
                driver_cores = 'N/A'
                driver_memory = 'N/A'
                
                try:
                    config_result = self.mcp_client.query_to_dict_list(config_query)
                    if config_result:
                        executor_cores = config_result[0].get('executor_cores', 'N/A')
                        executor_memory = config_result[0].get('executor_memory', 'N/A')
                        driver_cores = config_result[0].get('driver_cores', 'N/A')
                        driver_memory = config_result[0].get('driver_memory', 'N/A')
                except Exception as e:
                    print(f"  ⚠️ Could not fetch config from SparkEventLogs: {e}")
                
                if executor_count == 'N/A' and not config_result:
                    response_text = f"❌ No executor information found for `{app_id}`.\n\nPlease verify the application ID is correct."
                    self.chat_history.add_assistant_message(response_text)
                    return response_text
                
                # Calculate total cores (executor_count × executor_cores)
                total_cores = 'N/A'
                if executor_count != 'N/A' and executor_cores != 'N/A':
                    try:
                        total_cores = int(executor_count) * int(executor_cores)
                    except (ValueError, TypeError):
                        total_cores = 'N/A (calculation failed)'
                
                # Format response with available data
                response_text = f"🔢 **Executor Configuration for `{app_id}`:**\n\n"
                response_text += "| Property | Value |\n"
                response_text += "|---|---|\n"
                response_text += f"| Executor Count | **{executor_count}** |\n"
                response_text += f"| Executor Cores (per executor) | {executor_cores} |\n"
                response_text += f"| **Total Cores** | **{total_cores}** |\n"
                response_text += f"| Executor Memory (per executor) | {executor_memory} |\n"
                response_text += f"| Driver Cores | {driver_cores} |\n"
                response_text += f"| Driver Memory | {driver_memory} |\n"
                
                # Add source information
                response_text += "\n📊 **Data Sources:**\n"
                response_text += f"- Executor Count: `sparklens_metrics` table ✅\n"
                
                if config_result and executor_cores != 'N/A':
                    response_text += f"- Configuration: `SparkEventLogs` table ✅\n"
                    if total_cores != 'N/A':
                        response_text += f"\n🧮 **Calculation:** Total Cores = {executor_count} executors × {executor_cores} cores = **{total_cores} cores**\n"
                else:
                    response_text += f"- Configuration: `SparkEventLogs` table ❌ (not available)\n"
                    response_text += f"\n💡 **Note:** Executor cores/memory data requires the `SparkEventLogs` table with Spark configuration properties.\n"
                
                response_text += "\n💡 **Want to see scaling impact?**\n"
                response_text += f"Ask: `will increasing executors improve performance for {app_id}?`"
                
                self.chat_history.add_assistant_message(response_text)
                
                # Store in session
                session["messages"].append({
                    "role": "assistant",
                    "content": response_text,
                    "timestamp": datetime.utcnow().isoformat()
                })
                session["last_updated"] = datetime.utcnow().isoformat()
                
                print(f"  ✅ Returned executor config: count={executor_count}, cores={executor_cores}")
                return response_text
                
            except Exception as e:
                print(f"  ❌ Error querying Kusto: {e}")
                response_text = f"❌ Error querying Kusto: {str(e)}"
                self.chat_history.add_assistant_message(response_text)
                return response_text
        
        # Check if user wants to list/show available applications
        is_list_apps_query = any([
            ("list" in user_message.lower() or "show" in user_message.lower()) and ("available" in user_message.lower() or "all" in user_message.lower()) and ("app" in user_message.lower() or "application" in user_message.lower()),
            "what apps" in user_message.lower() and ("available" in user_message.lower() or "exist" in user_message.lower() or "have" in user_message.lower()),
        ])
        if is_list_apps_query:
            print(f"  📋 Detected list apps query - querying Kusto...")
            
            # Extract limit (default to 20)
            import re
            limit_match = re.search(r'\b(\d+)\b', user_message)
            limit = int(limit_match.group(1)) if limit_match else 20
            
            # Query for distinct app IDs
            query = f'sparklens_recommedations | distinct app_id | take {limit}'
            
            try:
                results = self.mcp_client.query_to_dict_list(query)
                
                if results and len(results) > 0:
                    response_text = f"📋 **Available applications in Kusto (showing first {len(results)}):**\n\n"
                    
                    for i, row in enumerate(results, 1):
                        app_id = row.get('app_id', 'N/A')
                        response_text += f"{i}. `{app_id}`\n"
                    
                    response_text += f"\n💡 Reply with `analyze application_XXX` to get recommendations for any app."
                    
                    self.chat_history.add_assistant_message(response_text)
                    
                    # Store in session
                    session["messages"].append({
                        "role": "assistant",
                        "content": response_text,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    session["last_updated"] = datetime.utcnow().isoformat()
                    
                    print(f"  ✅ Returned {len(results)} applications from Kusto")
                    return response_text
                else:
                    response_text = "❌ No applications found in Kusto. The `sparklens_recommedations` table may be empty."
                    self.chat_history.add_assistant_message(response_text)
                    return response_text
            except Exception as e:
                print(f"  ❌ Error querying Kusto: {e}")
                response_text = f"❌ Error querying Kusto: {str(e)}\n\nPlease verify the table `sparklens_recommedations` exists and contains data."
                self.chat_history.add_assistant_message(response_text)
                return response_text
        
        # Check if user wants recent applications
        is_recent_query = any([
            "today" in user_message.lower(),
            "recent" in user_message.lower() and "application" in user_message.lower(),
            "ran today" in user_message.lower(),
            "executed today" in user_message.lower(),
            "last " in user_message.lower() and ("hour" in user_message.lower() or "day" in user_message.lower()),
        ])
        if is_recent_query:
            # Parse hours if specified
            import re
            hours = 24  # default to today
            hour_match = re.search(r'last\s+(\d+)\s+hour', user_message.lower())
            day_match = re.search(r'last\s+(\d+)\s+day', user_message.lower())
            if hour_match:
                hours = int(hour_match.group(1))
            elif day_match:
                hours = int(day_match.group(1)) * 24
            
            recent_apps = self.find_recent_applications(hours)
            response_text = self._format_recent_apps_for_chat(recent_apps, hours)
            self.chat_history.add_assistant_message(response_text)
            
            # Store in session
            session["messages"].append({
                "role": "assistant",
                "content": response_text,
                "timestamp": datetime.utcnow().isoformat()
            })
            session["last_updated"] = datetime.utcnow().isoformat()
            
            return response_text
        
        # Check if this is a broad best practices / how-to question
        is_broad_question = any([
            "best practice" in user_message.lower(),
            "how to" in user_message.lower(),
            "how do i" in user_message.lower(),
            "how should i" in user_message.lower(),
            "what is" in user_message.lower(),
            "configure" in user_message.lower() and "fabric" in user_message.lower(),
            "tune" in user_message.lower() or "tuning" in user_message.lower(),
            "optimize" in user_message.lower() and "fabric" in user_message.lower(),
            "aqe" in user_message.lower(),
            "native execution" in user_message.lower(),
            "vorder" in user_message.lower() or "v-order" in user_message.lower(),
        ])
        
        if is_broad_question:
            print(f"  🔍 Detected broad question - querying RAG documentation...")
            
            # Query RAG for relevant documentation
            try:
                rag_results = self.mcp_client.search(user_message, top_k=5)
                
                if rag_results and len(rag_results) > 0:
                    # Format RAG chunks
                    rag_chunks = "\n\n---\n\n".join([
                        f"**Source:** {r.get('filename', 'Unknown')}\n**Content:**\n{r.get('content', '')[:1000]}"
                        for r in rag_results[:5]
                    ])
                    
                    # Build prompt
                    prompt = BROAD_QUESTION_PROMPT.format(
                        rag_chunks=rag_chunks,
                        question=user_message
                    )
                    
                    # Get LLM response
                    chat_history = ChatHistory()
                    chat_history.add_system_message("You are a Microsoft Fabric Spark expert.")
                    chat_history.add_user_message(prompt)
                    
                    settings = PromptExecutionSettings(
                        max_tokens=2000,
                        temperature=0.3  # Lower temp for factual answers
                    )
                    
                    response = await self.chat_service.get_chat_message_content(
                        chat_history=chat_history,
                        settings=settings
                    )
                    
                    response_text = str(response)
                    self.chat_history.add_assistant_message(response_text)
                    
                    # Store response in session
                    session["messages"].append({
                        "role": "assistant",
                        "content": response_text,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    session["last_updated"] = datetime.utcnow().isoformat()
                    
                    # Cleanup old sessions
                    await self._cleanup_old_sessions()
                    
                    print(f"  ✅ Answered using {len(rag_results)} RAG documentation chunks")
                    return response_text
                else:
                    print(f"  ⚠️ No RAG results found, falling back to LLM knowledge")
            except Exception as e:
                print(f"  ⚠️ RAG query failed: {e}, falling back to LLM")
        
        # Try dynamic query generation for data-related questions
        # This catches queries like "show me streaming jobs", "group by capacity", etc.
        is_data_query = any([
            "show" in user_message.lower(),
            "list" in user_message.lower(),
            "find" in user_message.lower(),
            "get" in user_message.lower(),
            "share" in user_message.lower(),  # Added: share 5 apps, share top apps, etc.
            "give me" in user_message.lower(),  # Added: give me 5 apps, etc.
            "which" in user_message.lower(),
            "what" in user_message.lower() and any(x in user_message.lower() for x in ["applications", "apps", "jobs"]),
            "how many" in user_message.lower(),
            "count" in user_message.lower(),
            "group" in user_message.lower(),
            "average" in user_message.lower(),
            "sum" in user_message.lower() or "total" in user_message.lower(),
            "top" in user_message.lower() and any(x in user_message.lower() for x in ["applications", "apps", "jobs"]),
        ])
        
        # Exclude if already handled by specific intents
        is_already_handled = any([
            "analyze" in user_message.lower() and "application" in user_message.lower(),
            "bad" in user_message.lower() and ("apps" in user_message.lower() or "practices" in user_message.lower()),
            is_recent_query,
            is_broad_question
        ])
        
        if is_data_query and not is_already_handled:
            print(f"  🤖 Attempting dynamic query generation...")
            
            try:
                results, query = await self.execute_dynamic_query(user_message)
                
                if results is not None and len(results) > 0:
                    # Format results
                    response_text = self._format_dynamic_query_results(results, query, user_message)
                    self.chat_history.add_assistant_message(response_text)
                    
                    # Store in session
                    session["messages"].append({
                        "role": "assistant",
                        "content": response_text,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    session["last_updated"] = datetime.utcnow().isoformat()
                    
                    await self._cleanup_old_sessions()
                    
                    print(f"  ✅ Answered using dynamic KQL query")
                    return response_text
                elif query:
                    # Query was generated but failed - show error with helpful hints
                    hints = []
                    if "SparkSQLExecutionEvents" in query and any(x in user_message.lower() for x in ["time", "duration", "longest", "slowest"]):
                        hints.append("💡 **Hint:** For queries about total compute time consumed, use `sparklens_metrics` table with `metric == 'Total Executor Time (sec)'`. For application wall-clock duration, use `metric == 'Application Duration (sec)'`.")
                    if "datetime_diff" in query or "EndTime" in query or "StartTime" in query:
                        hints.append("💡 **Hint:** Duration is pre-calculated in the `sparklens_metrics` table - no need to calculate from StartTime/EndTime.")
                    
                    hints_text = "\n\n" + "\n".join(hints) if hints else ""
                    
                    response_text = f"""I generated this query to answer your question:

```kql
{query}
```

However, the query failed to execute. This might be due to:
- Missing data in the table
- Incorrect column names or data types
- Empty result set{hints_text}

Try asking: "Show me the top 5 applications by duration" or "Which apps took the most time?"
"""
                    self.chat_history.add_assistant_message(response_text)
                    
                    session["messages"].append({
                        "role": "assistant",
                        "content": response_text,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    session["last_updated"] = datetime.utcnow().isoformat()
                    
                    return response_text
            except Exception as e:
                print(f"  ⚠️ Dynamic query failed: {e}, falling back to LLM")
        
        # Otherwise, regular chat with LLM
        settings = PromptExecutionSettings(
            max_tokens=2000,
            temperature=0.7
        )
        
        response = await self.chat_service.get_chat_message_content(
            chat_history=self.chat_history,
            settings=settings
        )
        
        response_text = str(response)
        self.chat_history.add_assistant_message(response_text)
        
        # Store response in session
        session["messages"].append({
            "role": "assistant",
            "content": response_text,
            "timestamp": datetime.utcnow().isoformat()
        })
        session["last_updated"] = datetime.utcnow().isoformat()
        
        # Cleanup old sessions
        await self._cleanup_old_sessions()
        
        return response_text
    
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
            # Query for healthy applications
            query = f"""
            SparkLogs
            | join kind=leftouter (
                SparkRecommendations
                | summarize ViolationCount=count(), 
                            CriticalCount=countif(Severity == "CRITICAL") by ApplicationId
            ) on ApplicationId
            | summarize 
                ViolationCount=max(coalesce(ViolationCount, 0)),
                TotalJobs=count(),
                CriticalCount=max(coalesce(CriticalCount, 0)) by ApplicationId
            | extend HealthScore = 100 
                     - (ViolationCount * 5) 
                     - (CriticalCount * 20)
            | where HealthScore >= {min_score}
            | order by HealthScore desc
            """
            
            # Execute query
            results = self.mcp_client.query_to_dict_list(query)
            
            if not results or len(results) == 0:
                print(f"  └─ No healthy applications found (min score: {min_score})")
                return []
            
            # Add grade labels
            for app in results:
                score = app.get("HealthScore", 0)
                if score >= 90:
                    app["Grade"] = "A"
                elif score >= 80:
                    app["Grade"] = "B"
                else:
                    app["Grade"] = "C"
            
            print(f"  ✓ Found {len(results)} healthy applications")
            print(f"  └─ ✅ Query complete!\n")
            
            return results
            
        except Exception as e:
            print(f"  └─ ❌ Error: {e}\n")
            return []
    
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
