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

__version__ = "0.1.0"
__author__ = "Microsoft"

from .advisor import SparkAdvisor
from .local_advisor import LocalSparkAdvisor

__all__ = ["SparkAdvisor", "LocalSparkAdvisor"]
