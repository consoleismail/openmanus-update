import math
from typing import Dict, List, Optional, Union

import tiktoken
from openai import (
    APIError,
    APIStatusError,
    AsyncAzureOpenAI,
    AsyncOpenAI,
    AuthenticationError,
    OpenAIError,
    RateLimitError,
)
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from app.bedrock import BedrockClient
from app.config import LLMSettings, config
from app.exceptions import TokenLimitExceeded
from app.logger import logger  # Assuming a logger is set up in your app
from app.schema import (
    ROLE_VALUES,
    TOOL_CHOICE_TYPE,
    TOOL_CHOICE_VALUES,
    Message,
    ToolChoice,
)


REASONING_MODELS = ["o1", "o3-mini"]
MULTIMODAL_MODELS = [
    "gpt-4-vision-preview",
    "gpt-4o",
    "gpt-4o-mini",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
]


class TokenCounter:
    # Token constants
    BASE_MESSAGE_TOKENS = 4
    FORMAT_TOKENS = 2
    LOW_DETAIL_IMAGE_TOKENS = 85
    HIGH_DETAIL_TILE_TOKENS = 170

    # Image processing constants
    MAX_SIZE = 2048
    HIGH_DETAIL_TARGET_SHORT_SIDE = 768
    TILE_SIZE = 512

    def __init__(self, tokenizer):
        self.tokenizer = tokenizer

    def count_text(self, text: str) -> int:
        """Calculate tokens for a text string"""
        return 0 if not text else len(self.tokenizer.encode(text))

    def count_image(self, image_item: dict) -> int:
        """
        Calculate tokens for an image based on detail level and dimensions

        For "low" detail: fixed 85 tokens
        For "high" detail:
        1. Scale to fit in 2048x2048 square
        2. Scale shortest side to 768px
        3. Count 512px tiles (170 tokens each)
        4. Add 85 tokens
        """
        detail = image_item.get("detail", "medium")

        # For low detail, always return fixed token count
        if detail == "low":
            return self.LOW_DETAIL_IMAGE_TOKENS

        # For medium detail (default in OpenAI), use high detail calculation
        # OpenAI doesn't specify a separate calculation for medium

        # For high detail, calculate based on dimensions if available
        if detail == "high" or detail == "medium":
            # If dimensions are provided in the image_item
            if "dimensions" in image_item:
                width, height = image_item["dimensions"]
                return self._calculate_high_detail_tokens(width, height)

        return (
            self._calculate_high_detail_tokens(1024, 1024) if detail == "high" else 1024
        )

    def _calculate_high_detail_tokens(self, width: int, height: int) -> int:
        """Calculate tokens for high detail images based on dimensions"""
        # Step 1: Scale to fit in MAX_SIZE x MAX_SIZE square
        if width > self.MAX_SIZE or height > self.MAX_SIZE:
            scale = self.MAX_SIZE / max(width, height)
            width = int(width * scale)
            height = int(height * scale)

        # Step 2: Scale so shortest side is HIGH_DETAIL_TARGET_SHORT_SIDE
        scale = self.HIGH_DETAIL_TARGET_SHORT_SIDE / min(width, height)
        scaled_width = int(width * scale)
        scaled_height = int(height * scale)

        # Step 3: Count number of 512px tiles
        tiles_x = math.ceil(scaled_width / self.TILE_SIZE)
        tiles_y = math.ceil(scaled_height / self.TILE_SIZE)
        total_tiles = tiles_x * tiles_y

        # Step 4: Calculate final token count
        return (
            total_tiles * self.HIGH_DETAIL_TILE_TOKENS
        ) + self.LOW_DETAIL_IMAGE_TOKENS

    def count_content(self, content: Union[str, List[Union[str, dict]]]) -> int:
        """Calculate tokens for message content"""
        if not content:
            return 0

        if isinstance(content, str):
            return self.count_text(content)

        token_count = 0
        for item in content:
            if isinstance(item, str):
                token_count += self.count_text(item)
            elif isinstance(item, dict):
                if "text" in item:
                    token_count += self.count_text(item["text"])
                elif "image_url" in item:
                    token_count += self.count_image(item)
        return token_count

    def count_tool_calls(self, tool_calls: List[dict]) -> int:
        """Calculate tokens for tool calls"""
        token_count = 0
        for tool_call in tool_calls:
            if "function" in tool_call:
                function = tool_call["function"]
                token_count += self.count_text(function.get("name", ""))
                token_count += self.count_text(function.get("arguments", ""))
        return token_count

    def count_message_tokens(self, messages: List[dict]) -> int:
        """Calculate the total number of tokens in a message list"""
        total_tokens = self.FORMAT_TOKENS  # Base format tokens

        for message in messages:
            tokens = self.BASE_MESSAGE_TOKENS  # Base tokens per message

            # Add role tokens
            tokens += self.count_text(message.get("role", ""))

            # Add content tokens
            if "content" in message:
                tokens += self.count_content(message["content"])

            # Add tool calls tokens
            if "tool_calls" in message:
                tokens += self.count_tool_calls(message["tool_calls"])

            # Add name and tool_call_id tokens
            tokens += self.count_text(message.get("name", ""))
            tokens += self.count_text(message.get("tool_call_id", ""))

            total_tokens += tokens

        return total_tokens


