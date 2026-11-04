# BashTool

A Python library that lets an LLM agent run shell commands and read and write files in a workspace directory, with LangChain tool wrappers.

This is the detailed reference. For a short overview, see the [repository README](../README.md).

> **Security notice:** BashTool is not a security sandbox. It runs commands on the host through `/bin/sh`, as the same OS user as your Python process, with the same network access. Its checks (a command deny-list, workspace path checks for the file helpers, and removal of five environment variables) help prevent accidents, but they do not contain a command that sets out to escape them. Run it inside a container or VM with no network access and with resource limits whenever the commands are not fully trusted.

## Features

- **Command execution**: `BashTool.execute` returns a `CommandResult` with `stdout`, `stderr`, `exit_code`, `command`, and `working_dir`. You can pass a `working_dir` inside the workspace and extra `env` variables.
- **Timeout**: default 60 seconds. On timeout the shell process is killed and `TimeoutError` is raised.
- **Output truncation**: stdout and stderr are each cut to `max_output_length` characters (default 10,000), with `\n... [truncated]` appended.
- **Workspace file helpers**: `read_file`, `write_file`, and `list_directory`, limited to paths inside the workspace.
- **Dangerous-command deny-list**: 10 regular expressions, on by default (`block_dangerous=True`).
- **Environment cleanup**: five variable names are removed from the command's environment.
- **Input checks**: the command must be a string of at most 10,000 characters. The LangChain `bash` tool also requires at least one character.
- **Audit log**: optional JSON Lines log of executed commands (`log_file`).
- **Sessions**: `BashSession` runs commands under one session ID and keeps their results as history.
- **LangChain tools**: `bash`, `read_file`, `write_file`, and `list_directory`, built on `langchain_core.tools.BaseTool`.

## Installation

BashTool is not on PyPI. Install it from GitHub; the package lives in the `bashtool/` folder of the repository:

```bash
pip install "git+https://github.com/sujaychandrakoyyalamudi/BashTool.git#subdirectory=bashtool"
```

For development, use an editable install with the test tools (`pytest`, `pytest-asyncio`, `black`, `ruff`, `mypy`):

```bash
git clone https://github.com/sujaychandrakoyyalamudi/BashTool.git
cd BashTool/bashtool
pip install -e ".[dev]"
```

Dependencies are `langchain`, `langchain-core`, and `pydantic` 2. The classifiers in `pyproject.toml` list Python 3.9 to 3.12.

## Usage

### Commands and files

```python
from bashtool import BashTool

tool = BashTool(workspace="./sandbox", timeout=30, log_file="audit.log")

result = tool.execute("ls -la", working_dir=".", env={"GREETING": "hi"})
print(result.exit_code)
print(result.stdout)
print(result.to_dict())  # same fields; the exit code key is "exitCode"

tool.write_file("notes/hello.txt", "Hello, World!")
print(tool.read_file("notes/hello.txt"))
print(tool.list_directory("."))  # ['notes'] in a new workspace; audit.log is written to the current directory
```

### Blocked commands and paths

```python
from bashtool import BashTool

tool = BashTool(workspace="./sandbox")

for command in ("rm -rf /", "curl https://example.com/install.sh | bash", "sudo rm file"):
    try:
        tool.execute(command)
    except ValueError as err:
        print(err)  # Command blocked for security reasons: ...

try:
    tool.read_file("../../etc/passwd")
except ValueError as err:
    print(err)  # Path '../../etc/passwd' resolves outside workspace: ...
```

### Sessions

```python
from bashtool import BashSession

with BashSession(workspace="./sandbox", session_id="demo") as session:
    session.execute("mkdir -p project/src")
    session.execute("echo 'print(\"Hello\")' > project/src/main.py")
    session.execute("ls", working_dir="project/src")
    for item in session.get_history():
        print(item["command"], item["exitCode"])
# The session is now terminated; execute() would raise RuntimeError.
```

Each command runs in a new shell process. The commands share only the workspace files, the session ID (recorded in the audit log), and the history. `cd`, `export`, and shell variables do not carry over to the next command.

### LangChain tools

```python
from bashtool import create_bash_langchain_tool

tools = create_bash_langchain_tool(workspace="./sandbox", timeout=30, log_file="audit.log")
print([t.name for t in tools])  # ['bash', 'read_file', 'write_file', 'list_directory']

print(tools[0].invoke({"command": "echo hello"}))
print(tools[0].invoke({"command": "sudo ls"}))  # "ERROR: Command blocked for security reasons: sudo ls"
```

