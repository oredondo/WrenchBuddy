import json
from decimal import Decimal

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
