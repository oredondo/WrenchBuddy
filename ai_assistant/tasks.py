import base64
import json
import logging
import re

from celery import shared_task
from PyPDF2 import PdfReader

from ai_assistant.ai_client import generate_text, analyze_image, get_embedding, get_structured_chain
from ai_assistant.schemas import TaskCatalogList, InvoiceAnalysis, NormalizedTask
from ai_assistant.prompts import CATALOG_GENERATION_PROMPT, INVOICE_ANALYSIS_PROMPT, NORMALIZE_PROMPT

logger = logging.getLogger(__name__)



@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def generate_vehicle_catalog(self, vehicle_id: int):
    """Generate TaskCatalog entries for a vehicle using AI."""
    from vehicles.models import Vehicle, VehicleDocument
    from maintenance.models import TaskCatalog

    try:
        vehicle = Vehicle.objects.get(id=vehicle_id)
    except Vehicle.DoesNotExist:
        logger.error("Vehicle %s not found for catalog generation", vehicle_id)
        return

    # Build vehicle info section
    displacement = f", {vehicle.displacement}cc" if vehicle.displacement else ''
    vehicle_info = (
        f"Brand: {vehicle.brand}\n"
        f"Model: {vehicle.model}\n"
        f"Year: {vehicle.year}{displacement}\n"
        f"Current km: {vehicle.current_km}\n"
        f"Usage type: {vehicle.usage_type}\n"
        f"Vehicle type: {vehicle.vehicle_type}"
    )

    # Build community context from other vehicles of same brand+model
    community_entries = (
        TaskCatalog.objects
        .filter(vehicle__brand__iexact=vehicle.brand, vehicle__model__iexact=vehicle.model)
        .exclude(vehicle_id=vehicle_id)
        .values('task_code', 'name', 'interval_km', 'interval_months')[:50]
    )

    community_section = ''
    if community_entries:
        lines = ['Community tasks from other users with the same vehicle model:']
        for e in community_entries:
            parts = []
            if e['interval_km']:
                parts.append(f"every {e['interval_km']} km")
            if e['interval_months']:
                parts.append(f"every {e['interval_months']} months")
            interval = ', '.join(parts) or 'no interval'
            lines.append(f"- {e['task_code']} ({e['name']}): {interval}")
        community_section = '\n'.join(lines)

    # RAG: retrieve the most relevant chunks from vehicle documents via vector search
    document_section = _retrieve_document_context(vehicle)

    try:
        chain = get_structured_chain(TaskCatalogList, CATALOG_GENERATION_PROMPT)
        result = chain.invoke({
            "vehicle_info": vehicle_info,
            "community_section": community_section,
            "document_section": document_section,
        })
    except Exception as exc:
        logger.exception("Failed to generate catalog for vehicle %s", vehicle_id)
        raise self.retry(exc=exc)

    if not result or not result.tasks:
        logger.warning("No catalog items parsed for vehicle %s.", vehicle_id)
        return

    catalog_objects = [
        TaskCatalog(
            vehicle=vehicle,
            task_code=item.task_code,
            name=item.name,
            description=item.description,
            interval_km=item.interval_km,
            interval_months=item.interval_months,
            is_safety_critical=item.is_safety_critical,
            source=TaskCatalog.Source.AI_GENERATED,
        )
        for item in result.tasks
    ]

    created = TaskCatalog.objects.bulk_create(catalog_objects, ignore_conflicts=True)
    logger.info("Created %d catalog entries for vehicle %s", len(created), vehicle_id)

