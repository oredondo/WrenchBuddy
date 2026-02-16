import logging

from django.db import transaction

from ai_assistant.context_builder import build_vehicle_context
from ai_assistant.ollama_client import generate_text
from ai_assistant.recommendation_prompt import build_recommendation_prompt, parse_recommendations
from maintenance.models import MaintenanceTask

logger = logging.getLogger(__name__)


def generate_recommendations(vehicle_id: int) -> list[MaintenanceTask]:
    """Generate AI maintenance recommendations for a vehicle.

    1. Build vehicle context (history, catalog, km)
    2. Build prompt and call AI
    3. Parse response into RecommendationItems
    4. Replace pending tasks in DB (atomic)

    Returns the newly created MaintenanceTask objects.
    """
    context = build_vehicle_context(vehicle_id)
    prompt = build_recommendation_prompt(context['full_prompt_context'])

    logger.info("Generating recommendations for vehicle %s", vehicle_id)
    raw_response = generate_text(prompt)
    logger.debug("AI response: %s", raw_response)

    items = parse_recommendations(raw_response)

    with transaction.atomic():
        # Delete only pending tasks (keep completed/dismissed)
        MaintenanceTask.objects.filter(
            vehicle_id=vehicle_id,
            status=MaintenanceTask.Status.PENDING,
        ).delete()

        tasks = []
        for item in items:
            task = MaintenanceTask.objects.create(
                vehicle_id=vehicle_id,
                task_code=item.task_code,
                priority=item.priority,
                due_km=item.due_km,
                due_date=item.due_date,
                explanation=item.explanation,
                estimated_cost=item.estimated_cost,
                status=MaintenanceTask.Status.PENDING,
            )
            tasks.append(task)

    logger.info("Created %d recommendations for vehicle %s", len(tasks), vehicle_id)
    return tasks
