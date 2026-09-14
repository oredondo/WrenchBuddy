from datetime import date

from django.db.models import Max

from maintenance.models import TaskCatalog, MaintenanceEvent
from vehicles.models import Vehicle


def build_vehicle_context(vehicle_id: int) -> dict:
    """Build complete vehicle context for AI recommendation prompts.

    Returns a dict with vehicle_info, catalog entries, last events per task_code,
    community context, and a full_prompt_context string ready for injection.
    """
    vehicle = Vehicle.objects.get(id=vehicle_id)

    vehicle_info = {
        'brand': vehicle.brand,
        'model': vehicle.model,
        'year': vehicle.year,
        'current_km': vehicle.current_km,
        'displacement': vehicle.displacement,
        'usage_type': vehicle.usage_type,
        'vehicle_type': vehicle.vehicle_type,
    }

    # Catalog for this specific vehicle
    catalog_entries = list(
        TaskCatalog.objects.filter(vehicle=vehicle)
        .values('task_code', 'name', 'interval_km', 'interval_months', 'is_safety_critical')
    )

    catalog_text = _format_catalog(catalog_entries)

    # Community context: tasks from other vehicles of same brand+model
    community_entries = list(
        TaskCatalog.objects
        .filter(vehicle__brand__iexact=vehicle.brand, vehicle__model__iexact=vehicle.model)
        .exclude(vehicle_id=vehicle_id)
        .values('task_code', 'name', 'interval_km', 'interval_months', 'is_safety_critical')[:50]
    )
    community_text = _format_catalog(community_entries)

    # Last event per task_code
    last_events = _get_last_events(vehicle, vehicle_info['current_km'])

    full_prompt_context = _build_full_context(vehicle_info, catalog_text, last_events, community_text)

    return {
        'vehicle_info': vehicle_info,
        'catalog_entries': catalog_entries,
        'catalog_text': catalog_text,
        'community_entries': community_entries,
        'community_text': community_text,
        'last_events': last_events,
        'full_prompt_context': full_prompt_context,
    }


def _format_catalog(entries: list[dict]) -> str:
    if not entries:
        return 'No catalog entries available.'
    lines = []
    for e in entries:
        interval = []
        if e['interval_km']:
            interval.append(f"every {e['interval_km']} km")
        if e['interval_months']:
            interval.append(f"every {e['interval_months']} months")
        safety = ' [SAFETY CRITICAL]' if e['is_safety_critical'] else ''
        lines.append(f"- {e['task_code']} ({e['name']}): {', '.join(interval) or 'no default interval'}{safety}")
    return '\n'.join(lines)


def _get_last_events(vehicle: Vehicle, current_km: int) -> list[dict]:
    """Get the most recent MaintenanceEvent per task_code for a vehicle."""
    today = date.today()

    # Get the latest event per task_code
    latest_ids = (
        MaintenanceEvent.objects
        .filter(vehicle=vehicle)
        .values('task_code')
        .annotate(latest_id=Max('id'))
    )

    if not latest_ids:
        return []

    ids = [entry['latest_id'] for entry in latest_ids]
    events = MaintenanceEvent.objects.filter(id__in=ids).order_by('task_code')

    result = []
    for event in events:
        km_ago = max(0, current_km - event.km_at_service)
        days_ago = (today - event.date).days
        result.append({
            'task_code': event.task_code,
            'date': event.date.isoformat(),
            'km_at_service': event.km_at_service,
            'km_ago': km_ago,
            'days_ago': days_ago,
        })
    return result


def _build_full_context(
    vehicle_info: dict,
    catalog_text: str,
    last_events: list[dict],
    community_text: str = '',
) -> str:
    events_text = 'No maintenance history recorded.'
    if last_events:
        lines = []
        for e in last_events:
            lines.append(
                f"- {e['task_code']}: last done on {e['date']} at {e['km_at_service']} km "
                f"({e['km_ago']} km ago, {e['days_ago']} days ago)"
            )
        events_text = '\n'.join(lines)

    displacement = f", {vehicle_info['displacement']}cc" if vehicle_info['displacement'] else ''

    community_section = ''
    if community_text and community_text != 'No catalog entries available.':
        community_section = f"\n\n=== COMMUNITY CONTEXT ===\n{community_text}"

    return f"""=== VEHICLE ===
{vehicle_info['brand']} {vehicle_info['model']} ({vehicle_info['year']}){displacement}
Type: {vehicle_info['vehicle_type']}, Usage: {vehicle_info['usage_type']}
Current odometer: {vehicle_info['current_km']} km

=== MAINTENANCE CATALOG ===
{catalog_text}

=== LAST MAINTENANCE PER TASK ===
{events_text}{community_section}"""


def retrieve_relevant_document_chunks(vehicle_id: int, query: str, limit: int = 5) -> str:
    """Retrieve the most relevant document chunks for a given user query using pgvector."""
    from vehicles.models import DocumentChunk, VehicleDocument
    from pgvector.django import CosineDistance
    from ai_assistant.ai_client import get_embedding
    import logging

    logger = logging.getLogger(__name__)

    has_chunks = DocumentChunk.objects.filter(
        document__vehicle_id=vehicle_id,
        document__extraction_status=VehicleDocument.ExtractionStatus.COMPLETED,
    ).exists()

    if not has_chunks:
        return ''

    try:
        query_vec = get_embedding(query)
    except Exception:
        logger.exception("Failed to embed query for RAG chat context: %s", query)
        return ''

    chunks = (
        DocumentChunk.objects
        .filter(
            document__vehicle_id=vehicle_id,
            document__extraction_status=VehicleDocument.ExtractionStatus.COMPLETED,
        )
        .order_by(CosineDistance('embedding', query_vec))[:limit]
    )

    if not chunks:
        return ''

    lines = ['=== VEHICLE MANUALS & DOCUMENTS (Relevant Excerpts) ===']
    for chunk in chunks:
        label = chunk.document.description or chunk.document.original_filename
        lines.append(f"[{label} - Chunk {chunk.chunk_index}]:\n{chunk.text}")
    return '\n\n'.join(lines)

