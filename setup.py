# -*- coding: utf-8 -*-
"""
OptGraph - Production-Grade Agent Orchestration Framework
"""

from setuptools import setup, find_packages

setup(
    name="optgraph",
    version="0.1.0",
    description="Production-grade optimizations for LangGraph agents",
    author="OptGraph Team",
    packages=find_packages(),
    install_requires=[
        "langgraph>=0.2.0",
        "langchain-core>=0.3.0",
        "langchain-openai>=0.2.0",
    ],
    python_requires=">=3.8",
)
