import logging

from ai_assistant.parsers import parse_analysis_result, VALID_TASK_CODES

logger = logging.getLogger(__name__)


def handle_analysis_completed(sender, attachment_id, analysis_result, **kwargs):
    """Update MaintenanceEvent with data extracted from attachment analysis."""
    from maintenance.models import EventAttachment

    try:
        attachment = EventAttachment.objects.select_related('event').get(id=attachment_id)
    except EventAttachment.DoesNotExist:
        logger.warning("Attachment %s not found for auto-update", attachment_id)
        return

    event = attachment.event
    parsed = parse_analysis_result(analysis_result)

    updated_fields = []

    # Overwrite cost if analysis provides one
    if parsed.cost is not None:
        event.cost = parsed.cost
        updated_fields.append('cost')

    # Overwrite km if analysis provides one
    if parsed.km is not None:
        event.km_at_service = parsed.km
        updated_fields.append('km_at_service')

    # Overwrite date if analysis provides one
    if parsed.date is not None:
        event.date = parsed.date
        updated_fields.append('date')

    # Overwrite task_code if analysis identifies a valid one
    if parsed.task_codes:
        event.task_code = parsed.task_codes[0]
        updated_fields.append('task_code')

    # Always append notes (never replace)
    if parsed.notes_extra:
        separator = "\n\n--- Análisis adjunto ---\n"
        if event.notes:
            event.notes = event.notes + separator + parsed.notes_extra
        else:
            event.notes = parsed.notes_extra
        updated_fields.append('notes')

    if updated_fields:
        event.save(update_fields=updated_fields + ['updated_at'])
        logger.info(
            "Updated MaintenanceEvent %s from attachment %s: %s",
            event.id, attachment_id, ', '.join(updated_fields)
        )
    else:
        logger.info(
            "No fields to update on MaintenanceEvent %s from attachment %s",
            event.id, attachment_id
        )
