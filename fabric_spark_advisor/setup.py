"""
Fabric Spark Advisor - Setup Configuration

A lightweight Python package for analyzing Apache Spark workloads
in Microsoft Fabric using expert-defined rules and LLM orchestration.
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="fabric-spark-advisor",
    version="0.1.0",
    author="Microsoft",
    author_email="",
    description="AI-powered Spark performance analysis for Microsoft Fabric",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/microsoft/fabric-spark-advisor",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=[
        "gradio>=4.0.0",
        "httpx>=0.25.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "spark-advisor=fabric_spark_advisor.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
