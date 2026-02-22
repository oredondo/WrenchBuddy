import base64
import logging
import threading
from datetime import datetime
from pathlib import Path

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_log_lock = threading.Lock()


def _get_log_path() -> Path:
    return Path(settings.BASE_DIR) / 'logs' / 'ai_prompts.log'


def _log_interaction(call_type: str, model: str, prompt: str, response: str):
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

DEFAULT_TIMEOUT = 300

# Cached token from email/password login
_token_cache = {
    'token': None,
    'lock': threading.Lock(),
}


def _get_base_url():
    return getattr(settings, 'OPENWEBUI_BASE_URL', 'https://leria.gal').rstrip('/')


def _login() -> str:
    """Authenticate with Open WebUI using email/password and return JWT token."""
    email = getattr(settings, 'OPENWEBUI_EMAIL', '')
    password = getattr(settings, 'OPENWEBUI_PASSWORD', '')

    if not email or not password:
        raise ValueError(
            "OPENWEBUI_EMAIL and OPENWEBUI_PASSWORD must be configured in settings"
        )

    url = f"{_get_base_url()}/api/v1/auths/signin"
    response = requests.post(
        url,
        json={'email': email, 'password': password},
        headers={'Content-Type': 'application/json'},
        timeout=30,
    )
    response.raise_for_status()
    token = response.json()['token']
    logger.info("Successfully authenticated with Open WebUI")
    return token


def _get_token() -> str:
    """Get cached JWT token, logging in if necessary."""
    with _token_cache['lock']:
        if _token_cache['token'] is None:
            _token_cache['token'] = _login()
        return _token_cache['token']


def invalidate_token():
    """Clear cached token (e.g. after a 401 response)."""
    with _token_cache['lock']:
        _token_cache['token'] = None


def _get_headers():
    headers = {'Content-Type': 'application/json'}
    token = _get_token()
    headers['Authorization'] = f'Bearer {token}'
    return headers


def _post_with_retry(url, payload):
    """POST request with automatic re-login on 401."""
    response = requests.post(
        url, json=payload, headers=_get_headers(), timeout=DEFAULT_TIMEOUT,
    )
    if response.status_code == 401:
        logger.info("Token expired, re-authenticating...")
        invalidate_token()
        response = requests.post(
            url, json=payload, headers=_get_headers(), timeout=DEFAULT_TIMEOUT,
        )
    response.raise_for_status()
    return response


def generate_text(prompt: str, model: str = None) -> str:
    """Send a text prompt to Open WebUI and return the generated response."""
    if model is None:
        model = getattr(settings, 'OPENWEBUI_TEXT_MODEL', 'llama3.2-vision:11b')

    url = f"{_get_base_url()}/api/chat/completions"
    payload = {
        'model': model,
        'messages': [
            {'role': 'user', 'content': prompt},
        ],
    }
    response = _post_with_retry(url, payload)
    result = response.json()['choices'][0]['message']['content']
    _log_interaction('text', model, prompt, result)
    return result


def analyze_image(image_base64: str, prompt: str, model: str = None) -> str:
    """Send an image (base64) with a prompt to Open WebUI vision model."""
    if model is None:
        model = getattr(settings, 'OPENWEBUI_VISION_MODEL', 'llama3.2-vision:11b')

    url = f"{_get_base_url()}/api/chat/completions"
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
    }
    response = _post_with_retry(url, payload)
    result = response.json()['choices'][0]['message']['content']
    _log_interaction('image', model, prompt, result)
    return result
