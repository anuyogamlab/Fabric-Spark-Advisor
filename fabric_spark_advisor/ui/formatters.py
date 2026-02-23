"""
Response formatters for Spark Advisor UI.

These formatters convert analysis results into styled HTML/Markdown
for display in Gradio chat interface, maintaining visual consistency
with the Chainlit web UI.
"""
from typing import Dict, Any, List
import re


def format_app_analysis(result: Dict[str, Any]) -> str:
    """
    Format application analysis results with clean box/card layouts.
    Grouped by source: KUSTO → RAG → LLM
    
    Args:
        result: Analysis result dictionary from orchestrator
    
    Returns:
        Formatted HTML/Markdown string
    """
    app_id = result.get("application_id", "unknown")
    health = result.get("overall_health", "unknown").upper()
    summary = result.get("summary", "No summary available")
    recs = result.get("validated_recommendations", [])
    
    # Group recommendations by source
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
    
    # TIER 1: KUSTO RECOMMENDATIONS
    md += """
<div style="margin-top: 24px;">
  <div style="background: linear-gradient(90deg, #0099CC, #00D4FF); height: 3px; margin-bottom: 12px;"></div>
  <h2 style="color: #00D4FF; margin: 0 0 8px 0; font-size: 18px;">📊 TIER 1 — Kusto Telemetry (Ground Truth)</h2>
  <p style="color: #5A7A8A; font-size: 12px; margin: 0 0 16px 0;"><strong>Source:</strong> Live Eventhouse data | <strong>Trust:</strong> ✅ VERIFIED</p>
</div>

"""
    
    if kusto_recs:
        for i, rec in enumerate(kusto_recs, 1):
            text = rec.get("recommendation", rec.get("text", "No recommendation text"))
            text_html = text.replace('\n', '<br>')
            
            priority = rec.get("priority", 999)
            metadata = rec.get("metadata", {})
            severity = metadata.get("severity", "").upper()
            
            if severity in ["CRITICAL", "HIGH"] or priority <= 9:
                border_color, bg_color = "#FF5252", "#1A0F0F"
            elif severity in ["MEDIUM", "WARNING"] or priority <= 29:
                border_color, bg_color = "#FFB300", "#1A1610"
            else:
                border_color, bg_color = "#3FB950", "#0F1A14"
            
            md += f"""
<div style="background: {bg_color}; border-left: 4px solid {border_color}; border-radius: 4px; padding: 14px 16px; margin-bottom: 12px;">
  <div style="color: #E8F4F8; font-size: 13px; line-height: 1.7;">
{text_html}
  </div>
</div>

"""
    else:
        md += """
<div style="background: #0D1318; border: 1px dashed #1C2A35; border-radius: 4px; padding: 14px 16px; margin-bottom: 12px;">
  <p style="color: #5A7A8A; font-style: italic; margin: 0;">
    No Spark Advisor or Fabric recommendations found in Kusto for this application.
  </p>
</div>

"""
    
    # TIER 2: RAG DOCUMENTATION
    md += """
<div style="margin-top: 32px;">
  <div style="background: linear-gradient(90deg, #3FB950, #00E676); height: 3px; margin-bottom: 12px;"></div>
  <h2 style="color: #3FB950; margin: 0 0 8px 0; font-size: 18px;">📚 TIER 2 — Documentation & Best Practices</h2>
  <p style="color: #5A7A8A; font-size: 12px; margin: 0 0 16px 0;"><strong>Source:</strong> Official Microsoft Fabric Spark docs | <strong>Trust:</strong> 📖 OFFICIAL</p>
</div>

"""
    
    if rag_recs:
        for i, rec in enumerate(rag_recs, 1):
            text = rec.get("recommendation", rec.get("text", "No recommendation text"))
            metadata = rec.get("metadata", {})
            doc_title = metadata.get("title", f"Documentation #{i}")
            source_url = metadata.get("source_url", "")
            
            truncated = len(text) > 1500
            if truncated:
                text = text[:1500]
            
            doc_link = ""
            if source_url:
                link_text = "Read full documentation →" if truncated else "View source documentation →"
                doc_link = f"""<div style="margin-top: 12px; padding-top: 10px; border-top: 1px solid #1C2A35;">
    <a href="{source_url}" target="_blank" style="color: #00D4FF; text-decoration: none; font-size: 12px;">
      📄 {link_text}
    </a>
  </div>"""
            
            md += f"""
<div style="background: #0D1318; border: 1px solid #243040; border-radius: 4px; padding: 16px 18px; margin-bottom: 14px;">
  <div style="color: #3FB950; font-weight: 600; font-size: 13px; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px;">
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
    
    # TIER 3: LLM RECOMMENDATIONS
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
            
            # Format text with structure
            paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
            formatted_body = ""
            for para in paragraphs:
                if para.startswith('-') or para.startswith('•') or re.match(r'^\d+\.', para):
                    formatted_body += f"\n{para}\n"
                elif para.endswith('?') or para.endswith(':'):
                    formatted_body += f"\n**{para}**\n"
                else:
                    formatted_body += f"\n{para}\n"
            
            formatted_body = re.sub(r'\n{3,}', '\n\n', formatted_body)
            
            # Extract title
            first_sentence_match = re.match(r'^([^.!?]+[.!?])', text)
            if first_sentence_match:
                title = first_sentence_match.group(1).strip()
            else:
                lines = text.split('\n')
                title = lines[0][:100] if lines[0] else "LLM Recommendation"
            
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
        md += """
