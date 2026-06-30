import json
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from maintenance.models import Accessory, MaintenanceEvent, TaskCatalog
from vehicles.models import Vehicle

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_vehicle_info",
            "description": (
                "Get the vehicle's details: brand, model, year, current km, "
                "displacement, usage type and notes."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_maintenance_history",
            "description": (
                "Get the maintenance history of the vehicle: all events with date, "
                "km at service, task name, cost and notes. Ordered most-recent first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max number of events to return (default 50).",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_task_catalog",
            "description": (
                "Get the vehicle's maintenance task catalog: scheduled tasks with "
                "their km/month intervals and whether they are safety-critical."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_accessories",
            "description": (
                "Get the list of installed accessories with their prices and notes. "
                "Also returns total money invested in accessories."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_spending_summary",
            "description": (
                "Get a summary of maintenance spending: total cost, breakdown by task "
                "type and breakdown by year."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def execute_tool(tool_name: str, tool_args: dict, vehicle_id: int) -> str:
    try:
        if tool_name == "get_vehicle_info":
            return _get_vehicle_info(vehicle_id)
        if tool_name == "get_maintenance_history":
            return _get_maintenance_history(vehicle_id, tool_args.get("limit", 50))
        if tool_name == "get_task_catalog":
            return _get_task_catalog(vehicle_id)
        if tool_name == "get_accessories":
            return _get_accessories(vehicle_id)
        if tool_name == "get_spending_summary":
            return _get_spending_summary(vehicle_id)
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _get_vehicle_info(vehicle_id: int) -> str:
    v = Vehicle.objects.get(id=vehicle_id)
    return json.dumps({
        "brand": v.brand,
        "model": v.model,
        "year": v.year,
        "current_km": v.current_km,
        "displacement_cc": v.displacement,
        "usage_type": v.usage_type,
        "vehicle_type": v.vehicle_type,
        "notes": v.notes or "",
    })


def _get_maintenance_history(vehicle_id: int, limit: int = 50) -> str:
    events = (
        MaintenanceEvent.objects
        .filter(vehicle_id=vehicle_id)
        .order_by('-date')[:limit]
    )
    result = [
        {
            "task_code": ev.task_code,
            "date": str(ev.date),
            "km": ev.km_at_service,
            "cost_eur": float(ev.cost) if ev.cost else None,
            "notes": ev.notes or "",
        }
        for ev in events
    ]
    return json.dumps(result)


def _get_task_catalog(vehicle_id: int) -> str:
    tasks = TaskCatalog.objects.filter(vehicle_id=vehicle_id)
    result = [
        {
            "name": t.name,
            "task_code": t.task_code,
            "interval_km": t.interval_km,
            "interval_months": t.interval_months,
            "is_safety_critical": t.is_safety_critical,
            "source": t.source,
        }
        for t in tasks
    ]
    return json.dumps(result)


def _get_accessories(vehicle_id: int) -> str:
    accessories = list(Accessory.objects.filter(vehicle_id=vehicle_id))
    total = sum(float(a.price) for a in accessories if a.price)
    result = [
        {
            "name": a.name,
            "price_eur": float(a.price) if a.price else None,
            "notes": a.notes or "",
        }
        for a in accessories
    ]
    return json.dumps({"accessories": result, "total_invested_eur": total})


def _get_maintenance_schedule(vehicle_id: int) -> str:
    """Pre-computed next-due km and date for every task in the catalog.

    The AI must NOT recalculate these values — use them directly to answer questions
    about upcoming maintenance, km remaining, or overdue tasks.
    """
    vehicle = Vehicle.objects.get(id=vehicle_id)
    current_km = vehicle.current_km
    today = date.today()

    tasks = list(TaskCatalog.objects.filter(vehicle_id=vehicle_id))

    # Last event per task_code (single query, most recent first)
    last_events: dict[str, MaintenanceEvent] = {}
    for ev in MaintenanceEvent.objects.filter(vehicle_id=vehicle_id).order_by('-date'):
        if ev.task_code not in last_events:
            last_events[ev.task_code] = ev

    schedule = []
    for task in tasks:
        last = last_events.get(task.task_code)
        entry: dict = {
            "task_code": task.task_code,
            "name": task.name,
            "safety_critical": task.is_safety_critical,
            "interval_km": task.interval_km,
            "interval_months": task.interval_months,
            "last_service_km": last.km_at_service if last else None,
            "last_service_date": str(last.date) if last else None,
        }

        # ── KM-based projection ──────────────────────────────────────────────
        if task.interval_km:
            if last:
                next_km = last.km_at_service + task.interval_km
                remaining = next_km - current_km
                entry["next_due_km"] = next_km
                entry["km_remaining"] = remaining
                entry["km_status"] = (
                    "OVERDUE" if remaining <= 0
                    else "DUE_SOON" if remaining <= 500
                    else "OK"
                )
            else:
                entry["next_due_km"] = "unknown — never serviced"
                entry["km_status"] = "NEVER_DONE"

        # ── Date-based projection ────────────────────────────────────────────
        if task.interval_months:
            if last:
                next_date = last.date + relativedelta(months=task.interval_months)
                days_left = (next_date - today).days
                entry["next_due_date"] = str(next_date)
                entry["days_remaining"] = days_left
                entry["date_status"] = (
                    "OVERDUE" if days_left <= 0
                    else "DUE_SOON" if days_left <= 30
                    else "OK"
                )
            else:
                entry["next_due_date"] = "unknown — never serviced"
                entry["date_status"] = "NEVER_DONE"

        schedule.append(entry)

    return json.dumps(schedule, ensure_ascii=False)


def _get_spending_summary(vehicle_id: int) -> str:
    events = MaintenanceEvent.objects.filter(
        vehicle_id=vehicle_id,
        cost__isnull=False,
    ).values("task_code", "date", "cost")

    total = Decimal("0")
    by_task: dict[str, float] = {}
    by_year: dict[str, float] = {}

    for ev in events:
        cost = Decimal(str(ev["cost"]))
        total += cost

        task = ev["task_code"]
        by_task[task] = float(Decimal(str(by_task.get(task, 0))) + cost)

        year = str(ev["date"])[:4]
        by_year[year] = float(Decimal(str(by_year.get(year, 0))) + cost)

    return json.dumps({
        "total_maintenance_eur": float(total),
        "by_task": by_task,
        "by_year": by_year,
    })
