"""
Test suite for BashTool.

This module contains unit tests and integration tests for the BashTool package.
"""

import pytest
import tempfile
import os
from pathlib import Path

from bashtool.core import BashTool, BashSession, CommandResult


class TestBashTool:
    """Tests for the BashTool class."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def bash_tool(self, temp_workspace):
        """Create a BashTool instance with temporary workspace."""
        return BashTool(workspace=temp_workspace)
    
    def test_echo_command(self, bash_tool):
        """Test basic echo command execution."""
        result = bash_tool.execute("echo hello")
        
        assert result.exit_code == 0
        assert result.stdout.strip() == "hello"
        assert result.stderr == ""
    
    def test_failed_command(self, bash_tool):
        """Test handling of failed commands."""
        result = bash_tool.execute("ls /nonexistent_directory_xyz123")
        
        assert result.exit_code != 0
        assert "No such file" in result.stderr or "cannot access" in result.stderr
    
    def test_working_directory(self, bash_tool, temp_workspace):
        """Test command execution in specific working directory."""
        # Create a subdirectory
        subdir = Path(temp_workspace) / "subdir"
        subdir.mkdir()
        
        # Execute command in subdirectory
        result = bash_tool.execute("pwd", working_dir="subdir")
        
        assert result.exit_code == 0
        assert "subdir" in result.stdout
    
    def test_dangerous_command_blocked(self, bash_tool):
        """Test that dangerous commands are blocked."""
        with pytest.raises(ValueError) as exc_info:
            bash_tool.execute("rm -rf /")
        
        assert "blocked for security reasons" in str(exc_info.value)
    
    def test_path_traversal_blocked(self, bash_tool):
        """Test that path traversal outside workspace is blocked."""
        with pytest.raises(ValueError) as exc_info:
            bash_tool.read_file("../../etc/passwd")
        
        assert "resolves outside workspace" in str(exc_info.value)
    
    def test_read_write_file(self, bash_tool):
        """Test file read/write operations."""
        # Write a file
        bash_tool.write_file("test.txt", "Hello, World!")
        
        # Read it back
        content = bash_tool.read_file("test.txt")
        
        assert content == "Hello, World!"
    
    def test_list_directory(self, bash_tool):
        """Test directory listing."""
        # Create some files
        bash_tool.write_file("file1.txt", "content1")
        bash_tool.write_file("file2.txt", "content2")
        
        # List directory
        items = bash_tool.list_directory(".")
        
        assert "file1.txt" in items
        assert "file2.txt" in items
    
    def test_command_timeout(self, temp_workspace):
        """Test command timeout handling."""
        tool = BashTool(workspace=temp_workspace, timeout=2)
        
        with pytest.raises(TimeoutError):
            # This should timeout
            tool.execute("sleep 10")
    
    def test_output_truncation(self, temp_workspace):
        """Test output truncation for long outputs."""
        tool = BashTool(workspace=temp_workspace, max_output_length=50)
        
        result = tool.execute("echo 'A' * 100")
        
        assert len(result.stdout) <= 65  # 50 + truncation message
    
    def test_environment_sanitization(self, bash_tool):
        """Test that sensitive environment variables are removed."""
        # Set a sensitive variable
        os.environ['AWS_SECRET_ACCESS_KEY'] = 'secret123'
        
        try:
            # Execute command that would expose env
            result = bash_tool.execute("env")
            
            # Sensitive vars should not be in output
            assert 'AWS_SECRET_ACCESS_KEY' not in result.stdout
        finally:
            # Clean up
            os.environ.pop('AWS_SECRET_ACCESS_KEY', None)
    
    def test_workspace_info(self, bash_tool):
        """Test workspace information retrieval."""
        info = bash_tool.get_workspace_info()
        
        assert "workspace" in info
        assert "files" in info
        assert "allow_network" in info


class TestBashSession:
    """Tests for the BashSession class."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_session_history(self, temp_workspace):
        """Test that session maintains command history."""
        with BashSession(workspace=temp_workspace) as session:
            session.execute("echo cmd1")
            session.execute("echo cmd2")
            
            history = session.get_history()
            
            assert len(history) == 2
            assert "cmd1" in history[0]["command"]
            assert "cmd2" in history[1]["command"]
    
    def test_session_termination(self, temp_workspace):
        """Test session termination prevents further execution."""
        session = BashSession(workspace=temp_workspace)
        session.terminate()
        
        with pytest.raises(RuntimeError) as exc_info:
            session.execute("echo test")
        
        assert "not active" in str(exc_info.value)
    
    def test_session_context_manager(self, temp_workspace):
        """Test session as context manager."""
        with BashSession(workspace=temp_workspace) as session:
            result = session.execute("echo test")
            assert result.exit_code == 0
        
        # Session should be terminated after context exit
        assert not session.active


class TestLangChainTools:
    """Tests for LangChain tool wrappers."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_bash_tool_creation(self, temp_workspace):
        """Test creating LangChain bash tool."""
        from bashtool.langchain_tool import BashLangChainTool
        
        tool = BashLangChainTool(workspace=temp_workspace)
        
        assert tool.name == "bash"
        assert "command" in tool.args_schema.model_fields
    
    def test_bash_tool_execution(self, temp_workspace):
        """Test LangChain bash tool execution."""
        from bashtool.langchain_tool import BashLangChainTool
        
        tool = BashLangChainTool(workspace=temp_workspace)
        result = tool._run(command="echo hello")
        
        assert "STDOUT:" in result
        assert "hello" in result
        assert "EXIT_CODE: 0" in result
    
    def test_create_tools_helper(self, temp_workspace):
        """Test the create_bash_langchain_tool helper function."""
        from bashtool.langchain_tool import create_bash_langchain_tool
        
        tools = create_bash_langchain_tool(workspace=temp_workspace)
        
        # Should have at least bash tool
        assert len(tools) >= 1
        
        # Check tool names
        tool_names = [t.name for t in tools]
        assert "bash" in tool_names
    
    def test_read_file_tool(self, temp_workspace):
        """Test LangChain read_file tool."""
        from bashtool.langchain_tool import ReadFileLangChainTool
        
        # Create a test file
        Path(temp_workspace).joinpath("test.txt").write_text("test content")
        
        tool = ReadFileLangChainTool(workspace=temp_workspace)
        result = tool._run(path="test.txt")
        
        assert "FILE CONTENT" in result
        assert "test content" in result
    
    def test_write_file_tool(self, temp_workspace):
        """Test LangChain write_file tool."""
        from bashtool.langchain_tool import WriteFileLangChainTool
        
        tool = WriteFileLangChainTool(workspace=temp_workspace)
        result = tool._run(path="output.txt", content="new content")
        
        assert "SUCCESS" in result
        
        # Verify file was written
        assert Path(temp_workspace).joinpath("output.txt").read_text() == "new content"
    
    def test_list_directory_tool(self, temp_workspace):
        """Test LangChain list_directory tool."""
        from bashtool.langchain_tool import ListDirectoryLangChainTool
        
        # Create test files
        Path(temp_workspace).joinpath("file1.txt").touch()
        Path(temp_workspace).joinpath("file2.txt").touch()
        
        tool = ListDirectoryLangChainTool(workspace=temp_workspace)
        result = tool._run(path=".")
        
        assert "DIRECTORY LISTING" in result
        assert "file1.txt" in result
        assert "file2.txt" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