<div style="background: #0D1318; border: 1px dashed #1C2A35; border-radius: 4px; padding: 14px 16px; margin-bottom: 12px;">
  <p style="color: #5A7A8A; font-style: italic; margin: 0;">No AI-generated recommendations needed — sufficient verified data available.</p>
</div>

"""
    
    return md


def format_skew_analysis(result: Dict[str, Any]) -> str:
    """
    Format skew analysis results with stage details and LLM recommendations.
    
    Args:
        result: Skew analysis result dictionary
    
    Returns:
        Formatted HTML/Markdown string
    """
    app_id = result.get("application_id", "unknown")
    status = result.get("status", "unknown")
    
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

**Note:** This application may not have detailed stage telemetry.
"""
    
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
    
    if llm_analysis:
        md += """
<div style="margin-top: 32px;">
  <div style="background: linear-gradient(90deg, #B388FF, #00D4FF); height: 3px; margin-bottom: 12px;"></div>
  <h2 style="color: #B388FF; margin: 0 0 8px 0; font-size: 18px;">🤖 Detailed Analysis & Recommendations</h2>
</div>

"""
        md += f"\n{llm_analysis}\n\n"
    
    return md


def format_scaling_analysis(result: Dict[str, Any]) -> str:
    """
    Format scaling impact analysis results with predictions and recommendations.
    
    Args:
        result: Scaling analysis result dictionary
    
    Returns:
        Formatted HTML/Markdown string
    """
    app_id = result.get("application_id", "unknown")
    status = result.get("status", "unknown")
    
    if status == "error":
        error = result.get("error", "Unknown error")
        return f"""
### ⚠️ Scaling Analysis Failed

**Application:** `{app_id}`

**Error:** {error}

Please verify the application ID exists and has metrics data in the database.
"""
    
    recommendation = result.get("recommendation", "UNKNOWN")
    llm_analysis = result.get("llm_analysis", "")
    current_metrics = result.get("current_metrics", {})
    predictions_count = result.get("predictions_count", 0)
    
    duration = current_metrics.get("duration_sec", 0)
    executors = current_metrics.get("executor_count", 0)
    driver_time = current_metrics.get("driver_time_pct", 0)
    efficiency = current_metrics.get("executor_efficiency", 0)
    
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
    
    # Current metrics cards
    md += """
<div style="margin-top: 24px;">
  <div style="background: linear-gradient(90deg, #FFB300, #FF5252); height: 3px; margin-bottom: 12px;"></div>
  <h2 style="color: #FFB300; margin: 0 0 8px 0; font-size: 18px;">📊 Current Performance Metrics</h2>
</div>

"""
    
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
    
    if llm_analysis:
        md += """
<div style="margin-top: 32px;">
  <div style="background: linear-gradient(90deg, #B388FF, #00D4FF); height: 3px; margin-bottom: 12px;"></div>
  <h2 style="color: #B388FF; margin: 0 0 8px 0; font-size: 18px;">📈 Detailed Scaling Analysis</h2>
</div>

"""
        md += f"\n{llm_analysis}\n\n"
    
    return md