class LLM:
    _instances: Dict[str, "LLM"] = {}
    _llm_config_names: list = []

    def __new__(
        cls, config_name: str = "default", llm_config: Optional[LLMSettings] = None
    ):
        if config_name not in cls._instances:
            instance = super().__new__(cls)
            instance.__init__(config_name, llm_config)
            cls._instances[config_name] = instance
        return cls._instances[config_name]

    def __init__(
        self, config_name: str = "default", llm_config: Optional[LLMSettings] = None
    ):
        if not hasattr(self, "client"):  # Only initialize if not already initialized
            llm_dict = (llm_config or config.llm)
            # Collect all available config names (default, primary, backup, backup2, ...)
            if not LLM._llm_config_names:
                # Define the preferred order for failover
                preferred_order = ["default", "primary", "backup", "backup2", "backup3", "backup4", "backup5", "backup6"]

                # Get all keys from the config
                available_keys = list(llm_dict.keys())

                # Build the final list based on preferred order first
                ordered_names = [name for name in preferred_order if name in available_keys]

                # Add any other keys that weren't in the preferred list (excluding 'vision')
                other_names = [name for name in available_keys if name not in ordered_names and name != "vision"]

                LLM._llm_config_names = ordered_names + other_names

                if not LLM._llm_config_names:
                    LLM._llm_config_names = ["default"]

            self._llm_dict = llm_dict
            self._current_idx = LLM._llm_config_names.index(config_name) if config_name in LLM._llm_config_names else 0
            self._set_config(LLM._llm_config_names[self._current_idx])

    def _set_config(self, config_name: str):
        llm_cfg = self._llm_dict.get(config_name, self._llm_dict.get("default"))
        if not llm_cfg:
            # Fallback to the first available if default is missing
            llm_cfg = next(iter(self._llm_dict.values()))

        self.model = llm_cfg["model"] if isinstance(llm_cfg, dict) else llm_cfg.model
        self.max_tokens = llm_cfg.get("max_tokens", 4096) if isinstance(llm_cfg, dict) else llm_cfg.max_tokens
        self.temperature = llm_cfg.get("temperature", 1.0) if isinstance(llm_cfg, dict) else llm_cfg.temperature
        self.api_type = llm_cfg.get("api_type", "") if isinstance(llm_cfg, dict) else llm_cfg.api_type
        self.api_key = llm_cfg.get("api_key", "") if isinstance(llm_cfg, dict) else llm_cfg.api_key
        self.api_version = llm_cfg.get("api_version", "") if isinstance(llm_cfg, dict) else llm_cfg.api_version
        self.base_url = llm_cfg.get("base_url", "") if isinstance(llm_cfg, dict) else llm_cfg.base_url
        self.total_input_tokens = 0
        self.total_completion_tokens = 0
        self.max_input_tokens = llm_cfg.get("max_input_tokens") if isinstance(llm_cfg, dict) else getattr(llm_cfg, "max_input_tokens", None)
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.model)
        except KeyError:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        if self.api_type == "azure":
            self.client = AsyncAzureOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                api_version=self.api_version,
            )
        elif self.api_type == "aws":
            self.client = BedrockClient()
        else:
            self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        self.token_counter = TokenCounter(self.tokenizer)

    def _switch_to_next_llm(self):
        if self._current_idx + 1 < len(LLM._llm_config_names):
            self._current_idx += 1
            config_name = LLM._llm_config_names[self._current_idx]
            self._set_config(config_name)
            logger.warning(f"Switched to next LLM config: {config_name} (Model: {self.model})")
            return True
        return False


    def count_tokens(self, text: str) -> int:
        """Calculate the number of tokens in a text"""
        if not text:
            return 0
        return len(self.tokenizer.encode(text))

    def count_message_tokens(self, messages: List[dict]) -> int:
        return self.token_counter.count_message_tokens(messages)

    def update_token_count(self, input_tokens: int, completion_tokens: int = 0) -> None:
        """Update token counts"""
        # Only track tokens if max_input_tokens is set
        self.total_input_tokens += input_tokens
        self.total_completion_tokens += completion_tokens
        logger.info(
            f"Token usage: Input={input_tokens}, Completion={completion_tokens}, "
            f"Cumulative Input={self.total_input_tokens}, Cumulative Completion={self.total_completion_tokens}, "
            f"Total={input_tokens + completion_tokens}, Cumulative Total={self.total_input_tokens + self.total_completion_tokens}"
        )

    def check_token_limit(self, input_tokens: int) -> bool:
        """Check if token limits are exceeded"""
        if self.max_input_tokens is not None:
            return (self.total_input_tokens + input_tokens) <= self.max_input_tokens
        # If max_input_tokens is not set, always return True
        return True

    def get_limit_error_message(self, input_tokens: int) -> str:
        return f"Token limit exceeded: {self.total_input_tokens + input_tokens} > {self.max_input_tokens}"

    def format_messages(self, messages: List[Union[dict, Message]], supports_images: bool) -> List[dict]:
        formatted = []
        for msg in messages:
            if isinstance(msg, Message):
                formatted.append(msg.to_dict())
            else:
                formatted.append(msg)
        return formatted

    async def ask(
        self,
        messages: List[Union[dict, Message]],
        system_msgs: Optional[List[Union[dict, Message]]] = None,
        stream: bool = True,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Ask LLM and return the response, with provider failover.
        """
        attempt = 0
        max_attempts = len(LLM._llm_config_names)
        last_exception: Exception | None = None

        while attempt < max_attempts:
            try:
                supports_images = self.model in MULTIMODAL_MODELS
                if system_msgs:
                    messages = self.format_messages(system_msgs, supports_images) + self.format_messages(messages, supports_images)
                else:
                    messages = self.format_messages(messages, supports_images)

                # Calculate input token count
                input_tokens = self.count_message_tokens(messages)

                # Check if token limits are exceeded
                if not self.check_token_limit(input_tokens):
                    error_message = self.get_limit_error_message(input_tokens)
                    raise TokenLimitExceeded(error_message)

                params = {
                    "model": self.model,
                    "messages": messages,
                }

                if self.model in REASONING_MODELS:
                    params["max_completion_tokens"] = self.max_tokens
                else:
                    params["max_tokens"] = self.max_tokens
                    params["temperature"] = (
                        temperature if temperature is not None else self.temperature
                    )

                if not stream:
                    # Non-streaming request
                    response = await self.client.chat.completions.create(
                        **params, stream=False
                    )

                    if not response.choices or not response.choices[0].message.content:
                        raise ValueError("Empty or invalid response from LLM")

                    # Update token counts
                    self.update_token_count(
                        response.usage.prompt_tokens, response.usage.completion_tokens
                    )

                    return response.choices[0].message.content

                # Streaming request
                self.update_token_count(input_tokens)

                response = await self.client.chat.completions.create(**params, stream=True)

                collected_messages = []
                completion_text = ""
                async for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        chunk_message = chunk.choices[0].delta.content
                        collected_messages.append(chunk_message)
                        completion_text += chunk_message
                        print(chunk_message, end="", flush=True)

                print()  # Newline after streaming
                full_response = "".join(collected_messages).strip()
                if not full_response:
                    raise ValueError("Empty response from streaming LLM")

                # estimate completion tokens for streaming response
                completion_tokens = self.count_tokens(completion_text)
                self.total_completion_tokens += completion_tokens

                return full_response

            except (TokenLimitExceeded, AuthenticationError, RateLimitError, APIError, OpenAIError) as e:
                logger.warning(f"Auto-switching LLM due to {type(e).__name__}: {e}")
                last_exception = e
                if not self._switch_to_next_llm():
                    raise
            except APIStatusError as e:
                status = getattr(e, "status_code", None)
                if status in (401, 402, 403, 404, 429, 500, 502, 503, 504):
                    logger.warning(f"Auto-switching LLM due to HTTP {status}: {e}")
                    last_exception = e
                    if not self._switch_to_next_llm():
                        raise
                else:
                    logger.exception(f"APIStatusError in ask (non-failover): {e}")
                    raise
            except Exception as e:
                logger.exception(f"Unexpected error in ask: {e}")
                raise

            attempt += 1

    async def ask_tool(
        self,
        messages: List[Union[dict, Message]],
        system_msgs: Optional[List[Union[dict, Message]]] = None,
        timeout: int = 300,
        tools: Optional[List[dict]] = None,
        tool_choice: TOOL_CHOICE_TYPE = ToolChoice.AUTO,  # type: ignore
        temperature: Optional[float] = None,
        **kwargs,
    ) -> ChatCompletionMessage | None:
        """
        Ask LLM using functions/tools and return the response, with provider failover.
        """
        attempt = 0
        max_attempts = len(LLM._llm_config_names)
        last_exception: Exception | None = None

        while attempt < max_attempts:
            try:
                # Validate tool_choice
                if tool_choice not in TOOL_CHOICE_VALUES:
                    raise ValueError(f"Invalid tool_choice: {tool_choice}")

                supports_images = self.model in MULTIMODAL_MODELS

                # Format messages
                if system_msgs:
                    sys_msgs = self.format_messages(system_msgs, supports_images)
                    formatted_messages = sys_msgs + self.format_messages(messages, supports_images)
                else:
                    formatted_messages = self.format_messages(messages, supports_images)

                # Calculate input tokens (include tool schemas)
                input_tokens = self.count_message_tokens(formatted_messages)
                if tools:
                    input_tokens += sum(self.count_tokens(str(t)) for t in tools)

                if not self.check_token_limit(input_tokens):
                    raise TokenLimitExceeded(self.get_limit_error_message(input_tokens))

                # Validate tools
                if tools:
                    for tool in tools:
                        if not isinstance(tool, dict) or "type" not in tool:
                            raise ValueError("Each tool must be a dict with 'type' field")

                params = {
                    "model": self.model,
                    "messages": formatted_messages,
                    "tools": tools,
                    "tool_choice": tool_choice,
                    "timeout": timeout,
                    "stream": False,
                    **kwargs,
                }

                if self.model in REASONING_MODELS:
                    params["max_completion_tokens"] = self.max_tokens
                else:
                    params["max_tokens"] = self.max_tokens
                    params["temperature"] = temperature if temperature is not None else self.temperature

                response: ChatCompletion = await self.client.chat.completions.create(**params)

                if not response.choices or not response.choices[0].message:
                    return None

                self.update_token_count(
                    response.usage.prompt_tokens, response.usage.completion_tokens
                )
                return response.choices[0].message

            except (TokenLimitExceeded, AuthenticationError, RateLimitError, APIError, OpenAIError, ValueError) as e:
                logger.warning(f"Auto-switching LLM due to {type(e).__name__}: {e}")
                last_exception = e
                if not self._switch_to_next_llm():
                    raise
            except APIStatusError as e:
                status = getattr(e, "status_code", None)
                if status in (401, 402, 403, 404, 429, 500, 502, 503, 504):
                    logger.warning(f"Auto-switching LLM due to HTTP {status}: {e}")
                    last_exception = e
                    if not self._switch_to_next_llm():
                        raise
                else:
                    logger.exception(f"APIStatusError in ask_tool (non-failover): {e}")
                    raise
            except Exception as e:
                logger.exception(f"Unexpected error in ask_tool: {e}")
                raise

            attempt += 1

        if last_exception:
            raise last_exception
        return None