def _update_attachment(attachment_id, **fields):
    """Atomic update via queryset to avoid Django 6 NotUpdated errors."""
    from maintenance.models import EventAttachment
    EventAttachment.objects.filter(id=attachment_id).update(**fields)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def analyze_attachment(self, attachment_id: int):
    """Analyze an EventAttachment using Open WebUI (text for PDFs, vision for images)."""
    from maintenance.models import EventAttachment, TaskCatalog

    try:
        attachment = EventAttachment.objects.select_related('event__vehicle').get(id=attachment_id)
    except EventAttachment.DoesNotExist:
        logger.error("Attachment %s not found", attachment_id)
        return

    _update_attachment(attachment_id, analysis_status=EventAttachment.AnalysisStatus.PROCESSING)

    # Build prompt with real task_codes from this vehicle's catalog
    vehicle = attachment.event.vehicle
    valid_codes = list(
        TaskCatalog.objects.filter(vehicle=vehicle).values_list('task_code', flat=True)
    )

    try:
        if attachment.file_type == EventAttachment.FileType.PDF:
            result_obj = _analyze_pdf(attachment, valid_codes)
        else:
            result_obj = _analyze_image(attachment, valid_codes)

        result_json = result_obj.model_dump_json()

        _update_attachment(
            attachment_id,
            analysis_status=EventAttachment.AnalysisStatus.COMPLETED,
            analysis_result=result_json,
            analysis_error=None,
        )
        logger.info("Attachment %s analyzed successfully", attachment_id)

        from ai_assistant.signals import attachment_analysis_completed
        attachment_analysis_completed.send(
            sender=analyze_attachment,
            attachment_id=attachment_id,
            analysis_result=result_json,
        )

    except Exception as exc:
        _update_attachment(
            attachment_id,
            analysis_status=EventAttachment.AnalysisStatus.FAILED,
            analysis_error=str(exc)[:500],
        )
        logger.exception("Failed to analyze attachment %s", attachment_id)
        raise self.retry(exc=exc)


def _analyze_pdf(attachment, valid_codes: list[str]) -> InvoiceAnalysis:
    """Extract text from PDF and send to Open WebUI text model."""
    with attachment.file.open('rb') as fh:
        reader = PdfReader(fh)
        text_parts = [
            page.extract_text()
            for page in reader.pages
            if page.extract_text()
        ]

    if not text_parts:
        return InvoiceAnalysis(tipo_servicio="No se pudo extraer texto del PDF.", task_codes=[], piezas=[])


    extracted_text = "\n".join(text_parts)
    if len(extracted_text) > 4000:
        extracted_text = extracted_text[:4000] + "\n[...texto truncado]"

    chain = get_structured_chain(InvoiceAnalysis, INVOICE_ANALYSIS_PROMPT)
    return chain.invoke({
        "valid_codes": ", ".join(valid_codes) if valid_codes else "oil_change, chain_service, tire_check, brake_check, coolant_change, spark_plugs, air_filter, itv",
        "document_text": extracted_text,
    })


def _analyze_image(attachment, valid_codes: list[str]) -> InvoiceAnalysis:
    """Send image to Open WebUI vision model for analysis."""
    with attachment.file.open('rb') as fh:
        image_data = base64.b64encode(fh.read()).decode('utf-8')
    
    prompt_str = f"Analyze this vehicle maintenance document. Extract the information. Valid task codes: {', '.join(valid_codes) if valid_codes else 'oil_change, chain_service, tire_check, brake_check, coolant_change, spark_plugs, air_filter, itv'}."
    
    from langchain_core.messages import SystemMessage, HumanMessage
    messages = [
        SystemMessage(content="You are a vehicle maintenance expert. Extract information from the image and respond with the requested structured schema."),
        HumanMessage(content=[
            {"type": "text", "text": prompt_str},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
        ])
    ]
    
    from ai_assistant.ai_client import _get_llm
    from django.conf import settings
    model = getattr(settings, 'AI_VISION_MODEL', 'leria:redacta')
    llm = _get_llm(model, call_type='structured_image')
    structured_llm = llm.with_structured_output(InvoiceAnalysis)
    return structured_llm.invoke(messages)


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


def _update_document(doc_id, **fields):
    """Atomic update for VehicleDocument."""
    from vehicles.models import VehicleDocument
    VehicleDocument.objects.filter(id=doc_id).update(**fields)


