# BashTool

`bashtool` is a Python library that lets an LLM agent run shell commands and read and write files in a workspace directory, with LangChain tool wrappers.

## What it does

`BashTool.execute` runs a command string through the system shell (`subprocess.Popen(..., shell=True)`) with the workspace as the working directory, and returns stdout, stderr, and the exit code. Before running a command it checks it against a short deny-list and removes five secret-named environment variables. File helpers (`read_file`, `write_file`, `list_directory`) refuse paths outside the workspace. `create_bash_langchain_tool` wraps these as LangChain tools for an agent.

**BashTool is not a security sandbox by itself.** Commands run on your machine, as your user, with your network access. See [Safety and limits](#safety-and-limits).

## Features

- Command execution that returns a `CommandResult` with `stdout`, `stderr`, and `exit_code`, with an optional `working_dir` inside the workspace and extra `env` variables.
- Timeout (default 60 seconds) that kills the shell and raises `TimeoutError`.
- Truncation of stdout and stderr (default 10,000 characters each).
- Workspace file helpers: `read_file`, `write_file` (creates parent directories), and `list_directory`. Paths are resolved, following `..` and symlinks, and rejected with `ValueError` if they leave the workspace.
- A deny-list of 10 regular expressions for dangerous commands, such as `rm -rf /`, `sudo`, `mkfs`, and `curl ... | bash` (`block_dangerous=True` by default).
- Removal of five environment variables from the command's environment: `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `PRIVATE_KEY`, `PASSWORD`, and `TOKEN`.
- Command input checks: must be a string of at most 10,000 characters.
- Optional JSON Lines audit log of executed commands (`log_file`).
- `BashSession`: runs commands under one session ID and keeps their results as history.
- LangChain tools: `bash`, `read_file`, `write_file`, and `list_directory`.

## Install

BashTool is not on PyPI. Install it from GitHub; the package lives in the `bashtool/` folder:

```bash
pip install "git+https://github.com/sujaychandrakoyyalamudi/BashTool.git#subdirectory=bashtool"
```

For development, use an editable install with the test tools:

```bash
git clone https://github.com/sujaychandrakoyyalamudi/BashTool.git
cd BashTool/bashtool
pip install -e ".[dev]"
```

Dependencies are `langchain`, `langchain-core`, and `pydantic` 2. The classifiers in `pyproject.toml` list Python 3.9 to 3.12.

## Quick start

```python
from bashtool import BashTool

tool = BashTool(workspace="./sandbox")  # created if missing; the default is /workspace

result = tool.execute("echo hello && pwd")
print(result.exit_code, result.stdout, result.stderr)

tool.write_file("notes/hello.txt", "Hello, World!")
print(tool.read_file("notes/hello.txt"))
print(tool.list_directory("notes"))  # ['hello.txt']

for command in ("sudo ls", "curl https://example.com/install.sh | bash"):
    try:
        tool.execute(command)
    except ValueError as err:
        print(err)  # Command blocked for security reasons: ...
```

LangChain tools:

```python
from bashtool import create_bash_langchain_tool

tools = create_bash_langchain_tool(workspace="./sandbox", timeout=30, log_file="audit.log")
print([t.name for t in tools])  # ['bash', 'read_file', 'write_file', 'list_directory']
print(tools[0].invoke({"command": "ls -la"}))  # STDOUT, STDERR, and EXIT_CODE sections
```

To use the tools in an agent with LangChain 1.x (Python 3.10 or newer), install `langchain-openai`, set `OPENAI_API_KEY`, and run:

```python
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

agent = create_agent(ChatOpenAI(model="gpt-4o"), tools=tools)
result = agent.invoke({"messages": [{"role": "user", "content": "How many files are in the workspace?"}]})
print(result["messages"][-1].content)
```

## Safety and limits

**BashTool is not a security sandbox by itself.** It runs commands with `shell=True` on the host, as the same OS user as your Python process. For real isolation, run it inside a container or VM with no network access and with resource limits.

- **Shell commands are not confined to the workspace.** Path checks apply only to `read_file`, `write_file`, `list_directory`, and `working_dir`. A command such as `cat ~/.ssh/config` runs normally.
- **`allow_network=False` does not block network access.** It only sets `BASHTOOL_NO_NETWORK=1` in the command's environment, and nothing reads that variable.
- **The deny-list is easy to bypass**, for example with `rm -fr /` or `curl ... | sh`. It also blocks harmless redirects to `/dev/`, such as `2>/dev/null`.
- **Only five exact variable names are removed** from the environment. Everything else is inherited, including keys such as `OPENAI_API_KEY` or `GITHUB_TOKEN`.
- **There are no CPU, memory, or process limits.** On timeout, only the top-level shell process is killed; processes it started can keep running.
- Output is truncated only after the command finishes, so the full output is held in memory first. `read_file` output is never truncated.
- Commands run with `/bin/sh`, which is not bash on every system (for example, it is dash on Debian and Ubuntu).
- `BashSession` does not keep shell state. Each command starts a new shell, so `cd` and `export` do not carry over; only files in the workspace persist.
- The audit log records only commands that ran to completion. Blocked commands, timeouts, and file-tool operations are not logged.

## Project layout

```
BashTool/
├── README.md                     # this overview
├── LICENSE
└── bashtool/                     # the Python project
    ├── pyproject.toml
    ├── README.md                 # detailed reference
    ├── src/bashtool/
    │   ├── __init__.py           # exports BashTool, BashSession, create_bash_langchain_tool
    │   ├── core.py               # BashTool, BashSession, CommandResult
    │   └── langchain_tool.py     # LangChain tool classes, create_bash_langchain_tool
    ├── tests/test_bashtool.py
    └── examples/
        ├── example_usage.py
        └── langchain_agent_example.py
```

## Tests

After the development install, from the repository root:

```bash
cd bashtool
pytest tests/test_bashtool.py -v
```

The tests run real shell commands (`echo`, `ls`, `pwd`, `env`, `sleep`) in temporary directories.

## Roadmap (not implemented yet)

- Network isolation that enforces `allow_network=False`.
- CPU, memory, and process limits, and killing the whole process group on timeout.
- Isolated execution, such as a container or namespaces, so commands cannot reach files outside the workspace.
- A long-lived shell per `BashSession`, so `cd` and environment changes persist between commands.
- Pattern-based removal of secret environment variables, such as any `*_KEY` or `*_TOKEN`.

## License

MIT. See [LICENSE](LICENSE).

## Detailed documentation

Configuration, the full deny-list, the API reference, and the example scripts are described in [bashtool/README.md](bashtool/README.md).