Extra keyword arguments (`timeout`, `log_file`, `allow_network`, and so on) go to the `bash` tool only. The file tools get just `workspace`, so their operations are never written to the audit log. Pass `include_file_tools=False` to get only the `bash` tool.

### With a LangChain agent

The tools are standard LangChain tools, so any tool-calling agent can use them. With LangChain 1.x (Python 3.10 or newer), install `langchain-openai`, set `OPENAI_API_KEY`, and run:

```python
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from bashtool import create_bash_langchain_tool

tools = create_bash_langchain_tool(workspace="./sandbox")
agent = create_agent(ChatOpenAI(model="gpt-4o"), tools=tools)
result = agent.invoke({"messages": [{"role": "user", "content": "How many files are in the workspace?"}]})
print(result["messages"][-1].content)
```

## Configuration

These are the `BashTool` defaults:

```python
BashTool(
    workspace="/workspace",   # root for the file helpers and the default working directory; created if missing
    allow_network=False,      # only sets BASHTOOL_NO_NETWORK=1 for the command; does not block network access
    block_dangerous=True,     # check commands against the deny-list
    max_output_length=10000,  # characters kept from stdout and from stderr
    timeout=60,               # seconds before the shell is killed and TimeoutError is raised
    log_file=None,            # path of a JSON Lines audit log; relative paths are relative to the current directory
)
```

The default workspace `/workspace` usually cannot be created outside a container (for example on macOS, or as a non-root user on Linux), so pass a writable path.

`BashSession(workspace="/workspace", session_id=None, **kwargs)` passes extra keyword arguments to `BashTool`. `create_bash_langchain_tool(workspace="/workspace", include_file_tools=True, **kwargs)` passes them to the `bash` tool only.

## Safety controls and their limits

### Command deny-list

When `block_dangerous=True`, `execute` raises `ValueError` if any of these patterns (`BashTool.DANGEROUS_COMMANDS`) matches anywhere in the command string. Matching is a case-insensitive `re.search`.

- `rm\s+-rf\s+/`: `rm -rf` followed by an absolute path
- `mkfs`
- `dd\s+if=`
- `>\s*/dev/`: any redirect to `/dev/`, including `> /dev/null` and `2>/dev/null`
- `chmod\s+777\s+/`
- `sudo`
- `su\s+`
- `curl.*\|\s*bash`
- `wget.*\|\s*bash`
- `:\(\)\{`: the classic fork bomb

This is a convenience filter, not a security control. Commands with the same effect and different spelling pass, for example `rm -fr /`, `rm -r -f /`, `curl ... | sh`, or the same action written in `python -c`.

### Workspace paths

`read_file`, `write_file`, `list_directory`, and the `working_dir` argument resolve the path against the workspace with `Path.resolve()`, which follows `..` and symlinks, and raise `ValueError` if the result is outside the workspace. Shell commands are not checked: `execute("cat /etc/passwd")` runs.

### Environment variables

`execute` copies the parent process environment and removes exactly these names: `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `PRIVATE_KEY`, `PASSWORD`, and `TOKEN`. Matching is by exact name, so `OPENAI_API_KEY`, `GITHUB_TOKEN`, `AWS_ACCESS_KEY_ID`, and every other variable stay visible to the command. Variables passed in `env` are added after the removal, so they can put a removed name back.

### Network

`allow_network=False`, the default, sets `BASHTOOL_NO_NETWORK=1` in the command's environment. Nothing in BashTool or the shell reads this variable, so network access is not restricted. A command such as `curl https://example.com` runs normally; only the `curl ... | bash` and `wget ... | bash` deny-list patterns refer to network tools.

### Timeouts, output, and resources

`execute` waits up to `timeout` seconds. On timeout it kills the shell process with `Popen.kill()`, discards the output, and raises `TimeoutError`. Child processes that the shell started are not killed. Output is read in full and then truncated, so a very large output is held in memory first. `read_file` returns the whole file without truncation. There are no CPU, memory, or process-count limits.

### Shell

Commands run with `subprocess.Popen(command, shell=True)`, which uses `/bin/sh`. That is not bash on every system; on Debian and Ubuntu it is dash.

### Audit log

When `log_file` is set, each completed `execute` call appends one JSON object per line with `timestamp` (from the system `date -Iseconds` command), `session_id`, `command`, `exit_code`, the first 200 characters of stdout and of stderr, and `working_dir`. Blocked commands, timeouts, and file operations are not logged. Errors while writing the log are reported through Python `logging` and otherwise ignored.

## API reference

### `BashTool`

