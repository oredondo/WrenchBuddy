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

        # Convert the history list to LangChain message format
        from langchain_core.messages import AIMessage, HumanMessage
        chat_history = []
        for msg in history[-10:]:
            if msg.get('role') == 'user' and msg.get('content'):
                chat_history.append(HumanMessage(content=msg.get('content', '')))
            elif msg.get('role') == 'assistant' and msg.get('content'):
                chat_history.append(AIMessage(content=msg.get('content', '')))

        from ai_assistant.prompts import CHAT_SYSTEM_PROMPT
        from ai_assistant.ai_client import _get_llm
        from django.conf import settings

        try:
            from ai_assistant.chat_tools import (
                _get_accessories, _get_maintenance_history, _get_maintenance_schedule,
                _get_spending_summary, _get_task_catalog, _get_vehicle_info,
            )
            from ai_assistant.context_builder import retrieve_relevant_document_chunks

            rag_context = retrieve_relevant_document_chunks(vehicle_id, message, limit=5)

            context_parts = [
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
            ]
            if rag_context:
                context_parts.append(rag_context)

            context = "\n".join(context_parts)

            model = getattr(settings, 'AI_TEXT_MODEL', 'leria:redacta')
            llm = _get_llm(model, call_type='conversation')
            
            # Map preferred language
            lang_code = request.user.preferred_language
            language_name = 'Spanish' if lang_code == 'es' else 'English'

            chain = CHAT_SYSTEM_PROMPT | llm
            response_msg = chain.invoke({
                "year": vehicle.year,
                "brand": vehicle.brand,
                "model": vehicle.model,
                "database_context": context,
                "chat_history": chat_history,
                "input_message": message,
                "language_name": language_name
            })
            
            return Response({'response': response_msg.content})
        except Exception:
            logger.exception("AIChatView error vehicle=%s", vehicle_id)
            return Response({'detail': 'Error al consultar la IA.'}, status=502)

