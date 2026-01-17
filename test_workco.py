import asyncio
import json
from app.agent.manus import WorkCo
from app.tool.terminate import Terminate

async def test_terminate_tool():
    print("Testing Terminate tool...")
    terminate = Terminate()
    
    # Test with proactive suggestions
    result = await terminate.execute(
        status="success", 
        proactive_suggestions=["Update documentation", "Add unit tests"]
    )
    print(f"Result with suggestions: {result}")
    assert "Proactive Suggestions" in result
    assert "Update documentation" in result
    
    print("Terminate tool test passed!")

async def test_workco_initialization():
    print("Testing WorkCo initialization...")
    agent = WorkCo()
    print(f"Agent name: {agent.name}")
    print(f"Agent description: {agent.description}")
    assert agent.name == "WorkCo"
    assert "proactive" in agent.description.lower()
    
    # Check if terminate tool in available_tools has the new parameters
    terminate_tool = agent.available_tools.tool_map["terminate"]
    print(f"Terminate tool parameters: {terminate_tool.parameters}")
    assert "proactive_suggestions" in terminate_tool.parameters["properties"]
    
    print("WorkCo initialization test passed!")

if __name__ == "__main__":
    asyncio.run(test_terminate_tool())
    asyncio.run(test_workco_initialization())
