import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from ai_assistant.parsers import VALID_TASK_CODES


RECOMMENDATION_SYSTEM_PROMPT = """You are a vehicle maintenance advisor. Based on the vehicle data below, generate a list of recommended maintenance tasks.

RULES:
- Only use task_codes from the catalog provided.
- Priority levels:
  - "high": overdue (past due_km or due_date based on catalog intervals)
  - "medium": due soon (within 1000 km or 30 days of interval)
  - "low": upcoming (within 3000 km or 90 days of interval)
- If a task has never been done and the vehicle has significant km, mark it as high priority.
- For safety-critical tasks, prefer higher priority.
- Estimate due_km and due_date based on last service + catalog interval.
- Provide a brief explanation in Spanish for each task.
- Estimate cost in EUR (reasonable range for Spain/Europe).

Respond ONLY with a JSON array. No extra text. Example:
[
  {
    "task_code": "oil_change",
    "priority": "high",
    "due_km": 15000,
    "due_date": "2026-03-01",
    "explanation": "Último cambio hace 6000 km, intervalo recomendado cada 5000 km.",
    "estimated_cost": 45.00
  }
]

If no maintenance is needed, respond with an empty array: []
"""


@dataclass
class RecommendationItem:
    task_code: str
    priority: str
    due_km: Optional[int] = None
    due_date: Optional[date] = None
    explanation: str = ''
    estimated_cost: Optional[Decimal] = None


def build_recommendation_prompt(context_text: str) -> str:
    return f"{RECOMMENDATION_SYSTEM_PROMPT}\n\n{context_text}"


def parse_recommendations(raw_text: str, valid_codes: set[str] | None = None) -> list[RecommendationItem]:
    """Parse AI response into RecommendationItems. Tries JSON first, then regex fallback.

    valid_codes: if provided, only items whose task_code is in this set are kept.
                 If None, falls back to the hardcoded VALID_TASK_CODES.
    """
    items = _try_parse_json(raw_text, valid_codes)
    if items is not None:
        return items

    items = _try_extract_json(raw_text, valid_codes)
    if items is not None:
        return items

    return []


def _clean_json_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)
    return text.strip()


def _try_parse_json(text: str, valid_codes: set[str] | None) -> Optional[list[RecommendationItem]]:
    cleaned = _clean_json_text(text)
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return None

    if isinstance(data, dict) and 'recommendations' in data:
        data = data['recommendations']

    if not isinstance(data, list):
        return None

    return _parse_items(data, valid_codes)


def _try_extract_json(text: str, valid_codes: set[str] | None) -> Optional[list[RecommendationItem]]:
    """Try to find a JSON array embedded in text."""
    match = re.search(r'\[[\s\S]*\]', text)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, list):
        return None
    return _parse_items(data, valid_codes)


VALID_PRIORITIES = {'high', 'medium', 'low'}


def _parse_items(data: list, valid_codes: set[str] | None) -> list[RecommendationItem]:
    allowed = valid_codes if valid_codes is not None else VALID_TASK_CODES
    items = []
    for entry in data:
        if not isinstance(entry, dict):
            continue

        task_code = entry.get('task_code', '')
        if task_code not in allowed:
            continue

        priority = entry.get('priority', 'medium')
        if priority not in VALID_PRIORITIES:
            priority = 'medium'

        due_km = None
        raw_km = entry.get('due_km')
        if raw_km is not None:
            try:
                due_km = int(raw_km)
            except (ValueError, TypeError):
                pass

        due_date = None
        raw_date = entry.get('due_date')
        if raw_date:
            try:
                due_date = date.fromisoformat(str(raw_date))
            except (ValueError, TypeError):
                pass

        estimated_cost = None
        raw_cost = entry.get('estimated_cost')
        if raw_cost is not None:
            try:
                estimated_cost = Decimal(str(raw_cost)).quantize(Decimal('0.01'))
            except (InvalidOperation, ValueError, TypeError):
                pass

        explanation = str(entry.get('explanation', ''))

        items.append(RecommendationItem(
            task_code=task_code,
            priority=priority,
            due_km=due_km,
            due_date=due_date,
            explanation=explanation,
            estimated_cost=estimated_cost,
        ))

    return items
