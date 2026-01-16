import asyncio
import sys
from unittest.mock import MagicMock, patch
from openai import APIConnectionError, AsyncOpenAI

# Mock config before importing app.llm
with patch("app.config.config") as mock_config:
    # Setup mock config with two LLMs
    mock_default_llm = MagicMock()
    mock_default_llm.model = "broken-model"
    mock_default_llm.api_key = "broken-key"
    mock_default_llm.base_url = "http://broken-url"
    mock_default_llm.api_type = "openai"
    mock_default_llm.max_tokens = 100
    mock_default_llm.temperature = 0.5
    # Add dictionary access for legacy code support
    mock_default_llm.__getitem__ = lambda self, key: getattr(self, key)
    
    mock_backup_llm = MagicMock()
    mock_backup_llm.model = "working-model"
    mock_backup_llm.api_key = "working-key"
    mock_backup_llm.base_url = "http://working-url"
    mock_backup_llm.api_type = "openai"
    mock_backup_llm.max_tokens = 100
    mock_backup_llm.temperature = 0.5
    mock_backup_llm.__getitem__ = lambda self, key: getattr(self, key)

    mock_config.llm = {
        "default": mock_default_llm,
        "backup": mock_backup_llm
    }

    # Now import LLM
    from app.llm import LLM

async def test_llm_switching():
    print("Starting LLM switching test...")
    
    # Mock AsyncOpenAI to fail for the first client and succeed for the second
    with patch("app.llm.AsyncOpenAI") as MockAsyncOpenAI:
        # Create a mock client instance
        mock_client_instance = MagicMock()
        MockAsyncOpenAI.return_value = mock_client_instance
        
        # Setup the chat.completions.create method to raise error first, then succeed
        async def side_effect(*args, **kwargs):
            # Check which model is being used
            model = kwargs.get("model")
            print(f"Call to model: {model}")
            
            if model == "broken-model":
                print("Simulating APIConnectionError for broken-model")
                # Simulate APIConnectionError
                # Note: APIConnectionError requires a request object in recent versions, 
                # but we'll try to instantiate it simply or use a mock if needed.
                # In openai<1.0 it was different. Assuming >=1.0
                raise APIConnectionError(message="Connection failed", request=MagicMock())
            elif model == "working-model":
                print("Simulating success for working-model")
                mock_response = MagicMock()
                mock_response.choices = [MagicMock(message=MagicMock(content="Success response"))]
                mock_response.usage.prompt_tokens = 10
                mock_response.usage.completion_tokens = 10
                return mock_response
            else:
                raise ValueError(f"Unexpected model: {model}")

        mock_client_instance.chat.completions.create.side_effect = side_effect

        # Initialize LLM
        # We need to clear instances to ensure fresh init
        LLM._instances = {}
        LLM._llm_config_names = []
        
        llm = LLM()
        print(f"Initial LLM config: {llm.model}")
        
        try:
            response = await llm.ask(messages=[{"role": "user", "content": "Hello"}], stream=False)
            print(f"Response: {response}")
            
            if response == "Success response":
                print("TEST PASSED: Successfully switched to backup LLM.")
            else:
                print("TEST FAILED: Unexpected response.")
                
        except Exception as e:
            print(f"TEST FAILED: Exception caught: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_llm_switching())
