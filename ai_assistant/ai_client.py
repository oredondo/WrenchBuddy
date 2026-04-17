import logging
from datetime import datetime
from pathlib import Path

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _get_log_path() -> Path:
    return Path(settings.BASE_DIR) / 'logs' / 'ai_prompts.log'


def _log_interaction(call_type: str, model: str, prompt: str, response: str):
    """Log AI interactions to file for debugging and auditing."""
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
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(entry)
    except Exception:
        logger.exception("Failed to write AI prompt log")


DEFAULT_TIMEOUT = 300


def _get_base_url():
    """Get the base URL for the OpenAI-compatible API."""
    base = getattr(settings, 'AI_BASE_URL', 'https://leria.gal').rstrip('/')
    api_path = getattr(settings, 'AI_API_PATH', '/v1')
    return f"{base}{api_path}"


def _get_api_key():
    """Get the API key for authentication."""
    api_key = getattr(settings, 'AI_API_KEY', '')
    if not api_key:
        raise ValueError(
            "AI_API_KEY must be configured in settings"
        )
    return api_key


def _get_headers():
    """Get headers with API key authentication."""
    api_key = _get_api_key()
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
    }


def _post_request(url, payload):
    """Make a POST request to the OpenAI-compatible API."""
    response = requests.post(
        url,
        json=payload,
        headers=_get_headers(),
        timeout=DEFAULT_TIMEOUT,
    )
    if not response.ok:
        logger.error(
            "AI API request failed [%s] %s — response body: %s",
            response.status_code, url, response.text[:500],
        )
    response.raise_for_status()
    return response


def get_embedding(text: str, model: str = None) -> list[float]:
    """Get a vector embedding for text using OpenAI-compatible embeddings API."""
    if model is None:
        model = getattr(settings, 'AI_EMBEDDING_MODEL', 'leria:redacta')
    url = f"{_get_base_url()}/embeddings"
    payload = {'model': model, 'input': text}
    response = _post_request(url, payload)
    data = response.json()
    # OpenAI-compatible response: {"data": [{"embedding": [...]}]}
    return data['data'][0]['embedding']


def generate_text(prompt: str, model: str = None) -> str:
    """Send a text prompt to OpenAI-compatible API and return the generated response."""
    if model is None:
        model = getattr(settings, 'AI_TEXT_MODEL', 'leria:redacta')

    url = f"{_get_base_url()}/chat/completions"
    payload = {
        'model': model,
        'messages': [
            {'role': 'user', 'content': prompt},
        ],
        'stream': False,
        'chat_template_kwargs': {'enable_thinking': False},
    }
    response = _post_request(url, payload)
    result = response.json()['choices'][0]['message']['content']
    _log_interaction('text', model, prompt, result)
    return result


def analyze_image(image_base64: str, prompt: str, model: str = None) -> str:
    """Send an image (base64) with a prompt to OpenAI-compatible vision API."""
    if model is None:
        model = getattr(settings, 'AI_VISION_MODEL', 'leria:redacta')

    url = f"{_get_base_url()}/chat/completions"
    payload = {
        'model': model,
        'messages': [
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': prompt},
                    {
                        'type': 'image_url',
                        'image_url': {
                            'url': f'data:image/jpeg;base64,{image_base64}',
                        },
                    },
                ],
            },
        ],
        'stream': False,
        'chat_template_kwargs': {'enable_thinking': False},
    }
    response = _post_request(url, payload)
    result = response.json()['choices'][0]['message']['content']
    _log_interaction('image', model, prompt, result)
    return result
