import logging

from ai_assistant.context_builder import build_vehicle_context
from ai_assistant.ai_client import generate_text
from ai_assistant.recommendation_prompt import build_recommendation_prompt, parse_recommendations

logger = logging.getLogger(__name__)


def get_whats_due(vehicle_id: int) -> list[dict]:
    """Ask the AI what maintenance is due for the vehicle and return a structured list.

    Uses the vehicle's own catalog codes (not a hardcoded whitelist) so any
    AI-generated or user-created task is considered.
    """
    context = build_vehicle_context(vehicle_id)

    valid_codes = {e['task_code'] for e in context['catalog_entries']}
    name_by_code = {e['task_code']: e['name'] for e in context['catalog_entries']}

    prompt = build_recommendation_prompt(context['full_prompt_context'])
    raw = generate_text(prompt)

    recommendations = parse_recommendations(raw, valid_codes=valid_codes)

    return [
        {
            'task_code': r.task_code,
            'task_name': name_by_code.get(r.task_code, r.task_code),
            'priority': r.priority,
            'due_km': r.due_km,
            'due_date': r.due_date.isoformat() if r.due_date else None,
            'explanation': r.explanation,
            'estimated_cost': float(r.estimated_cost) if r.estimated_cost else None,
        }
        for r in recommendations
    ]
