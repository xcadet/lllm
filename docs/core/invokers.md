# Invokers and Base Models

Invokers are the execution engines of the LLLM framework. They abstract the underlying LLM APIs, taking the state of a `Dialog` and executing the API call to generate the next response.

The default invoker in LLLM is built on top of the powerful [LiteLLM](https://github.com/BerriAI/litellm) library, giving you immediate access to over 100+ LLMs (OpenAI, Anthropic, Gemini, Vertex, local models via Ollama/vLLM, and more) using a single, unified interface.

---

## The `BaseInvoker` Interface

All invokers inherit from `BaseInvoker`. If you ever need to build a custom invoker, you only need to implement a single method: `call`.

Notice that the `call` method strictly reads the rules and parsing configurations from the `Dialog`'s `top_prompt`, ensuring the dialog acts as the single source of truth for execution state.

```python
class BaseInvoker(ABC):
    @abstractmethod
    def call(
        self,
        dialog: 'Dialog',
        model: str,
        model_args: Optional[Dict[str, Any]] = None,
        parser_args: Optional[Dict[str, Any]] = None,
        responder: str = 'assistant',
        extra: Optional[Dict[str, Any]] = None, 
        api_type: APITypes = APITypes.COMPLETION,
        stream_handler: BaseStreamHandler = None,
    ) -> Message:
        pass
```

### Arguments:

* `dialog`: The current `Dialog` object representing the conversation history. The invoker will automatically read `dialog.top_prompt` to apply system instructions, tool schemas, and structured output formats.
* `model`: The model identifier string (e.g., `'gpt-4o'`, `'anthropic/claude-3-5-sonnet'`). 
* `model_args`: A dictionary of provider-specific arguments (e.g., `temperature`, `max_tokens`, `api_base`).
* `parser_args`: Arguments passed directly to the prompt's output parser.
* `responder`: The name of the agent generating the response (useful for logging and multi-agent routing).
* `extra`: Metadata purely for tracking additional information (such as frontend replay data). This is attached to the final `Message` object but *not* sent to the LLM.
* `api_type`: `APITypes.COMPLETION` (standard chat completions) or `APITypes.RESPONSE` (OpenAI's newer Responses API, which supports advanced native tools like web search and computer use).
* `stream_handler`: An optional instance of `BaseStreamHandler`. If provided, the invoker will stream text chunks to this handler in real-time while still returning the fully constructed `Message` object at the end.

---

## Streaming with `BaseStreamHandler`

LLLM uses a callback pattern for streaming to keep your dialog state clean and synchronous. To stream outputs (e.g., to a terminal or a UI), subclass `BaseStreamHandler`:

```python
class MyConsoleStreamer(BaseStreamHandler):
    def handle_chunk(self, chunk_content: str, chunk_response: Any):
        # chunk_content is the text delta
        # chunk_response is the raw chunk object from LiteLLM
        print(chunk_content, end="", flush=True)

# Pass it to the invoker (or your Agent)
message = invoker.call(dialog, model="gpt-4o", stream_handler=MyConsoleStreamer())

```

---

## Using the `LiteLLMInvoker`

We use the `LiteLLMInvoker` as the default invoker for LLLM. It completely standardizes input and output schemas across all providers. It is a popular choice for many users. See section 1 below for more details.

Note that if you choose certain providers, you may need to set additional arguments in your agent config (See [Agent Configuration](./agent.md)). For example, ollama requires you to set the `api_base` argument to the base URL of your ollama server. And different provider may have different support for arguments. See section 3 below for more details.

```python
from lllm.invokers.litellm import LiteLLMInvoker

invoker = LiteLLMInvoker()
```

### 1. Model Naming Convention

LiteLLM routes requests automatically based on the model string prefix. You can specify the provider directly in the model string:

* **OpenAI:** `openai/gpt-4o` (or simply `gpt-4o`)
* **Anthropic:** `anthropic/claude-3-5-sonnet-20241022`
* **Google:** `gemini/gemini-1.5-pro`
* **Ollama (Local):** `ollama/llama3`
* **Azure:** `azure/my-gpt4-deployment`

You can find all supported models in the [LiteLLM model list](https://models.litellm.ai/) and [LiteLLM providers](https://docs.litellm.ai/docs/providers) for more details.

### 2. Setting API Keys

You do not need to pass API keys into the invoker itself. LiteLLM automatically detects standard environment variables. Ensure these are set in your environment or `.env` file before execution:

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GEMINI_API_KEY="AIza..."
```

Please refer to [LiteLLM Python SDK](https://docs.litellm.ai/docs/#litellm-python-sdk) to see the environment variables for each provider. For certain providers (such as Azure), you may need to initialize the litellm authentication manually.

Basically, you may do this at the beginning of your script or at the start of your program. Taking Azure as an example, you may do this:

```python
import litellm
from litellm.proxy_auth import AzureADCredential, ProxyAuthHandler

# One-time setup
litellm.proxy_auth = ProxyAuthHandler(
    credential=AzureADCredential(),  # uses DefaultAzureCredential
    scope="api://my-litellm-proxy/.default"
)
litellm.api_base = "https://my-proxy.example.com"
```

So that it provides context to the LiteLLM library to authenticate with the Azure API automatically later. Please see [LiteLLM Proxy Authentication](https://docs.litellm.ai/docs/proxy_auth) for more details.


### 3. Passing Provider-Specific Arguments (`model_args`)

Because LiteLLM provides a unified interface, you can pass provider-specific or standard arguments via the `model_args` dictionary.

**LLLM automatically drops unsupported parameters** safely. For example, if you pass `presence_penalty` in a dictionary sent to Anthropic (which doesn't support it), LLLM tells LiteLLM to quietly drop it rather than throwing an error.

```python
model_args = {
    "temperature": 0.2,
    "max_tokens": 4096,
    
    # Custom API endpoints (e.g., for local Ollama or vLLM deployments)
    "api_base": "http://localhost:11434", 
    
    # Azure specific configurations
    "api_version": "2024-02-15-preview",
}

```

Please refer to [LiteLLM Completion API](https://docs.litellm.ai/docs/completion/input) and [LiteLLM Response API](https://docs.litellm.ai/docs/response_api/input) for more details.

### 4. Exception Handling

LiteLLM standardizes all provider errors into the OpenAI exception format. This means you only ever have to write one set of error-handling logic, regardless of which model you are using.

Common exceptions (accessible via `from litellm.exceptions import ...` or standard `openai` exception types):

* `RateLimitError` (HTTP 429)
* `ContextWindowExceededError` (HTTP 400)
* `AuthenticationError` (HTTP 401)
* `APIConnectionError` (HTTP 500)

*(Note: In the LLLM framework, the `Agent` class handles `max_llm_recall` and rate-limit backoffs automatically for you).*
