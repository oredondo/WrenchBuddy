import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from django.conf import settings
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300
_log_lock = threading.Lock()


# ─── Logging ─────────────────────────────────────────────────────────────────

def _get_log_path() -> Path:
    return Path(settings.BASE_DIR) / 'logs' / 'ai_prompts.log'


def _log_interaction(call_type: str, model: str, prompt: str, response: str) -> None:
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    separator = '=' * 80
    entry = (
        f"\n{separator}\n"
        f"[{timestamp}] {call_type.upper()} · model={model}\n"
        f"{'-' * 40} PROMPT {'-' * 33}\n"
        f"{prompt}\n"
        f"{'-' * 40} RESPONSE {'-' * 31}\n"
        f"{response}\n"
        f"{separator}\n"
    )
    try:
        log_path = _get_log_path()
        log_path.parent.mkdir(exist_ok=True)
        with _log_lock:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(entry)
    except Exception:
        logger.exception("Failed to write AI prompt log")


class _AILoggerCallback(BaseCallbackHandler):
    """LangChain callback that writes every LLM exchange to ai_prompts.log.

    One instance per _get_llm() call ensures call_type is correctly scoped
    even across concurrent Celery workers.
    """

    def __init__(self, call_type: str) -> None:
        super().__init__()
        self.call_type = call_type
        self._last_model: str = ''
        self._last_prompt: str = ''

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list],
        **kwargs: Any,
    ) -> None:
        model_kw = serialized.get('kwargs', {})
        self._last_model = (
            model_kw.get('model_name', '')
            or model_kw.get('model', '')
            or (serialized.get('id') or [''])[-1]
        )

        parts: list[str] = []
        for msg_list in messages:
            for msg in msg_list:
                role = getattr(msg, 'type', 'unknown')
                content = msg.content
                if isinstance(content, list):
                    # Multimodal: extract text parts, mark image blocks
                    readable_parts = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get('type') == 'text':
                                readable_parts.append(block['text'])
                            elif block.get('type') == 'image_url':
                                readable_parts.append('[image]')
                    content = ' '.join(readable_parts)
                parts.append(f"[{role}] {str(content)[:800]}")
        self._last_prompt = '\n'.join(parts)

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        try:
            # ChatGeneration has both .text and .message; .text == .message.content
            result = response.generations[0][0].text
        except (IndexError, AttributeError):
            result = str(response)
        _log_interaction(self.call_type, self._last_model, self._last_prompt, result)


# ─── Client factory ──────────────────────────────────────────────────────────

def _get_base_url() -> str:
    base = getattr(settings, 'AI_BASE_URL', 'https://leria.gal').rstrip('/')
    api_path = getattr(settings, 'AI_API_PATH', '/api')
    return f"{base}{api_path}"


def _get_api_key() -> str:
    api_key = getattr(settings, 'AI_API_KEY', '')
    if not api_key:
        raise ValueError("AI_API_KEY must be configured in settings")
    return api_key


def _get_llm(model: str, call_type: str = 'text') -> ChatOpenAI:
    """Return a ChatOpenAI instance configured for our OpenAI-compatible endpoint."""
    return ChatOpenAI(
        base_url=_get_base_url(),
        api_key=_get_api_key(),
        model=model,
        timeout=DEFAULT_TIMEOUT,
        max_retries=0,
        # Non-standard param → must go in extra_body (not model_kwargs).
        # Without this, Qwen generates thousands of internal reasoning tokens → timeout.
        extra_body={'chat_template_kwargs': {'enable_thinking': False}},
        callbacks=[_AILoggerCallback(call_type)],
    )


# ─── Message helpers ─────────────────────────────────────────────────────────

_ROLE_TO_CLASS: dict[str, type] = {
    'user': HumanMessage,
    'assistant': AIMessage,
    'system': SystemMessage,
}


def _to_lc_messages(messages: list[dict]) -> list:
    """Convert OpenAI-format dicts [{role, content}] to LangChain message objects."""
    result = []
    for m in messages:
        cls = _ROLE_TO_CLASS.get(m['role'])
        if cls is None:
            logger.warning("Unknown message role '%s' — skipping", m['role'])
            continue
        result.append(cls(content=m['content']))
    return result


# ─── Public API ──────────────────────────────────────────────────────────────

def generate_text(prompt: str, model: str = None) -> str:
    """Send a single user prompt and return the assistant reply."""
    if model is None:
        model = getattr(settings, 'AI_TEXT_MODEL', 'leria:redacta')
    llm = _get_llm(model, call_type='text')
    return llm.invoke([HumanMessage(content=prompt)]).content


def analyze_image(image_base64: str, prompt: str, model: str = None) -> str:
    """Send a base64-encoded image with a text prompt and return the assistant reply."""
    if model is None:
        model = getattr(settings, 'AI_VISION_MODEL', 'leria:redacta')
    llm = _get_llm(model, call_type='image')
    message = HumanMessage(content=[
        {'type': 'text', 'text': prompt},
        {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{image_base64}'}},
    ])
    return llm.invoke([message]).content


def generate_conversation(messages: list[dict], model: str = None) -> str:
    """Send a full [{role, content}] history and return the assistant reply."""
    if model is None:
        model = getattr(settings, 'AI_TEXT_MODEL', 'leria:redacta')
    llm = _get_llm(model, call_type='conversation')
    return llm.invoke(_to_lc_messages(messages)).content


def get_embedding(text: str, model: str = None) -> list[float]:
    """Return a dense vector embedding for the given text."""
    if model is None:
        model = getattr(settings, 'AI_EMBEDDING_MODEL', 'leria:redacta')
    embeddings = OpenAIEmbeddings(
        base_url=_get_base_url(),
        api_key=_get_api_key(),
        model=model,
        timeout=DEFAULT_TIMEOUT,
    )
    return embeddings.embed_query(text)


def chat_with_tools(
    messages: list[dict],
    tools: list[dict],
    tool_executor: Callable[[str, dict], str],
    model: str = None,
    max_iterations: int = 6,
) -> str:
    """Run a tool-calling loop until the model returns plain text or max_iterations.

    tools: OpenAI-format tool definitions (list of dicts with 'type' and 'function').
    tool_executor(name, args) must return a JSON string result.
    """
    if model is None:
        model = getattr(settings, 'AI_TEXT_MODEL', 'leria:redacta')

    llm = _get_llm(model, call_type='chat_tools')
    llm_with_tools = llm.bind_tools(tools)
    current_messages = _to_lc_messages(messages)

    for _ in range(max_iterations):
        response: AIMessage = llm_with_tools.invoke(current_messages)
        current_messages.append(response)

        if not response.tool_calls:
            return response.content or ''

        # Execute every tool call the model requested and append results
        for tc in response.tool_calls:
            tool_result = tool_executor(tc['name'], tc['args'])
            current_messages.append(
                ToolMessage(content=tool_result, tool_call_id=tc['id'])
            )

    # Max iterations reached — return last non-empty assistant content
    for msg in reversed(current_messages):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content
    return 'No se pudo completar la consulta.'
