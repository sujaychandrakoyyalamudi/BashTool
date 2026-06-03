"""
BashTool - A secure, sandboxed bash execution tool for LLM agents.

This package provides a LangChain-compatible tool for executing shell commands
in a controlled environment with proper security measures.
"""

from bashtool.core import BashTool, BashSession
from bashtool.langchain_tool import create_bash_langchain_tool

__version__ = "0.1.0"
__all__ = ["BashTool", "BashSession", "create_bash_langchain_tool"]
