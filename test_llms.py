import asyncio
import toml
from app.llm import LLM
from app.schema import Message, ToolChoice

async def test_config(name):
    print(f"\nTesting config: {name}")
    try:
        llm = LLM(config_name=name)
        print(f"Model: {llm.model}")
        print(f"Base URL: {llm.base_url}")
        
        messages = [Message.user_message("Hello, can you hear me?")]
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "test_tool",
                    "description": "A test tool",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "input": {"type": "string"}
                        }
                    }
                }
            }
        ]
        
        response = await llm.ask_tool(
            messages=messages,
            tools=tools,
            tool_choice=ToolChoice.AUTO
        )
        
        if response:
            print(f"SUCCESS: Received response")
            if response.tool_calls:
                print(f"Tool calls: {[tc.function.name for tc in response.tool_calls]}")
            else:
                print(f"Content: {response.content}")
        else:
            print("FAILED: No response")
            
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")

async def main():
    with open("config/config.toml", "r") as f:
        config_data = toml.load(f)
    
    llm_configs = ["default"]
    if "llm" in config_data:
        for k, v in config_data["llm"].items():
            if isinstance(v, dict):
                llm_configs.append(k)
    
    print(f"Found configs: {llm_configs}")
    
    for config_name in llm_configs:
        await test_config(config_name)

if __name__ == "__main__":
    asyncio.run(main())
