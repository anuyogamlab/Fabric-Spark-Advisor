"""
Fabric Spark Advisor UI
~~~~~~~~~~~~~~~~~~~~~~~
Zero-dependency helper that embeds the Spark Advisor chat UI inside a
Fabric / Jupyter notebook cell.

Usage::

    from fabric_spark_advisor_ui import show

    show()                                                  # default ACA deployment
    show("https://<your-app>.azurecontainerapps.io")        # your own deployment
    show("http://localhost:7432")                           # local dev server
    show(url="...", height=900, theme="light")              # full options
"""

__version__ = "0.2.0"

_DEFAULT_URL = "https://spark-advisor-mcp.livelyground-08e83d90.eastus.azurecontainerapps.io"


def show(
    url: str = _DEFAULT_URL,
    height: int = 700,
    title: str = "Fabric Spark Advisor",
    subtitle: str = "AI-powered Spark optimization — MCP · RAG · LLM Judge",
    theme: str = "dark",
) -> None:
    """
    Embed the Spark Advisor chat UI inside a Fabric or Jupyter notebook.

    Args:
        url:      Base URL of the deployed Spark Advisor container.
                  Can be just the host (``https://your-app.azurecontainerapps.io``)
                  or the full path including ``/chat.html``.
                  Defaults to the shared Azure Container Apps instance.
        height:   iframe height in pixels (default 700).
        title:    Header title text (default "Fabric Spark Advisor").
        subtitle: Sub-heading text.
        theme:    ``"dark"`` (default) or ``"light"``.

    Examples::

        from fabric_spark_advisor_ui import show

        show()
        show("https://my-app.azurecontainerapps.io")
        show("https://my-app.azurecontainerapps.io", height=900, theme="light")
        show(url="http://localhost:7432", title="Dev Server")
    """
    # Normalise: strip trailing slash, append /chat.html if not already present
    base = url.rstrip("/")
    chat_url = base if base.endswith("/chat.html") else f"{base}/chat.html"

    # Try fabric_spark_advisor.show_ui first (supports title arg)
    try:
        from fabric_spark_advisor import show_ui
        show_ui(url=chat_url, height=height, title=title)
        return
    except ImportError:
        pass

    # Fallback: render inline HTML directly (no extra dependencies needed)
    _render_html(chat_url, height, title, subtitle, theme)


def _render_html(chat_url: str, height: int, title: str, subtitle: str, theme: str) -> None:
    """Render a self-contained iframe card without requiring fabric_spark_advisor."""
    import random

    uid = f"fsa{random.randint(100000, 999999)}"
    accent = "#1a73e8" if theme == "light" else "#0f3460"
    bg = "#ffffff" if theme == "light" else "#16213e"
    text_color = "#111111" if theme == "light" else "#e0e0e0"
    sub_color = "#555555" if theme == "light" else "#a0a0b0"

    html = f"""
<div id="{uid}_card" style="font-family:sans-serif;border-radius:12px;
     overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.3);background:{bg};
     max-width:100%;margin:8px 0;">
  <div style="background:linear-gradient(135deg,{accent},{accent}aa);
       padding:14px 20px;display:flex;align-items:center;justify-content:space-between;">
    <div>
      <span style="font-size:1.15em;font-weight:700;color:#fff;">⚡ {title}</span><br/>
      <span style="font-size:.8em;color:#ffffffcc;">{subtitle}</span>
    </div>
    <div style="display:flex;align-items:center;gap:10px;">
      <span id="{uid}_dot" style="width:10px;height:10px;border-radius:50%;
            background:#f5a623;display:inline-block;"></span>
      <a href="{chat_url}" target="_blank"
         style="color:#fff;font-size:.8em;text-decoration:none;
                border:1px solid #ffffff55;padding:3px 8px;border-radius:4px;">
        Open ↗
      </a>
    </div>
  </div>
  <div style="position:relative;background:{bg};">
    <div id="{uid}_spinner" style="position:absolute;inset:0;display:flex;
         align-items:center;justify-content:center;background:{bg};">
      <div style="width:36px;height:36px;border:4px solid {accent}44;
           border-top-color:{accent};border-radius:50%;
           animation:{uid}_spin 0.8s linear infinite;"></div>
    </div>
    <iframe id="{uid}_frame" src="{chat_url}"
            width="100%" height="{height}" frameborder="0"
            style="display:block;"
            onload="
              document.getElementById('{uid}_spinner').style.display='none';
              document.getElementById('{uid}_dot').style.background='#34a853';
            ">
    </iframe>
  </div>
  <div style="padding:6px 16px;font-size:.72em;color:{sub_color};
       border-top:1px solid {accent}33;">
    ☁ Azure Container Apps · Kusto · GPT-4o · RAG &nbsp;|&nbsp;
    fabric-spark-advisor-ui v{__version__}
  </div>
</div>
<style>
  @keyframes {uid}_spin {{ to {{ transform: rotate(360deg); }} }}
</style>
"""

    # Display via the best available method
    try:
        # Microsoft Fabric / Databricks built-in
        displayHTML(html)  # noqa: F821
        return
    except NameError:
        pass
    try:
        from IPython.display import HTML, display
        display(HTML(html))
        return
    except ImportError:
        pass
    print(html)