# Query used to retrieve the most maintenance-relevant chunks via vector search
_CATALOG_QUERY = (
    "vehicle maintenance schedule service intervals oil change brake inspection "
    "tire replacement filter air fuel coolant spark plugs chain fluid specifications "
    "torque values safety checks revision periodica"
)


def _retrieve_document_context(vehicle) -> str:
    """Vector-search the most relevant chunks from this vehicle's documents."""
    from vehicles.models import DocumentChunk, VehicleDocument
    from pgvector.django import CosineDistance

    has_chunks = DocumentChunk.objects.filter(
        document__vehicle=vehicle,
        document__extraction_status=VehicleDocument.ExtractionStatus.COMPLETED,
    ).exists()

    if not has_chunks:
        return ''

    try:
        query_vec = get_embedding(_CATALOG_QUERY)
    except Exception:
        logger.exception("Failed to embed catalog query for vehicle %s", vehicle.id)
        return ''

    chunks = (
        DocumentChunk.objects
        .filter(
            document__vehicle=vehicle,
            document__extraction_status=VehicleDocument.ExtractionStatus.COMPLETED,
        )
        .order_by(CosineDistance('embedding', query_vec))[:10]
    )

    if not chunks:
        return ''

    lines = ['=== VEHICLE DOCUMENTS — relevant excerpts (RAG) ===']
    for chunk in chunks:
        label = chunk.document.description or chunk.document.original_filename
        lines.append(f"[{label} · chunk {chunk.chunk_index}]\n{chunk.text}")
    return '\n\n'.join(lines)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def extract_document_text(self, doc_id: int):
    """Extract text from a VehicleDocument, chunk it, embed each chunk, then regenerate catalog."""
    from vehicles.models import VehicleDocument, DocumentChunk

    try:
        doc = VehicleDocument.objects.get(id=doc_id)
    except VehicleDocument.DoesNotExist:
        logger.error("VehicleDocument %s not found", doc_id)
        return

    _update_document(doc_id, extraction_status=VehicleDocument.ExtractionStatus.PROCESSING)

    try:
        if doc.file_type == VehicleDocument.FileType.PDF:
            full_text = _extract_pdf_text(doc)
        else:
            full_text = _describe_image(doc)

        # Persist raw text
        _update_document(
            doc_id,
            extracted_text=full_text,
            extraction_status=VehicleDocument.ExtractionStatus.COMPLETED,
            extraction_error='',
        )
        logger.info("VehicleDocument %s extracted (%d chars)", doc_id, len(full_text))

        # Chunk + embed (optional — skipped if embeddings are unavailable)
        try:
            doc.refresh_from_db()
            DocumentChunk.objects.filter(document=doc).delete()

            chunks_text = _chunk_text(full_text)
            chunk_objects = []
            for i, chunk in enumerate(chunks_text):
                embedding = get_embedding(chunk)
                chunk_objects.append(DocumentChunk(
                    document=doc,
                    chunk_index=i,
                    text=chunk,
                    embedding=embedding,
                ))

            DocumentChunk.objects.bulk_create(chunk_objects)
            logger.info("Created %d chunks for VehicleDocument %s", len(chunk_objects), doc_id)
        except Exception:
            logger.warning(
                "Embeddings unavailable for VehicleDocument %s — RAG skipped, catalog will regenerate without it",
                doc_id,
            )

        # Regenerate catalog (with RAG context if chunks were created, without if not)
        generate_vehicle_catalog.delay(doc.vehicle_id)
        logger.info("Triggered catalog regeneration for vehicle %s", doc.vehicle_id)

    except Exception as exc:
        _update_document(
            doc_id,
            extraction_status=VehicleDocument.ExtractionStatus.FAILED,
            extraction_error=str(exc)[:500],
        )
        logger.exception("Failed to process VehicleDocument %s", doc_id)
        raise self.retry(exc=exc)


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """Split text by page markers, then further chunk long pages with overlap."""
    import re
    pages = re.split(r'\[Página \d+\]\n', text)
    pages = [p.strip() for p in pages if p.strip()]

    chunks = []
    for page_text in pages:
        if len(page_text) <= chunk_size:
            chunks.append(page_text)
        else:
            start = 0
            while start < len(page_text):
                end = start + chunk_size
                chunk = page_text[start:end].strip()
                if chunk:
                    chunks.append(chunk)
                if end >= len(page_text):
                    break
                start = end - overlap

    return chunks


