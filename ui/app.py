"""
Chainlit Chat UI for Spark Recommender Agent
Provides an interactive interface to analyze Spark applications on Microsoft Fabric
"""
import sys
import os
import logging
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging to suppress verbose Azure SDK logs  
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.identity").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("semantic_kernel").setLevel(logging.WARNING)

import re
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
import chainlit as cl
from agent.orchestrator import SparkAdvisorOrchestrator


# ============================================================================
# INTENT DETECTION
# ============================================================================

def detect_feedback(message: str) -> Optional[Dict[str, Any]]:
    """
    Detect if message is user feedback (HELPFUL, NOT HELPFUL, PARTIAL).
    
    Returns:
        Dict with feedback_type and comment, or None if not feedback
    """
    message_upper = message.upper().strip()
    
    # Pattern: HELPFUL [optional comment]
    if message_upper.startswith('HELPFUL'):
        comment = message[7:].strip()  # Everything after "HELPFUL"
        return {
            "feedback_type": "HELPFUL",
            "comment": comment
        }
    
    # Pattern: NOT HELPFUL [reason: ...]
    if message_upper.startswith('NOT HELPFUL'):
        comment = message[11:].strip()  # Everything after "NOT HELPFUL"
        return {
            "feedback_type": "NOT_HELPFUL",
            "comment": comment
        }
    
    # Pattern: PARTIAL [what was missing]
    if message_upper.startswith('PARTIAL'):
        comment = message[7:].strip()  # Everything after "PARTIAL"
        return {
            "feedback_type": "PARTIAL",
            "comment": comment
        }
    
    return None


