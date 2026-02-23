"""
Gradio chat interface for Fabric Spark Advisor.

Provides notebook-friendly UI with dark theme matching Chainlit web app.
"""
import gradio as gr
from typing import List, Tuple, Dict, Any
import asyncio
from ..client.mcp_client import MCPClient
from .formatters import format_app_analysis, format_scaling_analysis, format_skew_analysis
from .intent import detect_intent


def create_gradio_interface(
    mcp_client: MCPClient,
    theme: str = "dark",
    chatbot_height: int = 700
):
    """
    Create Gradio chat interface connected to MCP server.
    
    Args:
        mcp_client: MCP client instance for server communication
        theme: UI theme ("dark" or "light")
        chatbot_height: Height of chatbot component in pixels
    
    Returns:
        Gradio Blocks app instance
    """
    
    # Define custom CSS for dark theme matching Chainlit
    custom_css = """
    .gradio-container {
        background-color: #0D1318 !important;
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .message-wrap {
        background-color: #1A2633 !important;
    }
    .bot {
        background-color: #0D1318 !important;
        border-left: 3px solid #00D4FF;
    }
    .user {
        background-color: #1A2633 !important;
        border-left: 3px solid #B388FF;
    }
    code {
        background-color: #1C2A35 !important;
        color: #00D4FF !important;
        padding: 2px 6px;
        border-radius: 3px;
        font-family: 'Consolas', 'Monaco', monospace;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 16px 0;
    }
    th, td {
        border: 1px solid #243040;
        padding: 10px;
        text-align: left;
    }
    th {
        background-color: #1A2633;
        color: #00D4FF;
        font-weight: 600;
    }
    """
    
    async def chat_handler(
        message: str,
        history: List[Tuple[str, str]],
        session_state: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Process user message and return response.
        
        Flow:
        1. Detect intent (analyze_app, analyze_skew, analyze_scaling, etc.)
        2. Call appropriate MCP tool
        3. Format response using appropriate formatter
        4. Update session state
        
        Args:
            message: User message text
            history: Chat history (list of user/bot message pairs)
            session_state: Session state dictionary
        
        Returns:
            Tuple of (response_text, updated_session_state)
        """
        try:
            # Detect user intent
            intent_result = detect_intent(message)
            intent = intent_result.get("intent")
            params = intent_result.get("params", {})
            
            # Route based on intent
            if intent == "analyze_app":
                app_id = params.get("application_id")
                result = await mcp_client.call_tool(
                    "get_application_analysis",
                    {"application_id": app_id}
                )
                response = format_app_analysis(result)
                session_state["current_app_id"] = app_id
            
            elif intent == "analyze_skew":
                app_id = params.get("application_id")
                result = await mcp_client.call_tool(
                    "analyze_skew",
                    {"application_id": app_id}
                )
                response = format_skew_analysis(result)
                session_state["current_app_id"] = app_id
            
            elif intent == "analyze_scaling":
                app_id = params.get("application_id")
                result = await mcp_client.call_tool(
                    "analyze_scaling_impact",
                    {"application_id": app_id}
                )
                response = format_scaling_analysis(result)
                session_state["current_app_id"] = app_id
            
            elif intent == "show_bad_apps":
                result = await mcp_client.call_tool(
                    "get_bad_practice_applications",
                    {"min_violations": params.get("min_violations", 3)}
                )
                response = _format_app_list(result, "Applications with Bad Practices")
            
            elif intent == "show_recent_apps":
                result = await mcp_client.call_tool(
                    "get_recent_applications",
                    {"hours": params.get("hours", 24)}
                )
                response = _format_app_list(result, f"Recent Applications (Last {params.get('hours', 24)}h)")
            
            elif intent == "show_driver_heavy":
                result = await mcp_client.call_tool(
                    "get_driver_heavy_applications",
                    {}
                )
                response = _format_app_list(result, "Driver-Heavy Applications")
            
            elif intent == "show_memory_intensive":
                result = await mcp_client.call_tool(
                    "get_memory_intensive_applications",
                    {}
                )
                response = _format_app_list(result, "Memory-Intensive Applications")
            
            elif intent == "general_chat":
                # General chat - could be RAG query or dynamic KQL
                result = await mcp_client.call_tool(
                    "chat",
                    {"message": message, "session_id": mcp_client.session_id}
                )
                response = result.get("response", "I couldn't process that request.")
            
            else:
                response = "I'm not sure how to help with that. Try asking about a specific application or requesting a list of applications."
            
            return response, session_state
        
        except Exception as e:
            error_msg = f"""
### ⚠️ Error Processing Request

**Error:** {str(e)}

**Troubleshooting:**
- Verify MCP server is running at `{mcp_client.server_url}`
- Check application ID format (e.g., `application_1771438258399_0001`)
- Ensure Kusto database has data for the requested query

**Need Help?** Try: `analyze application_1771438258399_0001`
"""
            return error_msg, session_state
    
    def _format_app_list(result: Dict[str, Any], title: str) -> str:
        """Format list of applications as markdown table."""
        apps = result.get("applications", [])
        
        if not apps:
            return f"### {title}\n\nNo applications found matching your criteria."
        
        md = f"### {title}\n\n"
        md += f"**Total Applications:** {len(apps)}\n\n"
        md += "| App ID | App Name | Duration | Status |\n"
        md += "| --- | --- | --- | --- |\n"
        
        for app in apps[:20]:
            app_id = app.get("app_id", "unknown")[:50]
            app_name = app.get("app_name", "Unknown")[:40]
            duration = app.get("duration", 0)
            
            # Format duration
            duration_min = int(duration // 60)
            duration_sec = int(duration % 60)
            duration_str = f"{duration_min}m {duration_sec}s"
            
            # Status indicator based on metrics
            health_score = app.get("health_score", 0)
            if health_score >= 80:
                status = "🟢 Healthy"
            elif health_score >= 40:
                status = "🟡 Warning"
            else:
                status = "🔴 Critical"
            
            md += f"| `{app_id}` | {app_name} | {duration_str} | {status} |\n"
        
        if len(apps) > 20:
            md += f"\n*Showing top 20 of {len(apps)} applications*\n"
        
        md += f"\n💡 **Tip:** Click on an app ID to analyze it: `analyze <app_id>`\n"
        
        return md
    
    # Define Gradio interface
    with gr.Blocks(css=custom_css, theme=gr.themes.Soft(primary_hue="cyan")) as app:
        gr.Markdown(
            """
            # 🔥 Fabric Spark Advisor
            
            AI-powered Spark performance analysis for Microsoft Fabric workloads.
            
            **Ask me about:**
            - `analyze application_1771438258399_0001` - Full application analysis
            - `are there any skews in application_123` - Skew detection
            - `will adding executors help application_123` - Scaling impact
            - `show bad apps` - List problematic applications
            - `show recent apps` - Recent applications
            """,
            elem_classes=["header"]
        )
        
        # Session state
        session_state = gr.State({"current_app_id": None, "session_id": mcp_client.session_id})
        
        # Chatbot component
        chatbot = gr.Chatbot(
            label="Spark Advisor Chat",
            height=chatbot_height,
            show_copy_button=True,
            render_markdown=True,
            bubble_full_width=False,
            elem_classes=["chatbot"]
        )
        
        # Chat interface
        with gr.Row():
            msg = gr.Textbox(
                label="Your Question",
                placeholder="Ask about Spark applications, performance issues, or best practices...",
                lines=2,
                scale=4
            )
            submit_btn = gr.Button("Ask", variant="primary", scale=1)
        
        # Example queries
        gr.Examples(
            examples=[
                "analyze application_1771438258399_0001",
                "show applications with bad practices",
                "are there any skews in application_1771438258399_0001",
                "will adding more executors improve performance for application_1771438258399_0001",
                "show recent apps",
            ],
            inputs=[msg],
            label="Example Questions"
        )
        
        # Connection status
        gr.Markdown(
            f"""
            ---
            **MCP Server:** `{mcp_client.server_url}` | **Session:** `{mcp_client.session_id[:16]}...`
            """,
            elem_classes=["footer"]
        )
        
        # Event handlers
        async def submit_message(message, history, state):
            """Handle message submission."""
            if not message.strip():
                return history, "", state
            
            # Add user message to history
            history = history + [[message, None]]
            
            # Get bot response
            response, new_state = await chat_handler(message, history, state)
            
            # Update history with bot response
            history[-1][1] = response
            
            return history, "", new_state
        
        msg.submit(
            submit_message,
            inputs=[msg, chatbot, session_state],
            outputs=[chatbot, msg, session_state]
        )
        
        submit_btn.click(
            submit_message,
            inputs=[msg, chatbot, session_state],
            outputs=[chatbot, msg, session_state]
        )
    
    return app
