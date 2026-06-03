"""
Core BashTool implementation with sandboxing and security features.

This module provides the main BashTool class for executing shell commands
in a controlled environment with proper security measures.
"""

import os
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import re

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Result of a command execution."""
    stdout: str
    stderr: str
    exit_code: int
    command: str
    working_dir: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exitCode": self.exit_code,
            "command": self.command,
            "working_dir": self.working_dir
        }


class BashTool:
    """
    Secure bash execution tool for LLM agents.
    
    Features:
    - Command execution with stdout/stderr/exit_code
    - File I/O within workspace
    - Directory listing and context
    - Input validation and sanitization
    - Security controls (path restrictions, command filtering)
    - Audit logging
    """
    
    # Dangerous commands that should be blocked or require approval
    DANGEROUS_COMMANDS = [
        r'rm\s+-rf\s+/',  # rm -rf /
        r'mkfs',  # Filesystem creation
        r'dd\s+if=',  # dd writing to devices
        r'>\s*/dev/',  # Writing to devices
        r'chmod\s+777\s+/',  # Dangerous permissions
        r'sudo',  # Privilege escalation
        r'su\s+',  # Switch user
        r'curl.*\|\s*bash',  # Curl pipe to bash
        r'wget.*\|\s*bash',  # Wget pipe to bash
        r':\(\)\{',  # Fork bomb
    ]
    
    def __init__(
        self,
        workspace: str = "/workspace",
        allow_network: bool = False,
        block_dangerous: bool = True,
        max_output_length: int = 10000,
        timeout: int = 60,
        log_file: Optional[str] = None
    ):
        """
        Initialize the BashTool.
        
        Args:
            workspace: Root directory for file operations (sandbox boundary)
            allow_network: Whether to allow network access (default: False)
            block_dangerous: Whether to block dangerous commands (default: True)
            max_output_length: Maximum length of stdout/stderr to return
            timeout: Command execution timeout in seconds
            log_file: Path to audit log file (optional)
        """
        self.workspace = Path(workspace).resolve()
        self.allow_network = allow_network
        self.block_dangerous = block_dangerous
        self.max_output_length = max_output_length
        self.timeout = timeout
        self.log_file = Path(log_file) if log_file else None
        
        # Ensure workspace exists
        self.workspace.mkdir(parents=True, exist_ok=True)
        
        # Compile dangerous command patterns
        self.dangerous_patterns = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.DANGEROUS_COMMANDS
        ]
        
        logger.info(f"BashTool initialized with workspace: {self.workspace}")
    
    def _validate_command(self, command: str) -> bool:
        """
        Validate command for safety.
        
        Args:
            command: The shell command to validate
            
        Returns:
            True if command is safe, False otherwise
            
        Raises:
            ValueError: If command is dangerous or invalid
        """
        if not isinstance(command, str):
            raise ValueError("Command must be a string")
        
        if len(command) > 10000:
            raise ValueError("Command too long (max 10000 characters)")
        
        if self.block_dangerous:
            for pattern in self.dangerous_patterns:
                if pattern.search(command):
                    logger.warning(f"Blocked dangerous command: {command}")
                    raise ValueError(
                        f"Command blocked for security reasons: {command}"
                    )
        
        return True
    
    def _validate_path(self, path: str) -> Path:
        """
        Validate and resolve path within workspace.
        
        Args:
            path: Path to validate
            
        Returns:
            Resolved Path object
            
        Raises:
            ValueError: If path is outside workspace
        """
        # Resolve the path (handle .., symlinks, etc.)
        resolved = (self.workspace / path).resolve()
        
        # Check if resolved path is within workspace
        try:
            resolved.relative_to(self.workspace)
        except ValueError:
            raise ValueError(
                f"Path '{path}' resolves outside workspace: {resolved}"
            )
        
        return resolved
    
    def _sanitize_output(self, text: str) -> str:
        """
        Sanitize output by truncating if necessary.
        
        Args:
            text: Output text to sanitize
            
        Returns:
            Sanitized text
        """
        if len(text) > self.max_output_length:
            return text[:self.max_output_length] + "\n... [truncated]"
        return text
    
    def _log_command(
        self, 
        command: str, 
        result: CommandResult,
        session_id: Optional[str] = None
    ):
        """
        Log command execution for auditing.
        
        Args:
            command: Executed command
            result: Command result
            session_id: Optional session identifier
        """
        if not self.log_file:
            return
        
        log_entry = {
            "timestamp": str(os.popen("date -Iseconds").read().strip()),
            "session_id": session_id,
            "command": command,
            "exit_code": result.exit_code,
            "stdout_preview": result.stdout[:200] if result.stdout else "",
            "stderr_preview": result.stderr[:200] if result.stderr else "",
            "working_dir": str(result.working_dir)
        }
        
        try:
            with open(self.log_file, 'a') as f:
                import json
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def execute(
        self,
        command: str,
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        session_id: Optional[str] = None
    ) -> CommandResult:
        """
        Execute a shell command.
        
        Args:
            command: Shell command to execute
            working_dir: Working directory (relative to workspace)
            env: Additional environment variables
            session_id: Optional session identifier for logging
            
        Returns:
            CommandResult with stdout, stderr, exit_code
            
        Raises:
            ValueError: If command is invalid or dangerous
            TimeoutError: If command exceeds timeout
        """
        # Validate command
        self._validate_command(command)
        
        # Determine working directory
        if working_dir:
            workdir = self._validate_path(working_dir)
        else:
            workdir = self.workspace
        
        # Prepare environment
        exec_env = os.environ.copy()
        # Remove sensitive variables
        sensitive_vars = [
            'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN',
            'PRIVATE_KEY', 'PASSWORD', 'TOKEN'
        ]
        for var in sensitive_vars:
            exec_env.pop(var, None)
        
        # Add custom environment
        if env:
            exec_env.update(env)
        
        # Disable network if configured
        if not self.allow_network:
            # This is a basic check; real sandboxing requires more
            exec_env['BASHTOOL_NO_NETWORK'] = '1'
        
        logger.info(f"Executing command: {command} in {workdir}")
        
        try:
            # Execute command
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=str(workdir),
                env=exec_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            try:
                stdout, stderr = process.communicate(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                raise TimeoutError(
                    f"Command timed out after {self.timeout} seconds"
                )
            
            result = CommandResult(
                stdout=self._sanitize_output(stdout),
                stderr=self._sanitize_output(stderr),
                exit_code=process.returncode,
                command=command,
                working_dir=str(workdir)
            )
            
            # Log execution
            self._log_command(command, result, session_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise
    
    def read_file(self, path: str) -> str:
        """
        Read a file within the workspace.
        
        Args:
            path: Path to file (relative to workspace)
            
        Returns:
            File contents
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If path is invalid
        """
        file_path = self._validate_path(path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        if not file_path.is_file():
            raise ValueError(f"Not a file: {path}")
        
        with open(file_path, 'r') as f:
            return f.read()
    
    def write_file(self, path: str, content: str) -> None:
        """
        Write content to a file within the workspace.
        
        Args:
            path: Path to file (relative to workspace)
            content: Content to write
            
        Raises:
            ValueError: If path is invalid
        """
        file_path = self._validate_path(path)
        
        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        logger.info(f"Wrote file: {path}")
    
    def list_directory(self, path: str = ".") -> List[str]:
        """
        List contents of a directory.
        
        Args:
            path: Directory path (relative to workspace)
            
        Returns:
            List of file/directory names
            
        Raises:
            NotADirectoryError: If path is not a directory
            ValueError: If path is invalid
        """
        dir_path = self._validate_path(path)
        
        if not dir_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")
        
        return sorted([item.name for item in dir_path.iterdir()])
    
    def get_workspace_info(self) -> Dict[str, Any]:
        """
        Get information about the workspace.
        
        Returns:
            Dictionary with workspace details
        """
        files = self.list_directory(".")
        return {
            "workspace": str(self.workspace),
            "files": files,
            "allow_network": self.allow_network,
            "timeout": self.timeout
        }


class BashSession:
    """
    Persistent bash session for multi-step workflows.
    
    Maintains state across multiple command executions.
    """
    
    def __init__(
        self,
        workspace: str = "/workspace",
        session_id: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize a persistent bash session.
        
        Args:
            workspace: Root directory for file operations
            session_id: Unique session identifier
            **kwargs: Additional arguments passed to BashTool
        """
        import uuid
        self.session_id = session_id or str(uuid.uuid4())
        self.tool = BashTool(workspace=workspace, **kwargs)
        self.history: List[CommandResult] = []
        self.active = True
        
        logger.info(f"BashSession created: {self.session_id}")
    
    def execute(
        self,
        command: str,
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None
    ) -> CommandResult:
        """
        Execute a command in this session.
        
        Args:
            command: Shell command to execute
            working_dir: Working directory (relative to workspace)
            env: Additional environment variables
            
        Returns:
            CommandResult with stdout, stderr, exit_code
            
        Raises:
            RuntimeError: If session is not active
        """
        if not self.active:
            raise RuntimeError("Session is not active")
        
        result = self.tool.execute(
            command=command,
            working_dir=working_dir,
            env=env,
            session_id=self.session_id
        )
        
        self.history.append(result)
        return result
    
    def get_history(self) -> List[Dict[str, Any]]:
        """
        Get command history for this session.
        
        Returns:
            List of command results as dictionaries
        """
        return [result.to_dict() for result in self.history]
    
    def terminate(self):
        """Terminate the session."""
        self.active = False
        logger.info(f"BashSession terminated: {self.session_id}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure session is terminated."""
        self.terminate()