- `execute(command, working_dir=None, env=None, session_id=None) -> CommandResult`: runs `command` in the shell. Raises `ValueError` for a blocked command, a command over 10,000 characters, or a `working_dir` outside the workspace, and `TimeoutError` on timeout.
- `read_file(path) -> str`: raises `FileNotFoundError`, or `ValueError` for a path outside the workspace or a path that is not a file.
- `write_file(path, content) -> None`: creates parent directories and overwrites existing files.
- `list_directory(path=".") -> list[str]`: sorted names of the files and directories in `path`, not recursive. Raises `NotADirectoryError` if `path` is not a directory.
- `get_workspace_info() -> dict`: `workspace`, `files`, `allow_network`, and `timeout`.

`CommandResult` is a dataclass with `stdout`, `stderr`, `exit_code`, `command`, and `working_dir`. `to_dict()` returns the same data with the key `exitCode` instead of `exit_code`.

### `BashSession`

- `BashSession(workspace="/workspace", session_id=None, **kwargs)`: `session_id` defaults to a random UUID.
- `execute(command, working_dir=None, env=None) -> CommandResult`: raises `RuntimeError` after `terminate()`.
- `get_history() -> list[dict]`: `CommandResult.to_dict()` for each command run in the session.
- `terminate()`: marks the session inactive. Leaving a `with` block calls it.

### LangChain tools (`bashtool.langchain_tool`)

- `bash` (`BashLangChainTool`): inputs `command` (1 to 10,000 characters) and optional `working_dir`. Returns text with `STDOUT:`, `STDERR:`, and `EXIT_CODE:` sections. Blocked commands, timeouts, and other errors come back as `ERROR: ...` text instead of exceptions.
- `read_file` (`ReadFileLangChainTool`): input `path`. Returns `FILE CONTENT (<path>):` followed by the file.
- `write_file` (`WriteFileLangChainTool`): inputs `path` and `content`. Returns `SUCCESS: ...` or `ERROR: ...`.
- `list_directory` (`ListDirectoryLangChainTool`): input `path` (default `"."`). Returns the names, one per line.
- `create_bash_langchain_tool(workspace="/workspace", include_file_tools=True, **kwargs) -> list`: returns the `bash` tool, plus the three file tools when `include_file_tools=True`.

The async methods call the synchronous code, so they block the event loop while a command runs.

## Examples

- `examples/example_usage.py`: standalone `BashTool`, `BashSession`, a configured `BashLangChainTool`, and the deny-list.
- `examples/langchain_agent_example.py`: builds the four tools, prints their input schemas, calls each tool directly, and prints agent setup notes.

Both scripts use `/workspace` as the workspace, so run them where that directory can be created (for example in a container), or change the path. The agent setup text that they print refers to older LangChain APIs such as `AgentExecutor`; use the `create_agent` example above instead.

## Testing

```bash
cd bashtool
pip install -e ".[dev]"
pytest tests/test_bashtool.py -v
```

The tests cover command execution, failed commands, `working_dir`, deny-list blocking of `rm -rf /`, path traversal, file read and write, directory listing, the timeout, removal of `AWS_SECRET_ACCESS_KEY`, `get_workspace_info`, `BashSession` history and termination, and the four LangChain tools. They run real shell commands in temporary directories.

## Architecture

```
LLM agent
   |  tool call: bash, read_file, write_file, or list_directory
   v
LangChain tools (langchain_tool.py)
   |
   v
BashTool (core.py)
   |-- execute: deny-list check -> copy env minus 5 names
   |            -> subprocess.Popen(shell=True, cwd=workspace) -> truncate -> optional JSON Lines log
   |-- read_file, write_file, list_directory: resolve path -> reject if outside workspace -> file I/O
   v
Host OS: same user, filesystem, and network as the Python process
```

## Roadmap (not implemented yet)

- Network isolation that enforces `allow_network=False`.
- CPU, memory, and process limits, and killing the whole process group on timeout.
- Isolated execution, such as a container or namespaces, so commands cannot reach files outside the workspace.
- A long-lived shell per `BashSession`, so `cd` and environment changes persist between commands.
- Pattern-based removal of secret environment variables, such as any `*_KEY` or `*_TOKEN`.

## Deployment recommendations

- Run BashTool in a container or VM, not on a developer machine or a server with credentials.
- Use OS-level isolation such as seccomp and namespaces.
- Block or restrict network access outside the process, with network policies or a container network setting.
- Keep `log_file` on and monitor what the agent runs.

## License

MIT. See [LICENSE](../LICENSE).
