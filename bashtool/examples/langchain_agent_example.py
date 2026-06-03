"""
LangChain Agent Integration Example

This example shows how to use BashTool with LangChain agents.
Run this with a valid OPENAI_API_KEY or other LLM provider.
"""

import os
from bashtool.langchain_tool import create_bash_langchain_tool


def simple_agent_example():
    """
    Simple example showing tool creation and basic usage.
    This doesn't require an API key - just demonstrates the setup.
    """
    print("=" * 60)
    print("BashTool LangChain Integration Demo")
    print("=" * 60)
    
    # Create the bash tools
    tools = create_bash_langchain_tool(
        workspace="/workspace",
        include_file_tools=True,
        block_dangerous=True,
        timeout=30
    )
    
    print(f"\n✓ Created {len(tools)} LangChain tools:")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description[:60]}...")
    
    # Demonstrate tool schemas
    print("\n✓ Tool Input Schemas:")
    for tool in tools:
        schema = tool.args_schema.model_json_schema()
        print(f"\n  {tool.name}:")
        print(f"    Properties: {list(schema.get('properties', {}).keys())}")
        if 'required' in schema:
            print(f"    Required: {schema['required']}")
    
    # Test the bash tool directly
    print("\n✓ Testing bash tool execution:")
    bash_tool = tools[0]
    result = bash_tool._run(command="echo 'Hello from LangChain tool!'")
    print(f"  Result:\n  {result.replace(chr(10), chr(10) + '  ')}")
    
    # Test file operations
    print("\n✓ Testing file tools:")
    
    # Write a file
    write_tool = tools[2]  # write_file
    write_result = write_tool._run(
        path="langchain_test.txt",
        content="Created by LangChain tool!"
    )
    print(f"  Write: {write_result}")
    
    # Read it back
    read_tool = tools[1]  # read_file
    read_result = read_tool._run(path="langchain_test.txt")
    print(f"  Read: {read_result[:80]}...")
    
    # List directory
    list_tool = tools[3]  # list_directory
    list_result = list_tool._run(path=".")
    print(f"  List: Found {len(list_result.split(chr(10))) - 1} items")
    
    print("\n" + "=" * 60)
    print("All tools working correctly!")
    print("=" * 60)
    
    return tools


def full_agent_setup_guide():
    """
    Show how to set up a full LangChain agent (requires API key).
    """
    print("\n" + "=" * 60)
    print("Full Agent Setup Guide")
    print("=" * 60)
    
    guide = """
To use these tools with a real LangChain agent, you need:

1. Install required packages:
   pip install langchain langchain-openai langgraph

2. Set your API key:
   export OPENAI_API_KEY='your-key-here'

3. Use one of these setups:

   Option A: Using LangGraph (Recommended for new projects)
   -------------------------------------------------------
   from langchain_openai import ChatOpenAI
   from langgraph.prebuilt import create_react_agent
   
   llm = ChatOpenAI(model="gpt-4o", temperature=0)
   tools = create_bash_langchain_tool(workspace="/workspace")
   agent = create_react_agent(llm, tools)
   
   response = agent.invoke({"messages": [("user", "List files in /workspace")]})
   print(response)

   Option B: Using AgentExecutor (Classic approach)
   ------------------------------------------------
   from langchain_openai import ChatOpenAI
   from langchain.agents import AgentExecutor, create_openai_functions_agent
   from langchain_core.prompts import ChatPromptTemplate
   
   llm = ChatOpenAI(model="gpt-4o", temperature=0)
   tools = create_bash_langchain_tool(workspace="/workspace")
   
   prompt = ChatPromptTemplate.from_messages([
       ("system", "You are a helpful assistant with access to shell tools."),
       ("placeholder", "{chat_history}"),
       ("human", "{input}"),
       ("placeholder", "{agent_scratchpad}")
   ])
   
   agent = create_openai_functions_agent(llm, tools, prompt)
   executor = AgentExecutor(agent=agent, tools=tools)
   
   response = executor.invoke({"input": "Count the files in workspace"})
   print(response["output"])

Security Best Practices:
------------------------
- Always run in isolated environments (containers/VMs)
- Set allow_network=False unless absolutely needed
- Enable audit logging with log_file parameter
- Use block_dangerous=True (default)
- Set reasonable timeouts to prevent hangs
- Monitor resource usage with cgroups or similar

Example with security settings:
-------------------------------
tools = create_bash_langchain_tool(
    workspace="/workspace",
    allow_network=False,      # No internet access
    block_dangerous=True,     # Block rm -rf, etc.
    max_output_length=5000,   # Limit output size
    timeout=30,               # 30 second timeout
    log_file="audit.log"      # Log all commands
)
"""
    print(guide)


if __name__ == "__main__":
    # Run the demo
    tools = simple_agent_example()
    
    # Show the setup guide
    full_agent_setup_guide()
    
    print("\n✓ Demo complete! The tools are ready to use with LangChain.")
