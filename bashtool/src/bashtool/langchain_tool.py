"""
LangChain integration for BashTool.

This module provides LangChain-compatible tool wrappers for the BashTool.
"""

from typing import Type, Dict, Any, Optional
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from bashtool.core import BashTool, BashSession, CommandResult


class BashInput(BaseModel):
    """Input schema for bash command execution."""
    command: str = Field(
        ...,
        description="The shell command to execute",
        min_length=1,
        max_length=10000
    )
    working_dir: Optional[str] = Field(
        default=None,
        description="Working directory (relative to workspace)"
    )


class BashLangChainTool(BaseTool):
    """
    LangChain tool wrapper for BashTool.
    
    This tool allows LLM agents to execute shell commands safely
    within a controlled workspace environment.
    """
    
    name: str = "bash"
    description: str = (
        "Execute a shell command in the workspace environment. "
        "Use this tool to run commands like 'ls', 'cat', 'grep', 'find', etc. "
        "The command runs in a sandboxed environment with restricted access. "
        "Returns stdout, stderr, and exit code."
    )
    args_schema: Type[BaseModel] = BashInput
    
    # Internal bash tool instance
    _bash_tool: BashTool = None
    
    def __init__(
        self,
        workspace: str = "/workspace",
        allow_network: bool = False,
        block_dangerous: bool = True,
        max_output_length: int = 10000,
        timeout: int = 60,
        log_file: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the LangChain bash tool.
        
        Args:
            workspace: Root directory for file operations
            allow_network: Whether to allow network access
            block_dangerous: Whether to block dangerous commands
            max_output_length: Maximum length of output to return
            timeout: Command execution timeout in seconds
            log_file: Path to audit log file
            **kwargs: Additional arguments
        """
        super().__init__(**kwargs)
        self._bash_tool = BashTool(
            workspace=workspace,
            allow_network=allow_network,
            block_dangerous=block_dangerous,
            max_output_length=max_output_length,
            timeout=timeout,
            log_file=log_file
        )
    
    def _run(
        self,
        command: str,
        working_dir: Optional[str] = None
    ) -> str:
        """
        Execute the command and return formatted output.
        
        Args:
            command: Shell command to execute
            working_dir: Working directory (optional)
            
        Returns:
            Formatted string with command results
        """
        try:
            result = self._bash_tool.execute(
                command=command,
                working_dir=working_dir
            )
            
            # Format output for LLM consumption
            output_parts = []
            
            if result.stdout:
                output_parts.append(f"STDOUT:\n{result.stdout}")
            
            if result.stderr:
                output_parts.append(f"STDERR:\n{result.stderr}")
            
            output_parts.append(f"EXIT_CODE: {result.exit_code}")
            
            if result.exit_code != 0:
                output_parts.append(
                    f"\nCommand failed with exit code {result.exit_code}"
                )
            
            return "\n".join(output_parts)
            
        except ValueError as e:
            return f"ERROR: {str(e)}"
        except TimeoutError as e:
            return f"ERROR: {str(e)}"
        except Exception as e:
            return f"ERROR: Unexpected error - {str(e)}"
    
    async def _arun(
        self,
        command: str,
        working_dir: Optional[str] = None
    ) -> str:
        """
        Async version of _run (currently synchronous implementation).
        
        Args:
            command: Shell command to execute
            working_dir: Working directory (optional)
            
        Returns:
            Formatted string with command results
        """
        # For now, delegate to sync version
        # In production, you'd use asyncio.create_subprocess_shell
        return self._run(command, working_dir)


class ReadFileInput(BaseModel):
    """Input schema for reading files."""
    path: str = Field(
        ...,
        description="Path to the file (relative to workspace)",
        min_length=1
    )


class ReadFileLangChainTool(BaseTool):
    """LangChain tool for reading files within the workspace."""
    
    name: str = "read_file"
    description: str = (
        "Read the contents of a file within the workspace. "
        "Use this to inspect file contents, configuration files, source code, etc. "
        "The path must be relative to the workspace directory."
    )
    args_schema: Type[BaseModel] = ReadFileInput
    
    _bash_tool: BashTool = None
    
    def __init__(self, workspace: str = "/workspace", **kwargs):
        super().__init__(**kwargs)
        self._bash_tool = BashTool(workspace=workspace)
    
    def _run(self, path: str) -> str:
        """Read file and return contents."""
        try:
            content = self._bash_tool.read_file(path)
            return f"FILE CONTENT ({path}):\n{content}"
        except FileNotFoundError as e:
            return f"ERROR: {str(e)}"
        except Exception as e:
            return f"ERROR: {str(e)}"
    
    async def _arun(self, path: str) -> str:
        """Async version of _run."""
        return self._run(path)


class WriteFileInput(BaseModel):
    """Input schema for writing files."""
    path: str = Field(
        ...,
        description="Path to the file (relative to workspace)",
        min_length=1
    )
    content: str = Field(
        ...,
        description="Content to write to the file"
    )


class WriteFileLangChainTool(BaseTool):
    """LangChain tool for writing files within the workspace."""
    
    name: str = "write_file"
    description: str = (
        "Write content to a file within the workspace. "
        "Use this to create or modify files, such as source code, configs, etc. "
        "The path must be relative to the workspace directory. "
        "Parent directories will be created automatically if needed."
    )
    args_schema: Type[BaseModel] = WriteFileInput
    
    _bash_tool: BashTool = None
    
    def __init__(self, workspace: str = "/workspace", **kwargs):
        super().__init__(**kwargs)
        self._bash_tool = BashTool(workspace=workspace)
    
    def _run(self, path: str, content: str) -> str:
        """Write file and return confirmation."""
        try:
            self._bash_tool.write_file(path, content)
            return f"SUCCESS: File written to {path}"
        except Exception as e:
            return f"ERROR: {str(e)}"
    
    async def _arun(self, path: str, content: str) -> str:
        """Async version of _run."""
        return self._run(path, content)


class ListDirectoryInput(BaseModel):
    """Input schema for listing directories."""
    path: str = Field(
        default=".",
        description="Directory path to list (relative to workspace)"
    )


class ListDirectoryLangChainTool(BaseTool):
    """LangChain tool for listing directory contents."""
    
    name: str = "list_directory"
    description: str = (
        "List the contents of a directory within the workspace. "
        "Returns a sorted list of files and subdirectories. "
        "Use '.' for the root workspace directory."
    )
    args_schema: Type[BaseModel] = ListDirectoryInput
    
    _bash_tool: BashTool = None
    
    def __init__(self, workspace: str = "/workspace", **kwargs):
        super().__init__(**kwargs)
        self._bash_tool = BashTool(workspace=workspace)
    
    def _run(self, path: str = ".") -> str:
        """List directory contents."""
        try:
            items = self._bash_tool.list_directory(path)
            if not items:
                return f"Directory '{path}' is empty"
            return f"DIRECTORY LISTING ({path}):\n" + "\n".join(items)
        except Exception as e:
            return f"ERROR: {str(e)}"
    
    async def _arun(self, path: str = ".") -> str:
        """Async version of _run."""
        return self._run(path)


def create_bash_langchain_tool(
    workspace: str = "/workspace",
    include_file_tools: bool = True,
    **kwargs
) -> list:
    """
    Create LangChain tools for bash execution.
    
    Args:
        workspace: Root directory for file operations
        include_file_tools: Whether to include read/write/list tools
        **kwargs: Additional arguments passed to BashLangChainTool
        
    Returns:
        List of LangChain tool instances
    """
    tools = [BashLangChainTool(workspace=workspace, **kwargs)]
    
    if include_file_tools:
        tools.append(ReadFileLangChainTool(workspace=workspace))
        tools.append(WriteFileLangChainTool(workspace=workspace))
        tools.append(ListDirectoryLangChainTool(workspace=workspace))
    
    return tools
