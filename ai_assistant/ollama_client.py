import base64
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300


def _get_base_url():
    return getattr(settings, 'OLLAMA_BASE_URL', 'https://leria.gal/')


def generate_text(prompt: str, model: str = 'llama3.2-vision:11b') -> str:
    """Send a text prompt to Ollama and return the generated response."""
    url = f"{_get_base_url()}/api/generate"
    payload = {
        'model': model,
        'prompt': prompt,
        'stream': False,
    }
    response = requests.post(url, json=payload, timeout=DEFAULT_TIMEOUT, auth=)
    response.raise_for_status()
    return response.json()['response']


def analyze_image(image_base64: str, prompt: str, model: str = 'llama3.2-vision:11b') -> str:
    """Send an image (base64) with a prompt to Ollama vision model."""
    url = f"{_get_base_url()}/api/generate"
    payload = {
        'model': model,
        'prompt': prompt,
        'images': [image_base64],
        'stream': False,
    }
    response = requests.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    return response.json()['response']
