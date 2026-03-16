"""
Fabric Spark Advisor UI
~~~~~~~~~~~~~~~~~~~~~~~
Minimal helper that embeds the Spark Advisor chat UI inside a
Fabric / Jupyter notebook cell.

Usage::

    from fabric_spark_advisor_ui import show

    show()                                              # default ACA deployment
    show("https://<your-app>.azurecontainerapps.io")   # your own deployment
    show("http://localhost:7432")                       # local dev server
"""

_DEFAULT_URL = "https://spark-advisor-mcp.livelyground-08e83d90.eastus.azurecontainerapps.io"


def show(url: str = _DEFAULT_URL, height: int = 700) -> None:
    """
    Embed the Spark Advisor chat UI inside a Fabric or Jupyter notebook.

    Args:
        url:    Base URL of the deployed Spark Advisor container.
                Can be just the host (``https://your-app.azurecontainerapps.io``)
                or the full path including ``/chat.html``.
                Defaults to the shared Azure Container Apps instance.
        height: iframe height in pixels (default 700).

    Examples::

        from fabric_spark_advisor_ui import show

        show()
        show("https://my-app.azurecontainerapps.io")
        show("https://my-app.azurecontainerapps.io", height=900)
    """
    # Normalise: strip trailing slash, append /chat.html if not already present
    base = url.rstrip("/")
    chat_url = base if base.endswith("/chat.html") else f"{base}/chat.html"

    # Delegate to fabric_spark_advisor.show_ui which renders the full iframe card
    try:
        from fabric_spark_advisor import show_ui
        show_ui(url=chat_url, height=height)
    except ImportError:
        # Fallback: plain IFrame if fabric_spark_advisor is not installed
        try:
            from IPython.display import IFrame, display
            display(IFrame(src=chat_url, width="100%", height=height))
        except ImportError:
            raise RuntimeError(
                "Install fabric_spark_advisor or IPython to use show(). "
                f"Chat URL: {chat_url}"
            )
