from datetime import date

from django.db.models import Max

from maintenance.models import TaskCatalog, MaintenanceEvent, MaintenanceTask
from vehicles.models import Vehicle


def build_vehicle_context(vehicle_id: int) -> dict:
    """Build complete vehicle context for AI recommendation prompts.

    Returns a dict with vehicle_info, catalog entries, last events per task_code,
    pending tasks, and a full_prompt_context string ready for injection.
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

    # Catalog filtered by vehicle type
    catalog_entries = list(
        TaskCatalog.objects.filter(vehicle_type=vehicle.vehicle_type)
        .values('task_code', 'name', 'default_interval_km', 'default_interval_months', 'is_safety_critical')
    )

    catalog_text = _format_catalog(catalog_entries)

    # Last event per task_code
    last_events = _get_last_events(vehicle, vehicle_info['current_km'])

    # Pending tasks
    pending_tasks = list(
        MaintenanceTask.objects.filter(vehicle=vehicle, status=MaintenanceTask.Status.PENDING)
        .values('task_code', 'priority', 'due_km', 'due_date', 'explanation')
    )

    pending_tasks_text = _format_pending_tasks(pending_tasks)

    full_prompt_context = _build_full_context(vehicle_info, catalog_text, last_events, pending_tasks_text)

    return {
        'vehicle_info': vehicle_info,
        'catalog_entries': catalog_entries,
        'catalog_text': catalog_text,
        'last_events': last_events,
        'pending_tasks': pending_tasks,
        'pending_tasks_text': pending_tasks_text,
        'full_prompt_context': full_prompt_context,
    }


def _format_catalog(entries: list[dict]) -> str:
    if not entries:
        return 'No catalog entries available.'
    lines = []
    for e in entries:
        interval = []
        if e['default_interval_km']:
            interval.append(f"every {e['default_interval_km']} km")
        if e['default_interval_months']:
            interval.append(f"every {e['default_interval_months']} months")
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


def _format_pending_tasks(tasks: list[dict]) -> str:
    if not tasks:
        return 'No pending AI tasks.'
    lines = []
    for t in tasks:
        parts = [f"- {t['task_code']} (priority: {t['priority']})"]
        if t['due_km']:
            parts.append(f"due at {t['due_km']} km")
        if t['due_date']:
            parts.append(f"due by {t['due_date']}")
        lines.append(', '.join(parts))
    return '\n'.join(lines)


def _build_full_context(vehicle_info: dict, catalog_text: str, last_events: list[dict], pending_tasks_text: str) -> str:
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

    return f"""=== VEHICLE ===
{vehicle_info['brand']} {vehicle_info['model']} ({vehicle_info['year']}){displacement}
Type: {vehicle_info['vehicle_type']}, Usage: {vehicle_info['usage_type']}
Current odometer: {vehicle_info['current_km']} km

=== MAINTENANCE CATALOG ===
{catalog_text}

=== LAST MAINTENANCE PER TASK ===
{events_text}

=== CURRENT PENDING TASKS ===
{pending_tasks_text}"""
