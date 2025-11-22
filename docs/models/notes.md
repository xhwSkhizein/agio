# 不同模型提供商(OpenAI、Anthropic、DeepSeek、Minimax 等)在具体实现上的差异和处理方式

## 核心准则

* 提供统一的 Model 基类，所有模型继承 Model 基类
* 提供统一的 Message 对象，使用 Message 封装消息，内部各自转换为提供商的格式


## 核心架构差异

### 1. OpenAI 兼容模型 vs 原生实现

Agio 中的模型提供商分为两大类:

- OpenAI-Like 模型(继承 OpenAILike 类):

  - DeepSeek: 继承 OpenAILike,使用 OpenAI API 规范, 例如 deepseek：

  ```python
  class DeepSeek(OpenAILike):
    """
    A class for interacting with DeepSeek models.

    Attributes:
        id (str): The model id. Defaults to "deepseek-chat".
        name (str): The model name. Defaults to "DeepSeek".
        provider (str): The provider name. Defaults to "DeepSeek".
        api_key (Optional[str]): The API key.
        base_url (str): The base URL. Defaults to "https://api.deepseek.com".
    """

    id: str = "deepseek-chat"
    name: str = "DeepSeek"
    provider: str = "DeepSeek"

    api_key: Optional[str] = field(default_factory=lambda: getenv("DEEPSEEK_API_KEY"))
    base_url: str = "https://api.deepseek.com"

    # Their support for structured outputs is currently broken
    supports_native_structured_outputs: bool = False

    def _get_client_params(self) -> Dict[str, Any]:
        # Fetch API key from env if not already set
        if not self.api_key:
            self.api_key = getenv("DEEPSEEK_API_KEY")
            if not self.api_key:
                # Raise error immediately if key is missing
                raise ModelProviderError(
                    message="DEEPSEEK_API_KEY not set. Please set the DEEPSEEK_API_KEY environment variable.",
                    model_name=self.name,
                    model_id=self.id,
                )

        # Define base client params
        base_params = {
            "api_key": self.api_key,
            "organization": self.organization,
            "base_url": self.base_url,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "default_headers": self.default_headers,
            "default_query": self.default_query,
        }

        # Create client_params dict with non-None values
        client_params = {k: v for k, v in base_params.items() if v is not None}

        # Add additional client params if provided
        if self.client_params:
            client_params.update(self.client_params)
        return client_params
  ```

  - OpenRouter: 同样继承 OpenAILike,支持多模型路由 openrouter.py:12-26

  ```python
  @dataclass
  class OpenRouter(OpenAILike):
    """
    A class for using models hosted on OpenRouter.

    Attributes:
        id (str): The model id. Defaults to "gpt-4o".
        name (str): The model name. Defaults to "OpenRouter".
        provider (str): The provider name. Defaults to "OpenRouter".
        api_key (Optional[str]): The API key.
        base_url (str): The base URL. Defaults to "https://openrouter.ai/api/v1".
        max_tokens (int): The maximum number of tokens. Defaults to 1024.
        fallback_models (Optional[List[str]]): List of fallback model IDs to use if the primary model
            fails due to rate limits, timeouts, or unavailability. OpenRouter will automatically try
            these models in order. Example: ["anthropic/claude-sonnet-4", "deepseek/deepseek-r1"]
    """

    id: str = "gpt-4o"
    name: str = "OpenRouter"

    api_key: Optional[str] = field(default_factory=lambda: getenv("OPENROUTER_API_KEY"))
    base_url: str = "https://openrouter.ai/api/v1"
    max_tokens: int = 1024
    models: Optional[List[str]] = None  # Dynamic model routing https://openrouter.ai/docs/features/model-routing

    def get_request_params(
        self,

        )

        # Add fallback models to extra_body if specified
        if self.models:
            # Get existing extra_body or create new dict
            extra_body = request_params.get("extra_body") or {}

            # Merge fallback models into extra_body
            extra_body["models"] = self.models

            # Update request params
            request_params["extra_body"] = extra_body

        return request_params
  ```

  - 其他如 Groq、Together、xAI 等也都继承此类

- 原生实现模型:

  - OpenAI: 直接实现 OpenAIChat 类,是标准参考实现
  - Anthropic (Claude): 完全独立实现,不兼容 OpenAI API
  - Google Gemini: 独立实现,使用 Google 的 API 规范

### 2. 消息格式处理差异

不同提供商对消息的处理方式各不相同:

- OpenAI 系列:

  - 使用标准的 messages 数组格式
  - 通过 \_format_message() 方法转换 Agio 的 Message 对象

- Anthropic Claude:

  - 需要特殊的消息块格式(ImageBlock、DocumentBlock)
  - 图片和文件需要转换为 base64 编码的特定结构
  - 使用 \_format_image_for_message() 和 \_format_file_for_message() 进行转换

- Google Gemini:

  - 使用 Part 对象表示多模态内容
  - 视频需要上传到 Gemini Files API 获取 URI
  - 通过 Part.from_bytes() 和 Part.from_uri() 处理媒体

### 3. 推理能力(Reasoning)处理

不同提供商的推理模型有不同的识别和处理逻辑:

- OpenAI 推理模型:

  - 识别 o1、o3、o4 系列模型
  - 也支持 DeepSeek-R1(通过 OpenAILike 接口)

  ```python
  def is_openai_reasoning_model(reasoning_model: Model) -> bool:
    return (
        (
            reasoning_model.__class__.__name__ == "OpenAIChat"
            or reasoning_model.__class__.__name__ == "OpenAIResponses"
            or reasoning_model.__class__.__name__ == "AzureOpenAI"
        )
        and (
            ("o4" in reasoning_model.id)
            or ("o3" in reasoning_model.id)
            or ("o1" in reasoning_model.id)
            or ("4.1" in reasoning_model.id)
            or ("4.5" in reasoning_model.id)
        )
    ) or (isinstance(reasoning_model, OpenAILike) and "deepseek-r1" in reasoning_model.id.lower())
  ```

  - 从响应中提取 <think> 标签内的推理内容

  ```python
    # We use the normal content as no reasoning content is returned
    if reasoning_agent_response.content is not None:
        # Extract content between <think> tags if present
        content = reasoning_agent_response.content
        if "<think>" in content and "</think>" in content:
            start_idx = content.find("<think>") + len("<think>")
            end_idx = content.find("</think>")
            reasoning_content = content[start_idx:end_idx].strip()
        else:
            reasoning_content = content

    return Message(
        role="assistant", content=f"<thinking>\n{reasoning_content}\n</thinking>", reasoning_content=reasoning_content
  ```
