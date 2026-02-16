import base64
import logging

from celery import shared_task
from PyPDF2 import PdfReader

from ai_assistant.ollama_client import generate_text, analyze_image as ollama_analyze_image

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = (
    "Analyze this vehicle maintenance document. "
    "Extract the information and respond ONLY with valid JSON (no additional text) "
    "using this structure:\n\n"
    "{\n"
    '  "tipo_servicio": "Description of the service performed",\n'
    '  "task_codes": ["oil_change"],\n'
    '  "km": 15000,\n'
    '  "coste_total": 75.50,\n'
    '  "fecha": "2026-01-15",\n'
    '  "taller": "Workshop name",\n'
    '  "piezas": ["Oil filter", "10W40 oil 4L"],\n'
    '  "observaciones": "Relevant notes"\n'
    "}\n\n"
    "Valid task_codes: oil_change, chain_service, tire_check, brake_check, "
    "coolant_change, spark_plugs, air_filter, itv.\n"
    "You may include multiple task_codes if the document reflects multiple services.\n"
    "If any data is not available, use \"No disponible\" for text fields or null for numbers."
)


def _update_attachment(attachment_id, **fields):
    """Atomic update via queryset to avoid Django 6 NotUpdated errors."""
    from maintenance.models import EventAttachment
    EventAttachment.objects.filter(id=attachment_id).update(**fields)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def analyze_attachment(self, attachment_id: int):
    """Analyze an EventAttachment using Ollama (text for PDFs, vision for images)."""
    from maintenance.models import EventAttachment

    try:
        attachment = EventAttachment.objects.get(id=attachment_id)
    except EventAttachment.DoesNotExist:
        logger.error("Attachment %s not found", attachment_id)
        return

    _update_attachment(attachment_id, analysis_status=EventAttachment.AnalysisStatus.PROCESSING)

    try:
        if attachment.file_type == EventAttachment.FileType.PDF:
            result = _analyze_pdf(attachment)
        else:
            result = _analyze_image(attachment)

        _update_attachment(
            attachment_id,
            analysis_status=EventAttachment.AnalysisStatus.COMPLETED,
            analysis_result=result,
            analysis_error=None,
        )
        logger.info("Attachment %s analyzed successfully", attachment_id)

        from ai_assistant.signals import attachment_analysis_completed
        attachment_analysis_completed.send(
            sender=analyze_attachment,
            attachment_id=attachment_id,
            analysis_result=result,
        )

    except Exception as exc:
        _update_attachment(
            attachment_id,
            analysis_status=EventAttachment.AnalysisStatus.FAILED,
            analysis_error=str(exc)[:500],
        )
        logger.exception("Failed to analyze attachment %s", attachment_id)
        raise self.retry(exc=exc)


def _analyze_pdf(attachment):
    """Extract text from PDF and send to Ollama text model."""
    reader = PdfReader(attachment.file.path)
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)

    if not text_parts:
        return "No se pudo extraer texto del PDF."

    extracted_text = "\n".join(text_parts)
    # Truncate to avoid exceeding model context
    if len(extracted_text) > 4000:
        extracted_text = extracted_text[:4000] + "\n[...texto truncado]"

    prompt = f"{ANALYSIS_PROMPT}\n\nTexto del documento:\n{extracted_text}"
    return generate_text(prompt)


def _analyze_image(attachment):
    """Send image to Ollama vision model for analysis."""
    with open(attachment.file.path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')

    return ollama_analyze_image(image_data, ANALYSIS_PROMPT)


@shared_task
def retry_failed_analyses():
    """Retry attachments that failed analysis (up to 3 retries tracked by Celery)."""
    from maintenance.models import EventAttachment

    failed = EventAttachment.objects.filter(
        analysis_status=EventAttachment.AnalysisStatus.FAILED,
    )
    count = 0
    for attachment in failed:
        analyze_attachment.delay(attachment.id)
        count += 1

    if count:
        logger.info("Retrying %d failed analyses", count)
