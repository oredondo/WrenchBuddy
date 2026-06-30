import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from vehicles.models import Vehicle

logger = logging.getLogger(__name__)


class AIChatView(APIView):
    """POST /api/ai/chat/<vehicle_id>/
    Body: { message: str, history: [{role, content}, ...] }
    Returns: { response: str }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, vehicle_id):
        try:
            vehicle = Vehicle.objects.get(id=vehicle_id, user=request.user)
        except Vehicle.DoesNotExist:
            return Response({'detail': 'Vehículo no encontrado.'}, status=404)

        message = (request.data.get('message') or '').strip()
        if not message:
            return Response({'detail': 'Mensaje vacío.'}, status=400)

        history = request.data.get('history') or []

        system_prompt = (
            f"You are WrenchBuddy, a vehicle maintenance assistant. "
            f"You help the owner of a {vehicle.year} {vehicle.brand} {vehicle.model}.\n"
            "You have access to the vehicle's real maintenance database injected below.\n"
            "Rules:\n"
            "- Always reply in the same language the user writes (Spanish if they write in Spanish).\n"
            "- For safety-critical issues (brakes, tires, steering) always recommend professional inspection.\n"
            "- Be precise with numbers: km, costs, dates.\n"
            "- If data is missing, say so clearly.\n"
            "- MAINTENANCE SCHEDULE section contains pre-computed next-due km and dates. "
            "  Use those values DIRECTLY — do NOT recalculate from history. "
            "  next_due_km = last_service_km + interval_km is already done for you. "
            "  km_remaining = next_due_km - current_km is already done for you."
        )

        messages = [{'role': 'system', 'content': system_prompt}]
        for msg in history[-10:]:
            if msg.get('role') in ('user', 'assistant') and msg.get('content'):
                messages.append({'role': msg['role'], 'content': msg['content']})
        messages.append({'role': 'user', 'content': message})

        try:
            from ai_assistant.chat_tools import (
                _get_accessories, _get_maintenance_history, _get_maintenance_schedule,
                _get_spending_summary, _get_task_catalog, _get_vehicle_info,
            )
            context = "\n".join([
                "=== VEHICLE INFO ===",
                _get_vehicle_info(vehicle_id),
                "=== MAINTENANCE SCHEDULE (pre-computed — next due km/date and status per task) ===",
                _get_maintenance_schedule(vehicle_id),
                "=== MAINTENANCE HISTORY (last 50, most recent first) ===",
                _get_maintenance_history(vehicle_id, 50),
                "=== TASK CATALOG (intervals only, schedule already computed above) ===",
                _get_task_catalog(vehicle_id),
                "=== ACCESSORIES ===",
                _get_accessories(vehicle_id),
                "=== SPENDING SUMMARY ===",
                _get_spending_summary(vehicle_id),
            ])
            messages[0]['content'] += f"\n\nCURRENT DATABASE CONTEXT (live data):\n{context}"

            from ai_assistant.ai_client import generate_conversation
            reply = generate_conversation(messages)
            return Response({'response': reply})
        except Exception:
            logger.exception("AIChatView error vehicle=%s", vehicle_id)
            return Response({'detail': 'Error al consultar la IA.'}, status=502)