def _extract_pdf_text(doc) -> str:
    """Extract plain text from all pages of a PDF document."""
    with doc.file.open('rb') as fh:
        reader = PdfReader(fh)
        raw_pages = [
            (i, page.extract_text())
            for i, page in enumerate(reader.pages)
        ]
    parts = [
        f"[Página {i + 1}]\n{text.strip()}"
        for i, text in raw_pages
        if text and text.strip()
    ]

    if not parts:
        return 'No se pudo extraer texto del PDF (puede ser un PDF escaneado sin texto embebido).'

    return '\n\n'.join(parts)


def _describe_image(doc) -> str:
    """Ask the vision model to describe/extract content from an image document."""
    prompt = (
        "This is a vehicle document image (e.g. owner's manual page, technical spec sheet, "
        "service schedule). Extract all relevant text and technical information you can see. "
        "Focus on: maintenance intervals, torque specs, fluid types, part numbers, service schedules. "
        "Respond in the same language as the document."
    )
    with doc.file.open('rb') as fh:
        image_data = base64.b64encode(fh.read()).decode('utf-8')
    return analyze_image(image_data, prompt)


def _slugify_fallback(text: str) -> str:
    """Simple ASCII slugify used when AI is unavailable."""
    slug = re.sub(r'[^a-z0-9]+', '_', text.lower().strip())
    return slug.strip('_') or 'custom_task'


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def normalize_task_code(self, event_id: int):
    """Normalize a user-provided task_code to English snake_case via AI,
    then update the MaintenanceEvent and ensure TaskCatalog has the entry."""
    from maintenance.models import MaintenanceEvent, TaskCatalog

    try:
        event = MaintenanceEvent.objects.select_related('vehicle').get(id=event_id)
    except MaintenanceEvent.DoesNotExist:
        logger.error("normalize_task_code: event %s not found", event_id)
        return

    original = event.task_code

    normalized_code = None
    normalized_name = None
    try:
        chain = get_structured_chain(NormalizedTask, NORMALIZE_PROMPT)
        result = chain.invoke({"input": original})
        
        code = result.task_code.strip().lower()
        code = re.sub(r'[^a-z0-9_]', '', code)
        code = re.sub(r'_+', '_', code).strip('_')
        if code:
            normalized_code = code
            normalized_name = result.name.strip() or code.replace('_', ' ').title()
    except Exception:
        logger.warning("normalize_task_code: AI failed for '%s', using slugify fallback", original)

    if normalized_code is None:
        normalized_code = _slugify_fallback(original)
        normalized_name = original.strip().title() or normalized_code.replace('_', ' ').title()

    if normalized_code == original:
        # Already normalized — just ensure catalog entry exists
        TaskCatalog.objects.get_or_create(
            vehicle=event.vehicle,
            task_code=normalized_code,
            defaults={'name': normalized_name, 'source': TaskCatalog.Source.USER_CREATED},
        )
        return

    # Update event task_code
    MaintenanceEvent.objects.filter(id=event_id).update(task_code=normalized_code)

    # Create or update catalog entry
    catalog_entry, created = TaskCatalog.objects.get_or_create(
        vehicle=event.vehicle,
        task_code=normalized_code,
        defaults={'name': normalized_name, 'source': TaskCatalog.Source.USER_CREATED},
    )
    if not created and catalog_entry.source == TaskCatalog.Source.USER_CREATED and not catalog_entry.name:
        catalog_entry.name = normalized_name
        catalog_entry.save(update_fields=['name', 'updated_at'])

    logger.info(
        "normalize_task_code: event %s '%s' → '%s'",
        event_id, original, normalized_code,
    )

