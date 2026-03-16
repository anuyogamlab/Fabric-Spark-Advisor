"""
Fabric Spark Advisor - AI-Powered Spark Performance Analysis

A lightweight notebook interface for analyzing Apache Spark workloads
running on Microsoft Fabric using expert-defined rules and LLM orchestration.

Usage:
    # Option 1: Connect to remote MCP server (ngrok/Azure/local)
    from fabric_spark_advisor import SparkAdvisor
    
    advisor = SparkAdvisor(mcp_server_url="https://your-server.com")
    advisor.launch()
    
    # Option 2: Run entirely in-notebook (no external server)
    from fabric_spark_advisor import LocalSparkAdvisor
    
    advisor = LocalSparkAdvisor()
    advisor.launch_ui()
"""

__version__ = "0.3.0"
__author__ = "Microsoft"

# Lazy imports — SparkAdvisor/LocalSparkAdvisor pull in httpx and (optionally)
# gradio; don't load them unless the user actually requests them.
def __getattr__(name):
    if name == "SparkAdvisor":
        from .advisor import SparkAdvisor
        return SparkAdvisor
    if name == "LocalSparkAdvisor":
        from .local_advisor import LocalSparkAdvisor
        return LocalSparkAdvisor
    raise AttributeError(f"module 'fabric_spark_advisor' has no attribute {name!r}")

_DEFAULT_URL = "https://spark-advisor-mcp.livelyground-08e83d90.eastus.azurecontainerapps.io/chat.html"


def show_ui(url: str = _DEFAULT_URL, height: int = 700, title: str = "Fabric Spark Advisor") -> None:
    """
    Embed the Spark Advisor chat UI inside a Fabric or Jupyter notebook.

    Renders a polished card with a gradient header, live status indicator,
    animated loading spinner, and an "Open in new tab" button.

    Args:
        url:    Full URL of the chat.html page served by the container.
                Defaults to the shared Azure Container Apps deployment.
        height: iframe height in pixels (default 700).
        title:  Title shown in the header bar (default "Fabric Spark Advisor").

    Example::

        from fabric_spark_advisor import show_ui
        show_ui()                                          # shared ACA instance
        show_ui(height=900)                                # taller window
        show_ui(url="http://localhost:7432/chat.html")     # local dev server
        show_ui(url="https://<your>.azurecontainerapps.io/chat.html")  # your ACA
    """
    import random
    uid = f"fsa{random.randint(100000, 999999)}"

    html = f"""
<style>
@keyframes {uid}-spin  {{ to {{ transform: rotate(360deg); }} }}
@keyframes {uid}-pulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:0.35; }} }}
</style>
<div style="font-family:'Segoe UI',system-ui,-apple-system,sans-serif;
            max-width:100%;border-radius:12px;
            box-shadow:0 4px 20px rgba(0,0,0,0.10);overflow:hidden;margin:4px 0 8px 0;">

  <!-- ── Header bar ── -->
  <div style="display:flex;align-items:center;justify-content:space-between;
              background:linear-gradient(135deg,#0E6DC9 0%,#0050A0 100%);
              padding:13px 18px;">

    <div style="display:flex;align-items:center;gap:12px;">
      <span style="font-size:24px;line-height:1;">&#9889;</span>
      <div>
        <div style="color:#fff;font-size:15px;font-weight:700;letter-spacing:0.2px;">
          {title}
        </div>
        <div style="color:rgba(255,255,255,0.7);font-size:11px;margin-top:2px;">
          AI-Powered Spark Performance Analysis
        </div>
      </div>
    </div>

    <div style="display:flex;align-items:center;gap:8px;">
      <!-- Status pill -->
      <span id="{uid}-status"
            style="display:inline-flex;align-items:center;gap:5px;
                   background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.25);
                   border-radius:20px;padding:4px 11px;
                   color:rgba(255,255,255,0.9);font-size:11px;font-weight:500;">
        <span id="{uid}-dot"
              style="width:7px;height:7px;border-radius:50%;
                     background:#FFC83D;display:inline-block;flex-shrink:0;"></span>
        Loading&#8230;
      </span>

      <!-- Open in tab button -->
      <a href="{url}" target="_blank" rel="noopener"
         style="text-decoration:none;display:inline-flex;align-items:center;gap:5px;
                background:rgba(255,255,255,0.18);border:1px solid rgba(255,255,255,0.35);
                border-radius:7px;padding:6px 13px;
                color:#fff;font-size:12px;font-weight:500;cursor:pointer;">
        Open&nbsp;&#8599;
      </a>
    </div>
  </div>

  <!-- ── Loading overlay ── -->
  <div id="{uid}-loading"
       style="background:#F4F8FF;display:flex;align-items:center;justify-content:center;
              gap:10px;padding:18px;border-left:1px solid #D0E4F7;border-right:1px solid #D0E4F7;">
    <div style="width:18px;height:18px;border-radius:50%;
                border:2.5px solid #C8DCF0;border-top-color:#0E6DC9;
                animation:{uid}-spin 0.75s linear infinite;flex-shrink:0;"></div>
    <span style="color:#5A7FA8;font-size:13px;">Connecting to Spark Advisor&#8230;</span>
  </div>

  <!-- ── iframe ── -->
  <iframe id="{uid}-frame" src="{url}" width="100%" height="{height}"
          style="display:none;border:none;
                 border-left:1px solid #D0E4F7;border-right:1px solid #D0E4F7;"
          allow="clipboard-write"
          onload="
            var l=document.getElementById('{uid}-loading');
            var f=document.getElementById('{uid}-frame');
            var d=document.getElementById('{uid}-dot');
            var s=document.getElementById('{uid}-status');
            if(l) l.style.display='none';
            if(f) f.style.display='block';
            if(d) {{ d.style.background='#2ECC71';
                     d.style.animation='{uid}-pulse 2s ease-in-out infinite'; }}
            if(s) s.innerHTML='<span style=\\'width:7px;height:7px;border-radius:50%;background:#2ECC71;display:inline-block;flex-shrink:0;animation:{uid}-pulse 2s ease-in-out infinite\\'></span>&nbsp;Connected';
          ">
  </iframe>

  <!-- ── Footer ── -->
  <div style="display:flex;align-items:center;justify-content:space-between;
              background:#EBF3FC;border:1px solid #D0E4F7;
              border-radius:0 0 12px 12px;padding:7px 18px;">
    <span style="font-size:10.5px;color:#7A9BBF;letter-spacing:0.2px;">
      &#9729; Azure Container Apps &nbsp;&#183;&nbsp; Kusto &nbsp;&#183;&nbsp; GPT-4o &nbsp;&#183;&nbsp; RAG
    </span>
    <span style="font-size:10.5px;color:#0E6DC9;font-weight:600;">
      fabric-spark-advisor&nbsp;v{__version__}
    </span>
  </div>

</div>"""

    try:
        displayHTML(html)  # type: ignore[name-defined]  # noqa: F821  — Fabric built-in
    except NameError:
        from IPython.display import HTML, display
        display(HTML(html))


__all__ = ["SparkAdvisor", "LocalSparkAdvisor", "show_ui"]