def extract_application_id(message: str) -> Optional[str]:
    """
    Extract Spark application ID from message text.
    
    Supports formats:
    - application_1771438258399_0001
    - app 12345
    - application-12345
    
    Args:
        message: User message text
        
    Returns:
        Extracted application ID or None if not found
    """
    message_lower = message.lower()
    
    # Pattern for full application ID format: application_TIMESTAMP_INDEX
    full_match = re.search(r'(application[_\s-]+\d+[_\s-]+\d+)', message, re.IGNORECASE)
    if full_match:
        return full_match.group(1).replace(" ", "_").replace("-", "_")
    
    # Fallback patterns for partial IDs
    patterns = [
        r'app[_\s-]*(\d+)',
        r'application[_\s-]*(\d+)',
        r'spark[_\s-]*app[_\s-]*(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message_lower)
        if match:
            return f"application_{match.group(1)}"
    
    return None


def detect_intent(message: str) -> Dict[str, Any]:
    """
    Classify user message intent using keyword matching and regex.
    
    Returns:
        dict with "intent" and "params" keys
    """
    message_lower = message.lower()
    
    # INTENT 1: analyze_app (fuzzy match to handle typos)
    analyze_triggers = ["analyz", "recommendations for", "what issues", 
                       "best practices for", "check app", "review app"]
    if any(trigger in message_lower for trigger in analyze_triggers):
        # Extract application ID pattern
        patterns = [
            r'app[_\s-]*(\d+)',  # app-123, app_123, app 123
            r'application[_\s-]*(\d+)',  # application-123
            r'spark[_\s-]*app[_\s-]*(\d+)',  # spark-app-123
            r'application[_\s]+([a-zA-Z0-9_]+)',  # application_1771438258399_0001
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message_lower)
            if match:
                app_id = match.group(1)
                # Reconstruct full ID if needed
                if "application_" in message_lower and "_" in message:
                    # Extract full application ID
                    full_match = re.search(r'(application[_\s]+[a-zA-Z0-9_]+)', message, re.IGNORECASE)
                    if full_match:
                        app_id = full_match.group(1).replace(" ", "_")
                
                return {
                    "intent": "analyze_app",
                    "params": {"application_id": app_id}
                }
    
    # INTENT 2: show_bad_apps
    bad_triggers = ["bad apps", "which apps have issues", "problem applications",
                   "apps with errors", "show issues", "worst apps",
                   "poor coding", "bad practices"]
    if any(trigger in message_lower for trigger in bad_triggers):
        return {
            "intent": "show_bad_apps",
            "params": {"min_violations": 3}
        }
    
    # INTENT 3: show_recent_apps (includes "all apps" queries)
    # Use flexible pattern matching for "show/list all [the] [spark] apps/applications"
    show_all_pattern = re.compile(r'\b(show|list|get|display)\s+(me\s+)?(all|every)\s+(the\s+)?(\w+\s+)?(apps?|applications?)\b')
    if show_all_pattern.search(message_lower):
        # Parse hours if specified
        hours = 24 * 7  # Default to last 7 days for "all apps" queries
        hour_match = re.search(r'last\s+(\d+)\s+hour', message_lower)
        day_match = re.search(r'last\s+(\d+)\s+day', message_lower)
        week_match = re.search(r'last\s+(\d+)\s+week', message_lower)
        if hour_match:
            hours = int(hour_match.group(1))
        elif day_match:
            hours = int(day_match.group(1)) * 24
        elif week_match:
            hours = int(week_match.group(1)) * 24 * 7
        elif any(x in message_lower for x in ["today", "ran today", "executed today"]):
            hours = 24
        
        return {
            "intent": "show_recent_apps",
            "params": {"hours": hours}
        }
    
    # Fallback: check for specific recent app triggers (for queries without "show/list all")
    recent_triggers = ["ran today", "executed today", "today's apps", "applications today",
                      "show today", "recent apps", "recent applications", "recently ran"]
    if any(trigger in message_lower for trigger in recent_triggers):
        # Parse hours if specified
        hours = 24  # default to today
        hour_match = re.search(r'last\s+(\d+)\s+hour', message_lower)
        day_match = re.search(r'last\s+(\d+)\s+day', message_lower)
        week_match = re.search(r'last\s+(\d+)\s+week', message_lower)
        if hour_match:
            hours = int(hour_match.group(1))
        elif day_match:
            hours = int(day_match.group(1)) * 24
        elif week_match:
            hours = int(week_match.group(1)) * 24 * 7
        
        return {
            "intent": "show_recent_apps",
            "params": {"hours": hours}
        }
    
    # INTENT 4: show_driver_heavy
    driver_triggers = ["driver heavy", "driver intensive", "high driver", 
                      "driver cpu", "driver memory", "driver jobs",
                      "driver overhead", "driver bottleneck"]
    if any(trigger in message_lower for trigger in driver_triggers):
        return {
            "intent": "show_driver_heavy",
            "params": {"metric": "driver"}
        }
    
    # INTENT 5: show_memory_intensive
    memory_triggers = ["memory intensive", "memory issues", "oom", "out of memory",
                      "memory spill", "high memory", "executor memory"]
    if any(trigger in message_lower for trigger in memory_triggers):
        return {
            "intent": "show_memory_intensive",
            "params": {"metric": "memory"}
        }
    
    # INTENT 6: show_shuffle_issues
    shuffle_triggers = ["shuffle spill", "shuffle issues", "bad shuffle",
                       "shuffle heavy", "high shuffle", "shuffle problems"]
    if any(trigger in message_lower for trigger in shuffle_triggers):
        return {
            "intent": "show_shuffle_issues",
            "params": {"metric": "shuffle"}
        }
    
    # INTENT 7: show_best_practice_apps
    best_triggers = ["best practices", "follow best", "healthy apps", 
                    "well optimized", "good apps", "no issues",
                    "clean apps", "compliant apps", "green apps"]
    if any(trigger in message_lower for trigger in best_triggers):
        return {
            "intent": "show_best_practice_apps",
            "params": {"min_score": 80}
        }
    
    # INTENT 8: analyze_skew
    skew_triggers = ["skew", "imbalance", "task imbalance", "shuffle imbalance",
                    "data skew", "partition skew", "skewed data", "skewed partitions",
                    "uneven distribution", "straggler", "stragglers"]
    if any(trigger in message_lower for trigger in skew_triggers):
        # Check if it's about a specific application
        app_id = extract_application_id(message)
        if app_id:
            return {
                "intent": "analyze_skew",
                "params": {"application_id": app_id}
            }
    
    # INTENT 9: analyze_scaling
    # Use regex for better matching of executor/resource scaling questions
    scaling_patterns = [
        r'\badd(?:ing)?\s+(?:more\s+)?executors?\b',  # add executors, adding executors, add more executors
        r'\bmore\s+executors?\b',  # more executors
        r'\bscal(?:e|ing)\s+(?:up|down|out)?\b',  # scale, scaling, scale up/down/out
        r'\bwill\s+scaling\s+help\b',  # will scaling help
        r'\bshould\s+(?:i|we)\s+scale\b',  # should i scale
        r'\b(?:add(?:ing)?|more|fewer|less)\s+(?:resources?|nodes?|executors?)\b',  # resource changes
        r'\b(?:increas(?:e|ing)|reduc(?:e|ing)|decreas(?:e|ing))\s+(?:executors?|nodes?|resources?)\b',  # increase/increasing/decrease/decreasing resources
        r'\bexecutor\s+count\b',  # executor count
        r'\bwill\s+(?:more|additional|extra|fewer|less)\s+executors?\b',  # will more/fewer executors
        r'\bwill\s+(?:increas(?:e|ing)|add(?:ing)?)\s+executors?\b',  # will increasing/adding executors
        r'\b(?:improve|help|boost|enhance)\s+performance\b.*\b(?:executor|resource|scal)',  # Performance improvement with scaling context
    ]
    
    # Check if message matches scaling patterns AND contains app ID
    if any(re.search(pattern, message_lower) for pattern in scaling_patterns):
        app_id = extract_application_id(message)
        if app_id:
            return {
                "intent": "analyze_scaling",
                "params": {"application_id": app_id}
            }
    
    # INTENT 10: general_chat (default)
    return {
        "intent": "general_chat",
        "params": {}
    }


# ============================================================================
# RESPONSE FORMATTERS
# ============================================================================

def format_app_analysis(result: Dict[str, Any]) -> str:
    """
    Format application analysis results with clean box/card layouts.
    Grouped by source: KUSTO → RAG → LLM
    """
    app_id = result.get("application_id", "unknown")
    health = result.get("overall_health", "unknown").upper()
    summary = result.get("summary", "No summary available")
    recs = result.get("validated_recommendations", [])
    
    # Group recommendations by source
    # Check both the source field AND the metadata marker (in case Judge changed source tag)
    kusto_recs = [r for r in recs if r.get("source") == "kusto" or r.get("metadata", {}).get("from_kusto")]
    rag_recs = [r for r in recs if r.get("source") == "rag" and not r.get("metadata", {}).get("from_kusto")]
    llm_recs = [r for r in recs if r.get("source") == "llm" and not r.get("metadata", {}).get("from_kusto")]
    
    # Count by severity
    critical_count = sum(1 for r in recs if r.get("priority", 999) <= 9)
    warning_count = sum(1 for r in recs if 10 <= r.get("priority", 999) <= 29)
    info_count = sum(1 for r in recs if r.get("priority", 999) >= 30)
    
    # Health badge
    health_badge = {
        "CRITICAL": "🔴",
        "WARNING": "🟡",
        "HEALTHY": "🟢",
        "EXCELLENT": "🌟"
    }.get(health, "⚪")
    
    # Build output with styled header
    md = f"""
<div style="background: #0D1318; border: 2px solid #00D4FF; border-radius: 4px; padding: 16px 20px; margin-bottom: 20px;">
  <h1 style="margin: 0 0 8px 0; color: #E8F4F8; font-size: 20px;">
    {health_badge} Application Analysis: <code style="color: #00D4FF;">{app_id}</code>
  </h1>
  <div style="color: #5A7A8A; font-size: 13px; line-height: 1.6;">
    <strong style="color: #E8F4F8;">Overall Health:</strong> {health}<br>
    <strong style="color: #E8F4F8;">Summary:</strong> {summary}<br>
    <strong style="color: #E8F4F8;">Total Recommendations:</strong> {len(recs)} 
    (<span style="color: #FF5252;">🔴 {critical_count} Critical</span> | 
     <span style="color: #FFB300;">🟡 {warning_count} Warning</span> | 
     <span style="color: #3FB950;">🟢 {info_count} Info</span>)
  </div>
</div>

"""
    
    # ========================================
    # SECTION 1: KUSTO RECOMMENDATIONS (TIER 1)
    # ========================================
    md += """
<div style="margin-top: 24px;">
  <div style="background: linear-gradient(90deg, #0099CC, #00D4FF); height: 3px; margin-bottom: 12px;"></div>
  <h2 style="color: #00D4FF; margin: 0 0 8px 0; font-size: 18px;">📊 TIER 1 — Kusto Telemetry (Ground Truth)</h2>
  <p style="color: #5A7A8A; font-size: 12px; margin: 0 0 16px 0;"><strong>Source:</strong> sparklens_recommedations + fabric_recommedations tables | <strong>Trust:</strong> ✅ VERIFIED</p>
</div>

"""
    
    if kusto_recs:
        for i, rec in enumerate(kusto_recs, 1):
            text = rec.get("recommendation", rec.get("text", "No recommendation text"))
            
            # Preserve formatting from Kusto - it often has emojis and structure
            # Convert newlines to HTML breaks for proper display
            text_html = text.replace('\n', '<br>')
            
            # Detect priority/severity from text content or metadata
            priority = rec.get("priority", 999)
            metadata = rec.get("metadata", {})
            severity = metadata.get("severity", "").upper()
            
            # Determine colors based on severity or priority
            if severity in ["CRITICAL", "HIGH"] or priority <= 9:
                border_color = "#FF5252"
                bg_color = "#1A0F0F"
            elif severity in ["MEDIUM", "WARNING"] or priority <= 29:
                border_color = "#FFB300"
                bg_color = "#1A1610"
            else:
                border_color = "#3FB950"
                bg_color = "#0F1A14"
            
            md += f"""
<div style="background: {bg_color}; border-left: 4px solid {border_color}; border-radius: 4px; padding: 14px 16px; margin-bottom: 12px; font-family: 'Segoe UI', 'IBM Plex Mono', monospace;">
  <div style="color: #E8F4F8; font-size: 13px; line-height: 1.7; white-space: pre-wrap;">
{text_html}
  </div>
</div>

"""
    else:
        # Only show "no data" message if we genuinely have no Kusto recommendations
        # Check if recommendations came from Kusto but were relabeled by judge
        has_kusto_data = any(r.get("metadata", {}).get("from_kusto") or "kusto" in str(r.get("metadata", {})) for r in recs)
        
        if not has_kusto_data and len(recs) == 0:
            md += """
<div style="background: #0D1318; border: 1px dashed #1C2A35; border-radius: 4px; padding: 14px 16px; margin-bottom: 12px;">
  <p style="color: #5A7A8A; font-style: italic; margin: 0;">
    No Spark Advisor or Fabric recommendations found in Kusto for this application.<br>
    <span style="font-size: 11px; color: #3A5060;">
      This could mean: (1) App hasn't been analyzed yet, 
      (2) App ID not found in recommendation tables, or 
      (3) No performance issues detected.
    </span>
  </p>
</div>

"""
        # If we have recommendations but source tag changed, don't show confusing message
    
    # ========================================
    # SECTION 2: RAG DOCUMENTATION (TIER 2)
    # ========================================
    md += """
<div style="margin-top: 32px;">
  <div style="background: linear-gradient(90deg, #3FB950, #00E676); height: 3px; margin-bottom: 12px;"></div>
  <h2 style="color: #3FB950; margin: 0 0 8px 0; font-size: 18px;">📚 TIER 2 — Documentation & Best Practices</h2>
  <p style="color: #5A7A8A; font-size: 12px; margin: 0 0 16px 0;"><strong>Source:</strong> Microsoft Fabric Spark docs via RAG | <strong>Trust:</strong> 📖 OFFICIAL</p>
</div>

"""
    
    if rag_recs:
        for i, rec in enumerate(rag_recs, 1):
            text = rec.get("recommendation", rec.get("text", ""))
            metadata = rec.get("metadata", {})
            doc_title = metadata.get("title", f"Documentation #{i}")
            source_url = metadata.get("source_url", "")
            
            # Handle empty content
            if not text or len(text.strip()) < 10:
                text = "<em style='color: #5A7A8A;'>Content not available - see documentation link below</em>"
                truncated = False
            else:
                # Truncate long RAG responses
                truncated = False
                if len(text) > 800:
                    text = text[:800]
                    truncated = True
            
            # Build doc link if source URL exists
            doc_link = ""
            if source_url:
                link_text = "📄 Read full documentation →"
                doc_link = f"""<div style="margin-top: 12px; padding-top: 10px; border-top: 1px solid #1C2A35;">
    <a href="{source_url}" target="_blank" style="color: #00D4FF; text-decoration: none; font-size: 12px;">
      {link_text}
    </a>
  </div>"""
            
            md += f"""
<div style="background: #0D1318; border: 1px solid #3FB950; border-left: 3px solid #3FB950; border-radius: 4px; padding: 16px 18px; margin-bottom: 14px;">
  <div style="color: #3FB950; font-weight: 600; font-size: 14px; margin-bottom: 10px;">
    📄 {doc_title}
  </div>
  <div style="color: #C9D1D9; font-size: 13px; line-height: 1.7;">
    {text}{' <em style="color: #5A7A8A;">...</em>' if truncated else ''}
  </div>
  {doc_link}
</div>

"""
    else:
        md += """
<div style="background: #0D1318; border: 1px dashed #1C2A35; border-radius: 4px; padding: 14px 16px; margin-bottom: 12px;">
  <p style="color: #5A7A8A; font-style: italic; margin: 0;">No relevant documentation found for this query.</p>
</div>

"""
    
    # ========================================
    # SECTION 3: LLM RECOMMENDATIONS (TIER 3)
    # ========================================
    if llm_recs:
        md += """
<div style="margin-top: 32px;">
  <div style="background: linear-gradient(90deg, #B388FF, #FF5252); height: 3px; margin-bottom: 12px;"></div>
  <h2 style="color: #B388FF; margin: 0 0 8px 0; font-size: 18px;">🤖 TIER 3 — AI Analysis (Validate Before Use)</h2>
</div>

<div style="background: #1A0F14; border: 2px dashed #B388FF; border-radius: 4px; padding: 16px 18px; margin-bottom: 16px;">
  <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
    <span style="font-size: 20px;">⚠️</span>
    <strong style="color: #FFB300; font-size: 14px; letter-spacing: 0.3px;">AI GENERATED — NOT FROM YOUR DATA</strong>
  </div>
  <div style="color: #5A7A8A; font-size: 12px; line-height: 1.6;">
    <strong>Source:</strong> LLM training knowledge | <strong>Confidence:</strong> MEDIUM<br>
    <strong>Action Required:</strong> Validate these suggestions against your actual workload before applying
  </div>
</div>

"""
        
        for i, rec in enumerate(llm_recs, 1):
            text = rec.get("recommendation", rec.get("text", "No recommendation text"))
            
            # Convert plain text to structured markdown
            import re
            
            # Split into paragraphs
            paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
            
            # Format as structured content
            formatted_body = ""
            for para in paragraphs:
                # Check if it's a bullet point or list item
                if para.startswith('-') or para.startswith('•') or re.match(r'^\d+\.', para):
                    formatted_body += f"\n{para}\n"
                # Check if it's a question or section header (ends with ? or :)
                elif para.endswith('?') or para.endswith(':'):
                    formatted_body += f"\n**{para}**\n"
                # Check if it contains key terms that should be highlighted
                elif any(term in para.lower() for term in ['task distribution', 'executor utilization', 'data skew', 'executor cpu', 'memory', 'pool']):
                    # Extract the term and make it bold
                    formatted_body += f"\n- {para}\n"
                else:
                    formatted_body += f"\n{para}\n"
            
            # Clean up excessive newlines
            formatted_body = re.sub(r'\n{3,}', '\n\n', formatted_body)
            
            # Extract title (first sentence or first 100 chars)
            first_sentence_match = re.match(r'^([^.!?]+[.!?])', text)
            if first_sentence_match:
                title = first_sentence_match.group(1).strip()
            else:
                lines = text.split('\n')
                title = lines[0][:100] if lines[0] else "LLM Recommendation"
            
            # Remove numbering from title
            title = re.sub(r'^\d+\.\s*', '', title)
            
            md += f"""
<div style="background: #0D1318; border-left: 3px solid #B388FF; border-radius: 3px; padding: 14px 16px; margin-bottom: 12px;">
  <div style="color: #B388FF; font-weight: 600; font-size: 13px; margin-bottom: 10px;">
    🤖 {title}
  </div>
  <div style="color: #C9D1D9; font-size: 12px; line-height: 1.8;">
    {formatted_body.strip()}
  </div>
</div>

"""
    else:
        # Empty state for LLM section
        md += """
<div style="background: #0D1318; border: 1px dashed #1C2A35; border-radius: 4px; padding: 14px 16px; margin-bottom: 12px;">
  <p style="color: #5A7A8A; font-style: italic; margin: 0;">No AI-generated recommendations needed — sufficient verified data available.</p>
</div>

"""
    
    # No text-based feedback request - will use action buttons instead
    return md


def format_app_table(apps: List[Dict[str, Any]], title: str, columns: List[str]) -> str:
    """
    Format applications list as markdown table with trend indicators.
    """
    if not apps:
        return f"### {title}\n\nNo applications found."
    
    md = f"### {title}\n\n"
    
    # Build table header
    header = "| " + " | ".join(columns) + " | Status |\n"
    separator = "|" + "|".join([" --- " for _ in columns]) + "| --- |\n"
    
    md += header + separator
    
    # Add rows
    for app in apps[:20]:  # Limit to 20 rows
        row = "| "
        for col in columns:
            value = app.get(col, "N/A")
            
            # Format large numbers
            if isinstance(value, (int, float)) and value > 1000:
                if value > 1_000_000_000:  # GB
                    value = f"{value / 1_000_000_000:.2f} GB"
                elif value > 1_000_000:  # MB
                    value = f"{value / 1_000_000:.2f} MB"
                else:
                    value = f"{value:,.0f}"
            elif isinstance(value, float):
                value = f"{value:.2f}"
            
            row += f"{value} | "
        
        # Add status indicator
        # Try to infer status from health score or violation count
        score = app.get("HealthScore", app.get("health_score", None))
        if score is not None:
            if score >= 80:
                status = "🟢"
            elif score >= 40:
                status = "🟡"
            else:
                status = "🔴"
        else:
            violations = app.get("ViolationCount", app.get("violation_count", 0))
            if violations == 0:
                status = "🟢"
            elif violations < 5:
                status = "🟡"
            else:
                status = "🔴"
        
        row += f"{status} |\n"
        md += row
    
    if len(apps) > 20:
        md += f"\n*Showing top 20 of {len(apps)} applications*\n"
    
    return md


def format_driver_heavy_table(apps: List[Dict[str, Any]]) -> str:
    """
    Format driver-heavy applications as markdown table.
    """
    if not apps:
        return "### 🖥️ Driver-Heavy Applications\n\nNo driver-heavy applications found."
    
    md = "### 🖥️ Driver-Heavy Applications\n\n"
    md += "| App ID | Application Name | Driver Time % | Duration | Alert |\n"
    md += "| --- | --- | --- | --- | --- |\n"
    
    for app in apps[:15]:
        app_id = app.get("app_id", "unknown")
        app_name = app.get("app_name", "Unknown")[:50]  # Truncate long names
        driver_pct = float(app.get("driver_time_pct", 0))
        duration = float(app.get("duration", 0))
        
        # Format duration as minutes:seconds
        duration_min = int(duration // 60)
        duration_sec = int(duration % 60)
        duration_str = f"{duration_min}m {duration_sec}s"
        
        # Alert if critical (>90% driver time)
        alert = "🚨 CRITICAL" if driver_pct > 90 else "⚠️ HIGH"
        
        md += f"| `{app_id}` | {app_name} | {driver_pct:.1f}% | {duration_str} | {alert} |\n"
    
    if len(apps) > 15:
        md += f"\n*Showing top 15 of {len(apps)} applications*\n"
    
    md += "\n💡 **Tip:** Driver-heavy workloads (>80% driver time) waste executor resources.\n"
    md += "   - **Solution:** Scale DOWN to single-node cluster or reduce executor count\n"
    md += "   - **Root Cause:** Too much driver-side processing (collect, broadcast, etc.)\n"
    
    return md



def format_memory_table(apps: List[Dict[str, Any]]) -> str:
    """
    Format memory-intensive applications as markdown table.
    """
    if not apps:
        return "### 💾 Memory-Intensive Applications\n\nNo memory-intensive applications found."
    
    md = "### 💾 Memory-Intensive Applications\n\n"
    md += "| App ID | Application Name | GC Overhead % | Duration | Risk |\n"
    md += "| --- | --- | --- | --- | --- |\n"
    
    for app in apps[:15]:
        app_id = app.get("app_id", "unknown")
        app_name = app.get("app_name", "Unknown")[:50]  # Truncate long names
        gc_overhead = float(app.get("gc_overhead_pct", 0))
        duration = float(app.get("duration", 0))
        
        # Format duration as minutes:seconds
        duration_min = int(duration // 60)
        duration_sec = int(duration % 60)
        duration_str = f"{duration_min}m {duration_sec}s"
        
        # Risk level based on GC overhead
        risk = "🔴 CRITICAL" if gc_overhead > 40 else "🟡 HIGH" if gc_overhead > 25 else "⚠️ MEDIUM"
        
        md += f"| `{app_id}` | {app_name} | {gc_overhead:.1f}% | {duration_str} | {risk} |\n"
    
    if len(apps) > 15:
        md += f"\n*Showing top 15 of {len(apps)} applications*\n"
    
    md += "\n💡 **Tip:** High GC overhead (>20%) indicates memory pressure.\n"
    md += "   - **Solution:** Increase `spark.executor.memory` by 50-100%\n"
    md += "   - **Also Check:** Cache usage - call `.unpersist()` when data no longer needed\n"
    
    return md


def format_recent_apps_table(apps: List[Dict[str, Any]], time_desc: str) -> str:
    """
    Format recent applications as markdown table grouped by health status.
    """
    if not apps:
        return f"### 📊 Recent Applications ({time_desc})\n\nNo applications found {time_desc}."
    
    # Group by health status
    critical = [app for app in apps if app.get("health_status") == "CRITICAL"]
    warning = [app for app in apps if app.get("health_status") == "WARNING"]
    healthy = [app for app in apps if app.get("health_status") == "HEALTHY"]
    unknown = [app for app in apps if app.get("health_status") == "UNKNOWN"]
    
    md = f"### 📊 Applications Executed {time_desc.title()}\n\n"
    md += f"**Total:** {len(apps)} applications | "
    md += f"🔴 {len(critical)} Critical | "
    md += f"🟡 {len(warning)} Warning | "
    md += f"✅ {len(healthy)} Healthy | "
    md += f"❓ {len(unknown)} Unknown\n\n"
    
    def format_section(title, emoji, apps_list):
        if not apps_list:
            return ""
        section = f"#### {emoji} {title} ({len(apps_list)})\n\n"
        section += "| App ID | Application Name | Duration | Executor Eff | GC Overhead |\n"
        section += "| --- | --- | --- | --- | --- |\n"
        
        for app in apps_list[:10]:  # Limit to 10 per section
            app_id = app.get("app_id", "unknown")
            app_name = app.get("app_name", "Unknown")[:40]
            duration = float(app.get("duration_min", 0))
            eff = float(app.get("executor_efficiency", 0))
            gc = float(app.get("gc_overhead_pct", 0))
            
            section += f"| `{app_id}` | {app_name} | {duration:.1f} min | {eff:.1%} | {gc:.1f}% |\n"
        
        if len(apps_list) > 10:
            section += f"\n*Showing top 10 of {len(apps_list)} {title.lower()} applications*\n"
        section += "\n"
        return section
    
    # Add sections in priority order
    if critical:
        md += format_section("Critical Issues", "🔴", critical)
    if warning:
        md += format_section("Warnings", "🟡", warning)
    if healthy:
        md += format_section("Healthy", "✅", healthy)
    if unknown:
        md += format_section("Unknown Status", "❓", unknown)
    
    md += "💡 **Tip:** Click on any `app_id` and ask me to analyze it!\n"
    
    return md


def format_healthy_apps_table(apps: List[Dict[str, Any]]) -> str:
    """
    Format healthy applications as markdown table with medals.
    """
    if not apps:
        return "### ✅ Healthy Applications\n\nNo healthy applications found."
    
    md = "### ✅ Applications Following Best Practices\n\n"
    md += "| Rank | App ID | Health Score | Jobs | Violations | Grade |\n"
    md += "| --- | --- | --- | --- | --- | --- |\n"
    
    for i, app in enumerate(apps[:20], 1):
        app_id = app.get("ApplicationId", "unknown")
        health_score = app.get("HealthScore", 0)
        job_count = app.get("TotalJobs", 0)
        violations = app.get("ViolationCount", 0)
        grade = app.get("Grade", "C")
        
        # Medal for top 3
        rank = f"{i}"
        if i == 1:
            rank = "🥇"
        elif i == 2:
            rank = "🥈"
        elif i == 3:
            rank = "🥉"
        
        md += f"| {rank} | `{app_id}` | {health_score:.0f} | {job_count} | {violations} | **{grade}** |\n"
    
    if len(apps) > 20:
        md += f"\n*Showing top 20 of {len(apps)} applications*\n"
    
    md += "\n💡 **Grading:** A = 90-100, B = 80-89 • Health Score = 100 - (violations × 5) - (critical × 20)\n"
    
    return md


def format_skew_analysis(result: Dict[str, Any]) -> str:
    """
    Format skew analysis results with stage details and LLM recommendations.
    """
    app_id = result.get("application_id", "unknown")
    status = result.get("status", "unknown")
    
    # Handle error or no data cases
    if status == "error":
        error = result.get("error", "Unknown error")
        return f"""
### ⚠️ Skew Analysis Failed

**Application:** `{app_id}`

**Error:** {error}

Please verify the application ID exists and has stage summary data in the database.
"""
    
    if status == "no_data":
        message = result.get("message", "No data available")
        return f"""
### 📊 Skew Analysis: {app_id}

{message}

**Note:** This application may not have detailed stage telemetry, or it completed too quickly to generate stage metrics.
"""
    
    # Build successful analysis output
    stages_analyzed = result.get("stages_analyzed", 0)
    stages_with_skew = result.get("stages_with_skew", 0)
    problematic_stages = result.get("problematic_stages", [])
    llm_analysis = result.get("llm_analysis", "")
    
    md = f"""
<div style="background: #0D1318; border: 2px solid #FFB300; border-radius: 4px; padding: 16px 20px; margin-bottom: 20px;">
  <h1 style="margin: 0 0 8px 0; color: #E8F4F8; font-size: 20px;">
    🔍 Skew Analysis: <code style="color: #FFB300;">{app_id}</code>
  </h1>
  <div style="color: #5A7A8A; font-size: 13px; line-height: 1.6;">
    <strong style="color: #E8F4F8;">Stages Analyzed:</strong> {stages_analyzed}<br>
    <strong style="color: #E8F4F8;">Stages with Skew:</strong> {stages_with_skew} 
    ({round(100 * stages_with_skew / stages_analyzed if stages_analyzed > 0 else 0, 1)}%)<br>
    <strong style="color: #E8F4F8;">Source:</strong> Stage telemetry + AI analysis
  </div>
</div>

"""
    
    # Show problematic stages summary table
    if problematic_stages:
        md += """
<div style="margin-top: 24px;">
  <div style="background: linear-gradient(90deg, #FF5252, #FFB300); height: 3px; margin-bottom: 12px;"></div>
  <h2 style="color: #FFB300; margin: 0 0 8px 0; font-size: 18px;">⚠️ Problematic Stages Summary</h2>
</div>

| Stage ID | Task Imbalance | Shuffle Imbalance | Duration (sec) | Severity |
| --- | --- | --- | --- | --- |
"""
        
        for stage in problematic_stages[:10]:
            stage_id = stage.get("stage_id", "?")
            task_imb = stage.get("task_imbalance", 0)
            shuffle_imb = stage.get("shuffle_imbalance", 0)
            duration = stage.get("stage_duration_sec", 0)
            severity = stage.get("severity", "UNKNOWN")
            
            severity_icon = {
                "CRITICAL": "🔴",
                "HIGH": "🟠",
                "MEDIUM": "🟡",
                "LOW": "⚫"
            }.get(severity, "⚪")
            
            md += f"| {stage_id} | {task_imb}x | {shuffle_imb}x | {duration:.1f} | {severity_icon} {severity} |\n"
        
        if len(problematic_stages) > 10:
            md += f"\n*Showing top 10 of {len(problematic_stages)} stages with skew*\n\n"
        else:
            md += "\n"
    else:
        md += """
<div style="background: #0F1A14; border-left: 4px solid #3FB950; border-radius: 4px; padding: 14px 16px; margin-bottom: 12px;">
  <strong style="color: #3FB950; font-size: 14px;">✅ No Significant Skew Detected</strong>
  <p style="color: #C9D1D9; font-size: 13px; margin: 8px 0 0 0;">
    All stages show balanced task and shuffle distribution (imbalance ratio < 2x).
  </p>
</div>

"""
    
    # Show LLM detailed analysis
    if llm_analysis:
        md += """
<div style="margin-top: 32px;">
  <div style="background: linear-gradient(90deg, #B388FF, #00D4FF); height: 3px; margin-bottom: 12px;"></div>
  <h2 style="color: #B388FF; margin: 0 0 8px 0; font-size: 18px;">🤖 Detailed Analysis & Recommendations</h2>
</div>

"""
        
        # Render LLM analysis as markdown (no monospace/pre-wrap wrapper)
        md += f"\n{llm_analysis}\n\n"
    
    return md


def format_scaling_analysis(result: Dict[str, Any]) -> str:
    """
    Format scaling impact analysis results with predictions and recommendations.
    """
    app_id = result.get("application_id", "unknown")
    status = result.get("status", "unknown")
    
    # Handle error case
    if status == "error":
        error = result.get("error", "Unknown error")
        return f"""
### ⚠️ Scaling Analysis Failed

**Application:** `{app_id}`

**Error:** {error}

Please verify the application ID exists and has metrics data in the database.
"""
    
    # Build successful analysis output
    recommendation = result.get("recommendation", "UNKNOWN")
    llm_analysis = result.get("llm_analysis", "")
    current_metrics = result.get("current_metrics", {})
    predictions_count = result.get("predictions_count", 0)
    existing_recs_count = result.get("existing_recommendations_count", 0)
    
    duration = current_metrics.get("duration_sec", 0)
    executors = current_metrics.get("executor_count", 0)
    driver_time = current_metrics.get("driver_time_pct", 0)
    efficiency = current_metrics.get("executor_efficiency", 0)
    
    # Determine recommendation badge
    rec_badges = {
        "SCALE_UP": ("🚀", "SCALE UP", "#3FB950"),
        "SCALE_DOWN": ("⬇️", "SCALE DOWN", "#FFB300"),
        "DON'T_SCALE": ("🛑", "DON'T SCALE", "#FF5252"),
        "OPTIMIZE_FIRST": ("🔧", "OPTIMIZE FIRST", "#00D4FF"),
        "ANALYZE_NEEDED": ("⚠️", "MORE DATA NEEDED", "#B388FF")
    }
    
    badge_emoji, badge_text, badge_color = rec_badges.get(recommendation, ("❓", "UNKNOWN", "#5A7A8A"))
    
    md = f"""
<div style="background: #0D1318; border: 2px solid {badge_color}; border-radius: 4px; padding: 16px 20px; margin-bottom: 20px;">
  <h1 style="margin: 0 0 8px 0; color: #E8F4F8; font-size: 20px;">
    {badge_emoji} Scaling Analysis: <code style="color: {badge_color};">{app_id}</code>
  </h1>
  <div style="color: #5A7A8A; font-size: 13px; line-height: 1.6;">
    <strong style="color: #E8F4F8;">Recommendation:</strong> <span style="color: {badge_color}; font-weight: 600;">{badge_text}</span><br>
    <strong style="color: #E8F4F8;">Current Duration:</strong> {duration:.1f}s ({(duration/60):.1f} min)<br>
    <strong style="color: #E8F4F8;">Current Executors:</strong> {executors}<br>
    <strong style="color: #E8F4F8;">Predictions Available:</strong> {predictions_count} data points<br>
    <strong style="color: #E8F4F8;">Source:</strong> SparkLens predictions + application metrics
  </div>
</div>

"""
    
    # Show current metrics summary
    md += """
<div style="margin-top: 24px;">
  <div style="background: linear-gradient(90deg, #FFB300, #FF5252); height: 3px; margin-bottom: 12px;"></div>
  <h2 style="color: #FFB300; margin: 0 0 8px 0; font-size: 18px;">📊 Current Performance Metrics</h2>
</div>

"""
    
    # Metrics cards
    md += f"""
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 24px;">
  <div style="background: #0D1318; border: 1px solid #243040; border-radius: 4px; padding: 14px;">
    <div style="color: #5A7A8A; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">Duration</div>
    <div style="color: #E8F4F8; font-size: 20px; font-weight: 600; margin-top: 4px;">{duration:.1f}s</div>
  </div>
  <div style="background: #0D1318; border: 1px solid #243040; border-radius: 4px; padding: 14px;">
    <div style="color: #5A7A8A; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">Executors</div>
    <div style="color: #E8F4F8; font-size: 20px; font-weight: 600; margin-top: 4px;">{executors}</div>
  </div>
  <div style="background: #0D1318; border: 1px solid #243040; border-radius: 4px; padding: 14px;">
    <div style="color: #5A7A8A; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">Executor Efficiency</div>
    <div style="color: #E8F4F8; font-size: 20px; font-weight: 600; margin-top: 4px;">{efficiency:.1f}%</div>
  </div>
  <div style="background: #0D1318; border: 1px solid #243040; border-radius: 4px; padding: 14px;">
    <div style="color: #5A7A8A; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">Driver Time %</div>
    <div style="color: #E8F4F8; font-size: 20px; font-weight: 600; margin-top: 4px;">{driver_time:.1f}%</div>
  </div>
</div>

"""
    
    # Show LLM detailed analysis with prediction tables
    if llm_analysis:
        md += """
<div style="margin-top: 32px;">
  <div style="background: linear-gradient(90deg, #B388FF, #00D4FF); height: 3px; margin-bottom: 12px;"></div>
  <h2 style="color: #B388FF; margin: 0 0 8px 0; font-size: 18px;">📈 Detailed Scaling Analysis</h2>
</div>

"""
        
        # Render LLM analysis as markdown (no monospace/pre-wrap wrapper)
        md += f"\n{llm_analysis}\n\n"
    
    return md


# ============================================================================
# SESSION STATE MANAGEMENT
# ============================================================================

def initialize_session_state():
    """Initialize session state variables."""
    state = {
        "last_analyzed_app": None,
        "total_recommendations": 0,
        "sources_used": {
            "kusto": False,
            "rag": False, 
            "llm": False
        },
        "apps_analyzed_count": 0,
        "session_start": datetime.now()
    }
    cl.user_session.set("state", state)
    return state


def update_session_state(result: Dict[str, Any], intent: str, app_count: int = 0, query_type: str = None):
    """Update session state after processing a request."""
    state = cl.user_session.get("state", initialize_session_state())
    
    if intent == "analyze_app":
        state["last_analyzed_app"] = result.get("application_id")
        state["apps_analyzed_count"] += 1
        
        recs = result.get("validated_recommendations", [])
        state["total_recommendations"] += len(recs)
        
        # Update sources used
        sources = result.get("source_counts", {})
        if sources.get("kusto", 0) > 0:
            state["sources_used"]["kusto"] = True
        if sources.get("rag", 0) > 0:
            state["sources_used"]["rag"] = True
        if sources.get("llm", 0) > 0:
            state["sources_used"]["llm"] = True
    
    elif intent in ["show_driver_heavy", "show_memory_intensive", "show_shuffle_issues"]:
        # Pattern-based queries
        pattern_names = {
            "show_driver_heavy": "driver-heavy apps",
            "show_memory_intensive": "memory-intensive apps",
            "show_shuffle_issues": "shuffle-heavy apps"
        }
        state["last_analyzed_app"] = pattern_names.get(intent, "query")
        state["apps_analyzed_count"] += app_count
        state["sources_used"]["kusto"] = True
    
    elif intent == "analyze_skew":
        # Skew analysis uses Kusto stage data + LLM analysis
        state["last_analyzed_app"] = "skew analysis"
        state["total_recommendations"] += app_count  # Count of problematic stages
        state["sources_used"]["kusto"] = True
        state["sources_used"]["llm"] = True
    
    elif intent == "analyze_scaling":
        # Scaling analysis uses Kusto predictions + metrics + LLM analysis
        state["last_analyzed_app"] = "scaling analysis"
        state["total_recommendations"] += 1
        state["sources_used"]["kusto"] = True
        state["sources_used"]["llm"] = True
    
    elif intent == "show_bad_apps":
        state["last_analyzed_app"] = "bad practice apps"
        state["apps_analyzed_count"] += app_count
        state["sources_used"]["kusto"] = True
    
    elif intent == "show_recent_apps":
        state["last_analyzed_app"] = "recent apps"
        state["apps_analyzed_count"] += app_count
        state["sources_used"]["kusto"] = True
    
    elif intent == "show_best_practice_apps":
        state["last_analyzed_app"] = "healthy apps"
        state["apps_analyzed_count"] += app_count
        state["sources_used"]["kusto"] = True
    
    elif intent == "general_chat" and query_type == "dynamic_query":
        # Dynamic KQL queries
        state["last_analyzed_app"] = "dynamic query"
        state["apps_analyzed_count"] += app_count
        state["sources_used"]["kusto"] = True
    
    elif intent == "general_chat" and query_type == "rag":
        # RAG documentation queries
        state["sources_used"]["rag"] = True
        state["sources_used"]["llm"] = True
    
    elif intent == "general_chat":
        # Pure LLM conversations
        state["sources_used"]["llm"] = True
    
    cl.user_session.set("state", state)
    return state


async def send_sidebar_update():
    """Send sidebar with session statistics."""
    state = cl.user_session.get("state", initialize_session_state())
    
    duration = datetime.now() - state["session_start"]
    minutes = int(duration.total_seconds() / 60)
    
    sidebar_text = f"""
### 📊 Session Summary
**Last App:** {state['last_analyzed_app'] or 'None yet'}  
**Apps Analyzed:** {state['apps_analyzed_count']}  
**Total Recommendations:** {state['total_recommendations']}

### 🔌 Sources Used
{'✅' if state['sources_used']['kusto'] else '⬜'} Kusto/Eventhouse  
{'✅' if state['sources_used']['rag'] else '⬜'} RAG Docs  
{'✅' if state['sources_used']['llm'] else '⬜'} LLM Knowledge

### ⏱️ Session
Started: {state['session_start'].strftime('%H:%M:%S')}  
Duration: {minutes} min
"""
    
    await cl.Message(
        content=sidebar_text,
        author="📊 Stats"
    ).send()


# ============================================================================
# LOADING MESSAGES
# ============================================================================

def get_loading_message(intent: str, params: Dict[str, Any]) -> str:
    """Get contextual loading message based on intent."""
    
    # Special handling for show_recent_apps to show context-aware message
    if intent == "show_recent_apps":
        hours = params.get('hours', 24)
        if hours == 24:
            time_desc = "today"
        elif hours == 24 * 7:
            time_desc = "from the last 7 days"
        elif hours < 24:
            time_desc = f"from the last {hours} hours"
        elif hours % 24 == 0:
            days = hours // 24
            time_desc = f"from the last {days} days"
        else:
            time_desc = f"from the last {hours} hours"
        
        return f"📊 Finding all applications {time_desc}...\n\n⏳ Querying Kusto database..."
    
    messages = {
        "analyze_app": f"🔍 Analyzing application `{params.get('application_id', 'unknown')}`...\n\n"
                      "⏳ Checking Kusto telemetry, searching documentation, consulting LLM...",
        
        "analyze_skew": f"🔍 Analyzing task and shuffle skew for `{params.get('application_id', 'unknown')}`...\n\n"
                       "⏳ Fetching stage summary data and detecting imbalance patterns...",
        
        "analyze_scaling": f"📈 Analyzing scaling impact for `{params.get('application_id', 'unknown')}`...\n\n"
                          "⏳ Fetching predictions, metrics, and running cost-benefit analysis...",
        
        "show_bad_apps": "⚠️ Scanning all applications for violations...\n\n"
                        "⏳ Querying Kusto database...",
        
        "show_driver_heavy": "🖥️ Identifying driver-heavy applications...\n\n"
                            "⏳ Analyzing driver CPU and memory metrics...",
        
        "show_memory_intensive": "💾 Finding memory-intensive applications...\n\n"
                                "⏳ Checking memory spills and GC overhead...",
        
        "show_shuffle_issues": "🔀 Detecting shuffle-heavy applications...\n\n"
                              "⏳ Analyzing shuffle read/write patterns...",
        
        "show_best_practice_apps": "✅ Finding well-optimized applications...\n\n"
                                  "⏳ Calculating health scores...",
        
        "general_chat": "💭 Thinking..."
    }
    
    return messages.get(intent, "⏳ Processing...")


# ============================================================================
# FOLLOW-UP ACTIONS
# ============================================================================

def get_follow_up_actions(intent: str, result: Any) -> List[cl.Action]:
    """Get suggested follow-up actions based on intent."""
    
    if intent == "analyze_app":
        return [
            cl.Action(
                name="follow_up",
                payload={"value": "Show me similar apps with this issue"},
                label="🔍 Find Similar Apps"
            ),
            cl.Action(
                name="follow_up",
                payload={"value": "How do I fix the top issue?"},
                label="🛠️ Fix Top Issue"
            ),
            cl.Action(
                name="follow_up",
                payload={"value": "Compare with healthy apps"},
                label="📊 Compare with Best"
            )
        ]
    
    elif intent == "show_bad_apps":
        if isinstance(result, list) and len(result) > 0:
            worst_app = result[0].get("application_id", "unknown") if result else "unknown"
            return [
                cl.Action(
                    name="follow_up",
                    payload={"value": f"Analyze {worst_app}"},
                    label="🔍 Analyze Worst App"
                ),
                cl.Action(
                    name="follow_up",
                    payload={"value": "Show apps that follow best practices"},
                    label="✅ Show Healthy Apps"
                ),
                cl.Action(
                    name="follow_up",
                    payload={"value": "What is the most common issue?"},
                    label="📈 Common Issues"
                )
            ]
    
    elif intent == "show_recent_apps":
        return [
            cl.Action(
                name="follow_up",
                payload={"value": "Show bad apps"},
                label="⚠️ Show Problem Apps"
            ),
            cl.Action(
                name="follow_up",
                payload={"value": "Show driver heavy apps"},
                label="🖥️ Driver Issues"
            ),
            cl.Action(
                name="follow_up",
                payload={"value": "Show healthy apps"},
                label="✅ Healthy Apps"
            )
        ]
    
    elif intent == "show_driver_heavy":
        return [
            cl.Action(
                name="follow_up",
                payload={"value": "Show memory intensive apps too"},
                label="💾 Memory Issues"
            ),
            cl.Action(
                name="follow_up",
                payload={"value": "How do I reduce driver overhead?"},
                label="🛠️ Fix Driver Overhead"
            ),
            cl.Action(
                name="follow_up",
                payload={"value": "Show shuffle heavy apps"},
                label="🔀 Shuffle Issues"
            )
        ]
    
    elif intent in ["show_memory_intensive", "show_shuffle_issues"]:
        return [
            cl.Action(
                name="follow_up",
                payload={"value": "Show driver heavy apps"},
                label="🖥️ Driver Issues"
            ),
            cl.Action(
                name="follow_up",
                payload={"value": "Show healthy apps"},
                label="✅ Healthy Apps"
            ),
            cl.Action(
                name="follow_up",
                payload={"value": "How do I optimize this?"},
                label="🛠️ Get Help"
            )
        ]
    
    elif intent == "show_best_practice_apps":
        return [
            cl.Action(
                name="follow_up",
                payload={"value": "What makes these apps healthy?"},
                label="❓ Why Healthy?"
            ),
            cl.Action(
                name="follow_up",
                payload={"value": "Compare with bad apps"},
                label="📊 Compare Bad vs Good"
            ),
            cl.Action(
                name="follow_up",
                payload={"value": "Show me driver heavy apps"},
                label="🖥️ Show Problems"
            )
        ]
    
    # Default actions
    return [
        cl.Action(
            name="follow_up",
            payload={"value": "Show bad apps"},
            label="⚠️ Problem Apps"
        ),
        cl.Action(
            name="follow_up",
            payload={"value": "Show healthy apps"},
            label="✅ Healthy Apps"
        )
    ]


# ============================================================================
# CHAINLIT HANDLERS
# ============================================================================

@cl.on_chat_start
async def start():
    """Initialize chat session and show welcome message."""
    
    # Initialize session state
    initialize_session_state()
    
    # Initialize orchestrator
    orchestrator = SparkAdvisorOrchestrator()
    cl.user_session.set("orchestrator", orchestrator)
    
    # Professional branded welcome content
    welcome_content = """
<div style="
  background: linear-gradient(145deg, #0A0F14 0%, #0d1318 100%);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 12px;
  padding: 24px 26px;
  margin-bottom: 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2), 0 1px 4px rgba(0, 212, 255, 0.05);
  position: relative;
  overflow: hidden;
">
  <!-- Subtle background gradient -->
  <div style="
    position: absolute; top: -50%; right: -20%; width: 300px; height: 300px;
    background: radial-gradient(circle, rgba(0, 212, 255, 0.06) 0%, transparent 70%);
    pointer-events: none;
  "></div>
  
  <!-- Header with icon -->
  <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 16px; position: relative; z-index: 1;">
    <div style="
      width: 48px; height: 48px; border-radius: 10px;
      background: linear-gradient(135deg, #0099CC 0%, #00D4FF 50%, #B388FF 100%);
      display: flex; align-items: center; justify-content: center;
      font-size: 20px; font-weight: 800; color: #ffffff;
      flex-shrink: 0; letter-spacing: -0.8px;
      box-shadow: 0 4px 12px rgba(0, 212, 255, 0.25);
    ">🎯</div>
    <div>
      <div style="font-family: 'Syne', sans-serif; font-size: 20px; font-weight: 800; color: #E8F4F8; letter-spacing: -0.5px;">
        Fabric <span style="background: linear-gradient(90deg, #00D4FF, #B388FF); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Spark Advisor</span>
      </div>
      <div style="font-size: 11px; color: #5A7A8A; letter-spacing: 0.06em; margin-top: 4px; font-weight: 500;">
        <span style="color: #00D4FF;">●</span> AI-Powered Spark Optimization <span style="color: #3A5060;">·</span> Live Eventhouse Data
      </div>
    </div>
  </div>

  <!-- Description -->
  <div style="font-size: 13px; color: #8b949e; line-height: 1.8; margin-bottom: 18px; padding-left: 62px; position: relative; z-index: 1;">
    Analyzes your Spark applications using <span style="color: #00D4FF; font-weight: 600;">live Kusto data</span>,
    official Fabric docs, and Spark expertise.<br>
    <span style="font-size: 12px; color: #3FB950;">All recommendations show their source</span> — you always know what's from your data vs. AI knowledge.
  </div>

  <!-- Source badges -->
  <div style="display: flex; flex-wrap: wrap; gap: 8px; padding-left: 62px; padding-top: 14px; border-top: 1px solid rgba(28, 42, 53, 0.6); position: relative; z-index: 1;">
    <span style="
      padding: 6px 12px; background: linear-gradient(135deg, rgba(63, 185, 80, 0.1), rgba(63, 185, 80, 0.05));
      border: 1px solid rgba(63, 185, 80, 0.3); font-size: 10px; color: #3FB950;
      border-radius: 6px; font-weight: 600; letter-spacing: 0.02em;
    ">● Spark Advisor recommendations</span>
    <span style="
      padding: 6px 12px; background: linear-gradient(135deg, rgba(0, 212, 255, 0.1), rgba(0, 212, 255, 0.05));
      border: 1px solid rgba(0, 212, 255, 0.3); font-size: 10px; color: #00D4FF;
      border-radius: 6px; font-weight: 600; letter-spacing: 0.02em;
    ">● Fabric recommendations</span>
    <span style="
      padding: 6px 12px; background: linear-gradient(135deg, rgba(41, 182, 246, 0.1), rgba(41, 182, 246, 0.05));
      border: 1px solid rgba(41, 182, 246, 0.3); font-size: 10px; color: #29B6F6;
      border-radius: 6px; font-weight: 600; letter-spacing: 0.02em;
    ">● SparkDocumentation RAG</span>
    <span style="
      padding: 6px 12px; background: linear-gradient(135deg, rgba(179, 136, 255, 0.1), rgba(179, 136, 255, 0.05));
      border: 1px solid rgba(179, 136, 255, 0.3); font-size: 10px; color: #B388FF;
      border-radius: 6px; font-weight: 600; letter-spacing: 0.02em;
    ">● GPT-4o fallback (labeled)</span>
  </div>
</div>
"""

    commands_content = """
<div style="
  font-family: 'IBM Plex Mono', monospace;
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 12px; font-size: 12px;
">
  <div style="
    background: linear-gradient(145deg, #0D1318 0%, #0a0f14 100%);
    border: 1px solid rgba(0, 212, 255, 0.2);
    border-radius: 10px; padding: 18px 20px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    transition: all 0.3s ease;
  ">
    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 14px;">
      <span style="font-size: 18px;">🔍</span>
      <div style="color: #00D4FF; font-weight: 700; letter-spacing: 0.03em; font-size: 11px;">
        APP ANALYSIS
      </div>
    </div>
    <div style="display: flex; flex-direction: column; gap: 8px; color: #8b949e;">
      <div style="padding: 6px 10px; background: rgba(0, 212, 255, 0.05); border-left: 2px solid rgba(0, 212, 255, 0.3); border-radius: 4px;">> analyze app-123</div>
      <div style="padding: 6px 10px; background: rgba(0, 212, 255, 0.05); border-left: 2px solid rgba(0, 212, 255, 0.3); border-radius: 4px;">> recommendations for application_177..._0001</div>
      <div style="padding: 6px 10px; background: rgba(0, 212, 255, 0.05); border-left: 2px solid rgba(0, 212, 255, 0.3); border-radius: 4px;">> what issues does my-pipeline have?</div>
      <div style="padding: 6px 10px; background: rgba(0, 212, 255, 0.05); border-left: 2px solid rgba(0, 212, 255, 0.3); border-radius: 4px;">> show scaling predictions for app-456</div>
    </div>
  </div>

  <div style="
    background: linear-gradient(145deg, #0D1318 0%, #0a0f14 100%);
    border: 1px solid rgba(255, 82, 82, 0.2);
    border-radius: 10px; padding: 18px 20px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    transition: all 0.3s ease;
  ">
    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 14px;">
      <span style="font-size: 18px;">⚠️</span>
      <div style="color: #FF5252; font-weight: 700; letter-spacing: 0.03em; font-size: 11px;">
        PROBLEM DETECTION
      </div>
    </div>
    <div style="display: flex; flex-direction: column; gap: 8px; color: #8b949e;">
      <div style="padding: 6px 10px; background: rgba(255, 82, 82, 0.05); border-left: 2px solid rgba(255, 82, 82, 0.3); border-radius: 4px;">> show bad apps</div>
      <div style="padding: 6px 10px; background: rgba(255, 82, 82, 0.05); border-left: 2px solid rgba(255, 82, 82, 0.3); border-radius: 4px;">> show me driver heavy jobs</div>
      <div style="padding: 6px 10px; background: rgba(255, 82, 82, 0.05); border-left: 2px solid rgba(255, 82, 82, 0.3); border-radius: 4px;">> which apps have shuffle spills?</div>
      <div style="padding: 6px 10px; background: rgba(255, 82, 82, 0.05); border-left: 2px solid rgba(255, 82, 82, 0.3); border-radius: 4px;">> top 5 apps by executor time</div>
    </div>
  </div>

  <div style="
    background: linear-gradient(145deg, #0D1318 0%, #0a0f14 100%);
    border: 1px solid rgba(0, 230, 118, 0.2);
    border-radius: 10px; padding: 18px 20px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    transition: all 0.3s ease;
  ">
    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 14px;">
      <span style="font-size: 18px;">✅</span>
      <div style="color: #00E676; font-weight: 700; letter-spacing: 0.03em; font-size: 11px;">
        HEALTHY APPS
      </div>
    </div>
    <div style="display: flex; flex-direction: column; gap: 8px; color: #8b949e;">
      <div style="padding: 6px 10px; background: rgba(0, 230, 118, 0.05); border-left: 2px solid rgba(0, 230, 118, 0.3); border-radius: 4px;">> show well optimized apps</div>
      <div style="padding: 6px 10px; background: rgba(0, 230, 118, 0.05); border-left: 2px solid rgba(0, 230, 118, 0.3); border-radius: 4px;">> which apps are healthy?</div>
      <div style="padding: 6px 10px; background: rgba(0, 230, 118, 0.05); border-left: 2px solid rgba(0, 230, 118, 0.3); border-radius: 4px;">> top 5 by executor efficiency</div>
      <div style="padding: 6px 10px; background: rgba(0, 230, 118, 0.05); border-left: 2px solid rgba(0, 230, 118, 0.3); border-radius: 4px;">> show best practice applications</div>
    </div>
  </div>

  <div style="
    background: linear-gradient(145deg, #0D1318 0%, #0a0f14 100%);
    border: 1px solid rgba(255, 179, 0, 0.2);
    border-radius: 10px; padding: 18px 20px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    transition: all 0.3s ease;
  ">
    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 14px;">
      <span style="font-size: 18px;">💡</span>
      <div style="color: #FFB300; font-weight: 700; letter-spacing: 0.03em; font-size: 11px;">
        GENERAL QUESTIONS
      </div>
    </div>
   <div style="display: flex; flex-direction: column; gap: 8px; color: #8b949e;">
      <div style="padding: 6px 10px; background: rgba(255, 179, 0, 0.05); border-left: 2px solid rgba(255, 179, 0, 0.3); border-radius: 4px;">> what is shuffle spill?</div>
      <div style="padding: 6px 10px; background: rgba(255, 179, 0, 0.05); border-left: 2px solid rgba(255, 179, 0, 0.3); border-radius: 4px;">> how do I fix GC overhead?</div>
      <div style="padding: 6px 10px; background: rgba(255, 179, 0, 0.05); border-left: 2px solid rgba(255, 179, 0, 0.3); border-radius: 4px;">> what is VOrder in Fabric?</div>
      <div style="padding: 6px 10px; background: rgba(255, 179, 0, 0.05); border-left: 2px solid rgba(255, 179, 0, 0.3); border-radius: 4px;">> explain Native Execution Engine</div>
    </div>
  </div>
</div>

<div style="
  font-family: 'IBM Plex Mono', monospace;
  margin-top: 12px; padding: 14px 18px;
  background: linear-gradient(145deg, #0D1318 0%, #0a0f14 100%);
  border: 1px solid rgba(179, 136, 255, 0.15);
  border-radius: 10px;
  display: flex; justify-content: space-between; align-items: center;
  font-size: 10.5px; color: #5A7A8A;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
">
  <span style="font-weight: 600; letter-spacing: 0.02em;">
    <span style="color: #B388FF;">GPT-4o</span> · <span style="color: #29B6F6;">Semantic Kernel</span> · <span style="color: #00D4FF;">FastMCP</span> · <span style="color: #3FB950;">Azure AI Search</span>
  </span>
  <span>Reply <span style="color: #3FB950; font-weight: 700;">HELPFUL</span> or <span style="color: #FF5252; font-weight: 700;">NOT HELPFUL</span> after each response</span>
</div>
"""
    
    # Send welcome message
    await cl.Message(
        content=welcome_content + commands_content,
        author="Fabric Spark Advisor"
    ).send()


@cl.on_message
async def main(message: cl.Message):
    """Handle incoming chat messages."""
    
    # Get orchestrator
    orchestrator = cl.user_session.get("orchestrator")
    if not orchestrator:
        orchestrator = SparkAdvisorOrchestrator()
        cl.user_session.set("orchestrator", orchestrator)
    
    # Get session ID for context tracking
    session_id = cl.user_session.get("id", "default")
    
    # Check if this is feedback first
    feedback = detect_feedback(message.content)
    if feedback:
        # User is providing feedback on the last response
        last_query = cl.user_session.get("last_query_text", "")
        last_response = cl.user_session.get("last_response_text", "")
        last_intent = cl.user_session.get("last_query_intent", "general_chat")
        last_app_id = cl.user_session.get("last_application_id", "N/A")
        last_rec_count = cl.user_session.get("last_recommendation_count", 0)
        last_sources = cl.user_session.get("last_source_counts", {"kusto": 0, "rag": 0, "llm": 0})
        
        # Save feedback to Kusto
        try:
            success = orchestrator.kusto_client.insert_feedback(
                session_id=session_id,
                application_id=last_app_id,
                query_text=last_query,
                query_intent=last_intent,
                actual_result_generated=last_response,
                feedback_type=feedback["feedback_type"],
                feedback_comment=feedback["comment"],
                recommendation_count=last_rec_count,
                source_kusto_count=last_sources.get("kusto", 0),
                source_rag_count=last_sources.get("rag", 0),
                source_llm_count=last_sources.get("llm", 0)
            )
            
            if success:
                response_msg = "✅ Thank you for your feedback! This helps improve future recommendations."
                
                # Add personalized follow-up based on feedback type
                if feedback["feedback_type"] == "NOT_HELPFUL":
                    response_msg += "\n\nI'm sorry the response wasn't helpful. Could you rephrase your question or ask something more specific?"
                elif feedback["feedback_type"] == "PARTIAL":
                    response_msg += "\n\nI'll try to address what was missing. What additional information would you like?"
                else:  # HELPFUL
                    response_msg += "\n\nWhat else can I help you analyze?"
                
                await cl.Message(content=response_msg).send()
            else:
                await cl.Message(content="⚠️ Feedback received but couldn't save to database. Thank you anyway!").send()
        
        except Exception as e:
            print(f"Error saving feedback: {e}")
            await cl.Message(content="⚠️ Error saving feedback, but thank you for providing it!").send()
        
        return  # Don't process as regular query
    
    # Resolve coreferences BEFORE intent detection (critical for follow-up queries)
    session_id = cl.user_session.get("id")
    try:
        # Get orchestrator's session context
        session = orchestrator.sessions.get(session_id, {})
        current_app_id = session.get("current_app_id")
        
        # Helper: Check if query needs app context but doesn't have app ID
        def needs_app_context(msg):
            msg_lower = msg.lower()
            # Scaling/skew queries that need app context
            context_triggers = [
                "scaling", "scale", "executor", "resource", "skew", "imbalance",
                "improve performance", "will it help", "should i", "can i"
            ]
            return any(trigger in msg_lower for trigger in context_triggers)
        
        # Trigger resolution if:
        # 1. Message explicitly references "this" or
        # 2. There's a current app AND query needs app context
        should_resolve = (
            "this application" in message.content.lower() or
            "this app" in message.content.lower() or
            (current_app_id and needs_app_context(message.content))
        )
        
        if should_resolve:
            # First try LLM resolution
            resolved_data = await orchestrator._resolve_references(message.content, session)
            resolved_message = resolved_data.get("resolved_message", message.content)
            
            # If LLM didn't resolve and we have current_app_id, manually inject it
            if resolved_message == message.content and current_app_id and needs_app_context(message.content):
                # Manually inject app ID at the start
                resolved_message = f"{current_app_id} {message.content}"
                print(f"  🔗 UI: Auto-injected app ID: '{message.content}' → '{resolved_message}'")
            elif resolved_message != message.content:
                print(f"  🔗 UI: Resolved '{message.content}' → '{resolved_message}'")
            
            message_to_analyze = resolved_message
        else:
            message_to_analyze = message.content
    except Exception as e:
        print(f"  ⚠️ Coreference resolution failed: {e}, using original message")
        message_to_analyze = message.content
    
    # Detect intent for regular queries (now uses resolved message)
    intent_result = detect_intent(message_to_analyze)
    intent = intent_result["intent"]
    params = intent_result["params"]
    
    # Show loading message
    loading_msg = get_loading_message(intent, params)
    loading = await cl.Message(content=loading_msg).send()
    
    try:
        # Route based on intent
        result = None
        response_text = ""
        
        if intent == "analyze_app":
            app_id = params["application_id"]
            
            # Show progress indicators
            async with cl.Step(name="🔍 Analyzing application...", type="tool") as step:
                step.output = f"Application ID: {app_id}"
            
            async with cl.Step(name="📊 Fetching Kusto telemetry...", type="tool") as step:
                result = await orchestrator.analyze_application(app_id, session_id=session_id)
                step.output = "✓ Retrieved SparkLens + Fabric recommendations"
            
            async with cl.Step(name="📚 Searching documentation...", type="tool") as step:
                step.output = "✓ Found relevant best practices"
            
            async with cl.Step(name="🤖 Generating analysis...", type="llm") as step:
                try:
                    print(f"  🔍 Formatting result with {len(result.get('validated_recommendations', []))} recs")
                    recs = result.get('validated_recommendations', [])
                    if recs:
                        print(f"  🔍 Sample rec: {recs[0]}")
                        kusto_count = len([r for r in recs if r.get("source") == "kusto" or r.get("metadata", {}).get("from_kusto")])
                        print(f"  🔍 Kusto recs by source tag: {len([r for r in recs if r.get('source') == 'kusto'])}")
                        print(f"  🔍 Kusto recs by metadata: {len([r for r in recs if r.get('metadata', {}).get('from_kusto')])}")
                        print(f"  🔍 Total Kusto count: {kusto_count}")
                    
                    print(f"  🔍 Calling format_app_analysis...")
                    response_text = format_app_analysis(result)
                    print(f"  ✅ format_app_analysis returned {len(response_text)} chars")
                    step.output = "✓ Analysis complete"
                except Exception as format_error:
                    print(f"  ❌ FORMAT ERROR: {format_error}")
                    import traceback
                    traceback.print_exc()
                    raise
            
            print(f"  🔍 Calling update_session_state...")
            try:
                update_session_state(result, intent)
                print(f"  ✅ update_session_state complete")
            except Exception as state_error:
                print(f"  ❌ STATE UPDATE ERROR: {state_error}")
                import traceback
                traceback.print_exc()
            
            print(f"  🔍 Storing feedback context...")
            # Store context for feedback
            cl.user_session.set("last_query_text", message.content)
            cl.user_session.set("last_response_text", response_text)
            cl.user_session.set("last_query_intent", intent)
            cl.user_session.set("last_application_id", app_id)
            cl.user_session.set("last_recommendation_count", len(result.get("validated_recommendations", [])))
            cl.user_session.set("last_source_counts", result.get("source_counts", {"kusto": 0, "rag": 0, "llm": 0}))
            print(f"  ✅ Feedback context stored")
        
        elif intent == "show_bad_apps":
            min_violations = params.get("min_violations", 3)
            result = orchestrator.find_bad_applications(min_violations)
            response_text = format_app_table(
                result,
                "⚠️ Applications with Bad Practices",
                ["application_id", "violation_count"]
            )
            update_session_state({}, intent, app_count=len(result) if result else 0)
            
            # Store context for feedback
            cl.user_session.set("last_query_text", message.content)
            cl.user_session.set("last_response_text", response_text)
            cl.user_session.set("last_query_intent", intent)
            cl.user_session.set("last_application_id", "N/A")
            cl.user_session.set("last_recommendation_count", len(result) if result else 0)
            cl.user_session.set("last_source_counts", {"kusto": len(result) if result else 0, "rag": 0, "llm": 0})
        
        elif intent == "show_recent_apps":
            hours = params.get("hours", 24)
            result = orchestrator.find_recent_applications(hours)
            
            # Generate descriptive time description
            if hours == 24:
                time_desc = "today"
            elif hours == 24 * 7:
                time_desc = "from the last 7 days"
            elif hours < 24:
                time_desc = f"from the last {hours} hours"
            elif hours % 24 == 0:
                days = hours // 24
                time_desc = f"from the last {days} days"
            else:
                time_desc = f"from the last {hours} hours"
            
            response_text = format_recent_apps_table(result, time_desc)
            update_session_state({}, intent, app_count=len(result) if result else 0)
            
            # Store context for feedback
            cl.user_session.set("last_query_text", message.content)
            cl.user_session.set("last_response_text", response_text)
            cl.user_session.set("last_query_intent", intent)
            cl.user_session.set("last_application_id", "N/A")
            cl.user_session.set("last_recommendation_count", len(result) if result else 0)
            cl.user_session.set("last_source_counts", {"kusto": len(result) if result else 0, "rag": 0, "llm": 0})
        
        elif intent == "show_driver_heavy":
            result = orchestrator.find_applications_by_pattern("driver_heavy")
            response_text = format_driver_heavy_table(result)
            update_session_state({}, intent, app_count=len(result) if result else 0)
            
            # Store context for feedback
            cl.user_session.set("last_query_text", message.content)
            cl.user_session.set("last_response_text", response_text)
            cl.user_session.set("last_query_intent", intent)
            cl.user_session.set("last_application_id", "N/A")
            cl.user_session.set("last_recommendation_count", len(result) if result else 0)
            cl.user_session.set("last_source_counts", {"kusto": len(result) if result else 0, "rag": 0, "llm": 0})
        
        elif intent == "show_memory_intensive":
            result = orchestrator.find_applications_by_pattern("memory_intensive")
            response_text = format_memory_table(result)
            update_session_state({}, intent, app_count=len(result) if result else 0)
            
            # Store context for feedback
            cl.user_session.set("last_query_text", message.content)
            cl.user_session.set("last_response_text", response_text)
            cl.user_session.set("last_query_intent", intent)
            cl.user_session.set("last_application_id", "N/A")
            cl.user_session.set("last_recommendation_count", len(result) if result else 0)
            cl.user_session.set("last_source_counts", {"kusto": len(result) if result else 0, "rag": 0, "llm": 0})
        
        elif intent == "show_shuffle_issues":
            result = orchestrator.find_applications_by_pattern("shuffle_heavy")
            response_text = format_app_table(
                result,
                "🔀 Shuffle-Heavy Applications",
                ["ApplicationId", "TotalShuffle", "AvgShufflePerJob", "JobCount"]
            )
            update_session_state({}, intent, app_count=len(result) if result else 0)
            
            # Store context for feedback
            cl.user_session.set("last_query_text", message.content)
            cl.user_session.set("last_response_text", response_text)
            cl.user_session.set("last_query_intent", intent)
            cl.user_session.set("last_application_id", "N/A")
            cl.user_session.set("last_recommendation_count", len(result) if result else 0)
            cl.user_session.set("last_source_counts", {"kusto": len(result) if result else 0, "rag": 0, "llm": 0})
        
        elif intent == "show_best_practice_apps":
            min_score = params.get("min_score", 80)
            result = orchestrator.find_healthy_applications(min_score)
            response_text = format_healthy_apps_table(result)
            update_session_state({}, intent, app_count=len(result) if result else 0)
            
            # Store context for feedback
            cl.user_session.set("last_query_text", message.content)
            cl.user_session.set("last_response_text", response_text)
            cl.user_session.set("last_query_intent", intent)
            cl.user_session.set("last_application_id", "N/A")
            cl.user_session.set("last_recommendation_count", len(result) if result else 0)
            cl.user_session.set("last_source_counts", {"kusto": len(result) if result else 0, "rag": 0, "llm": 0})
        
        elif intent == "analyze_skew":
            app_id = params.get("application_id")
            
            # Show progress indicators
            async with cl.Step(name="📊 Fetching stage telemetry...", type="tool") as step:
                step.output = f"Application ID: {app_id}"
            
            async with cl.Step(name="🔍 Analyzing task distribution...", type="tool") as step:
                result = await orchestrator.analyze_skew(app_id, session_id=session_id)
                step.output = "✓ Retrieved stage-level metrics"
            
            async with cl.Step(name="🤖 Identifying skew patterns...", type="llm") as step:
                response_text = format_skew_analysis(result)
                step.output = "✓ Skew analysis complete"
            
            # Update session state
            stages_with_skew = result.get("stages_with_skew", 0)
            update_session_state({}, intent, app_count=stages_with_skew)
            
            # Store context for feedback
            cl.user_session.set("last_query_text", message.content)
            cl.user_session.set("last_response_text", response_text)
            cl.user_session.set("last_query_intent", intent)
            cl.user_session.set("last_application_id", app_id)
            cl.user_session.set("last_recommendation_count", stages_with_skew)
            cl.user_session.set("last_source_counts", {"kusto": 1, "rag": 0, "llm": 1})  # Stage data from Kusto + LLM analysis
        
        elif intent == "analyze_scaling":
            app_id = params.get("application_id")
            
            # Show progress indicators
            async with cl.Step(name="📊 Fetching scaling predictions...", type="tool") as step:
                step.output = f"Application ID: {app_id}"
            
            async with cl.Step(name="📈 Analyzing resource impact...", type="tool") as step:
                result = await orchestrator.analyze_scaling_impact(app_id, session_id=session_id)
                step.output = "✓ Retrieved SparkLens predictions + current metrics"
            
            async with cl.Step(name="🤖 Generating recommendations...", type="llm") as step:
                response_text = format_scaling_analysis(result)
                step.output = "✓ Cost-benefit analysis complete"
            
            # Update session state
            update_session_state({}, intent, app_count=1)
            
            # Store context for feedback
            cl.user_session.set("last_query_text", message.content)
            cl.user_session.set("last_response_text", response_text)
            cl.user_session.set("last_query_intent", intent)
            cl.user_session.set("last_application_id", app_id)
            cl.user_session.set("last_recommendation_count", 1)
            cl.user_session.set("last_source_counts", {"kusto": 1, "rag": 0, "llm": 1})  # Predictions + metrics from Kusto + LLM analysis
        
        else:  # general_chat
            response_text = await orchestrator.chat(message.content, session_id=session_id)
            
            # Detect what type of general chat response was provided
            query_type = None
            row_count = 0
            
            # Check if it was a dynamic query (look for query results indicator)
            if "📊 Query Results" in response_text or "Generated KQL Query" in response_text:
                query_type = "dynamic_query"
                # Try to extract row count from response
                import re
                count_match = re.search(r'\((\d+) records?\)', response_text)
                if count_match:
                    row_count = int(count_match.group(1))
            
            # Check if it was a RAG response (look for documentation references)
            elif "**Source:**" in response_text or "documentation" in response_text.lower():
                query_type = "rag"
            
            # Update session state for general chat
            update_session_state({}, intent, app_count=row_count, query_type=query_type)
            
            # Store context for feedback
            cl.user_session.set("last_query_text", message.content)
            cl.user_session.set("last_response_text", response_text)
            cl.user_session.set("last_query_intent", "general_chat")
            cl.user_session.set("last_application_id", "N/A")
            cl.user_session.set("last_recommendation_count", 0)
            cl.user_session.set("last_source_counts", {"kusto": 0, "rag": 0, "llm": 0})
        
        # Remove loading message
        await loading.remove()
        
        print(f"  🔍 About to send response ({len(response_text)} chars)...")
        # Send response
        try:
            await cl.Message(content=response_text).send()
            print(f"  ✅ Response sent successfully")
        except Exception as send_error:
            print(f"  ❌ SEND ERROR: {send_error}")
            import traceback
            traceback.print_exc()
            raise
        
        # Add feedback action buttons for most query types
        if intent in ["analyze_app", "show_bad_apps", "show_recent_apps", "general_chat"]:
            feedback_actions = [
                cl.Action(
                    name="feedback",
                    payload={"value": "HELPFUL"},
                    label="✅ Helpful",
                    description="This analysis was helpful"
                ),
                cl.Action(
                    name="feedback",
                    payload={"value": "NOT_HELPFUL"},
                    label="❌ Not Helpful",
                    description="This analysis was not helpful"
                ),
                cl.Action(
                    name="feedback",
                    payload={"value": "PARTIAL"},
                    label="⚠️ Partially Helpful",
                    description="This analysis was partially helpful"
                )
            ]
            
            await cl.Message(
                content="💬 **Was this helpful?** Click a button below:",
                actions=feedback_actions
            ).send()
        
        # Send sidebar update
        await send_sidebar_update()
        
        # Send follow-up actions
        actions = get_follow_up_actions(intent, result)
        if actions:
            await cl.Message(
                content="**What would you like to do next?**",
                actions=actions
            ).send()
    
    except Exception as e:
        await loading.remove()
        error_msg = f"❌ **Error:** {str(e)}\n\nPlease try again or ask a different question."
        await cl.Message(content=error_msg).send()


@cl.action_callback("feedback")
async def handle_feedback(action: cl.Action):
    """Handle feedback action button clicks."""
    feedback_type = action.value
    
    # Get orchestrator
    orchestrator = cl.user_session.get("orchestrator")
    if not orchestrator:
        await cl.Message(content="⚠️ Session expired. Please start a new analysis.").send()
        return
    
    # Get session context
    session_id = cl.user_session.get("id", "default")
    last_query = cl.user_session.get("last_query_text", "")
    last_response = cl.user_session.get("last_response_text", "")
    last_intent = cl.user_session.get("last_query_intent", "general_chat")
    last_app_id = cl.user_session.get("last_application_id", "N/A")
    last_rec_count = cl.user_session.get("last_recommendation_count", 0)
    last_sources = cl.user_session.get("last_source_counts", {"kusto": 0, "rag": 0, "llm": 0})
    
    # For NOT_HELPFUL and PARTIAL, ask for comment
    comment = ""
    if feedback_type in ["NOT_HELPFUL", "PARTIAL"]:
        prompt_text = {
            "NOT_HELPFUL": "What made this analysis not helpful? (e.g., too generic, wrong for my case, incorrect data)",
            "PARTIAL": "What was missing from this analysis?"
        }
        
        res = await cl.AskUserMessage(
            content=prompt_text[feedback_type],
            timeout=30
        ).send()
        
        if res:
            comment = res.get("output", "")
    
    # Save feedback to Kusto
    try:
        success = orchestrator.kusto_client.insert_feedback(
            session_id=session_id,
            application_id=last_app_id,
            query_text=last_query,
            query_intent=last_intent,
            actual_result_generated=last_response,
            feedback_type=feedback_type,
            feedback_comment=comment,
            recommendation_count=last_rec_count,
            source_kusto_count=last_sources.get("kusto", 0),
            source_rag_count=last_sources.get("rag", 0),
            source_llm_count=last_sources.get("llm", 0)
        )
        
        if success:
            response_messages = {
                "HELPFUL": "✅ Thank you! Your positive feedback helps us improve.",
                "NOT_HELPFUL": "🔧 Thank you for the feedback. We'll work on improving this type of analysis.",
                "PARTIAL": "📝 Thank you! We'll use your input to enhance future recommendations."
            }
            await cl.Message(content=response_messages[feedback_type]).send()
        else:
            await cl.Message(content="⚠️ Feedback received but couldn't save to database. Thank you anyway!").send()
    
    except Exception as e:
        print(f"Error saving feedback: {e}")
        await cl.Message(content="⚠️ Error saving feedback, but thank you for providing it!").send()


@cl.action_callback("follow_up")
async def handle_follow_up(action: cl.Action):
    """Handle follow-up action button clicks."""
    # Treat clicked action as a new message
    await main(cl.Message(content=action.payload["value"]))


@cl.action_callback("quick_start")
async def handle_quick_start(action: cl.Action):
    """Handle quick-start action button clicks."""
    # Treat clicked action as a new message
    await main(cl.Message(content=action.payload["value"]))


# ============================================================================
# RUN THE APP
# ============================================================================

if __name__ == "__main__":
    # Run with: chainlit run ui/app.py --port 8501
    pass
