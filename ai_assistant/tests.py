import base64
import json
from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import Mock, patch, MagicMock, mock_open

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, SimpleTestCase, override_settings
from langchain_core.messages import AIMessage

from ai_assistant import ai_client
from ai_assistant.handlers import handle_analysis_completed
from ai_assistant.parsers import parse_analysis_result, ParsedAnalysis
from ai_assistant.signals import attachment_analysis_completed
from ai_assistant.tasks import analyze_attachment, retry_failed_analyses, _analyze_pdf, _analyze_image
from maintenance.models import EventAttachment, MaintenanceEvent
from users.models import CustomUser
from vehicles.models import Vehicle


# Mock API key for tests
MOCK_API_KEY = 'test-api-key-12345'


def _mock_llm(content: str = 'response') -> Mock:
    """Return a mock LLM whose invoke() returns an AIMessage."""
    mock = Mock()
    mock.invoke.return_value = AIMessage(content=content)
    mock.bind_tools.return_value = mock
    return mock


@override_settings(AI_API_KEY=MOCK_API_KEY)
class TestAIClient(SimpleTestCase):
    """Tests for ai_client module (LangChain / OpenAI-compatible integration)."""

    def setUp(self):
        self.test_prompt = "Test prompt for generation"
        self.test_model = "qwen2.5:7b-instruct"
        self.test_vision_model = "llava:7b"
        self.test_image_base64 = base64.b64encode(b"fake_image_data").decode('utf-8')

    # ── generate_text ────────────────────────────────────────────────────────

    @patch('ai_assistant.ai_client._get_llm')
    def test_generate_text_with_valid_response_returns_text(self, mock_get_llm):
        expected = "This is the generated response text"
        mock_get_llm.return_value = _mock_llm(expected)

        result = ai_client.generate_text(self.test_prompt, self.test_model)

        self.assertEqual(result, expected)
        mock_get_llm.assert_called_once_with(self.test_model, call_type='text')

    @override_settings(AI_TEXT_MODEL='custom-model')
    @patch('ai_assistant.ai_client._get_llm')
    def test_generate_text_uses_model_from_settings(self, mock_get_llm):
        mock_get_llm.return_value = _mock_llm()

        ai_client.generate_text(self.test_prompt)

        mock_get_llm.assert_called_once_with('custom-model', call_type='text')

    @patch('ai_assistant.ai_client._get_llm')
    def test_generate_text_propagates_llm_exception(self, mock_get_llm):
        mock = Mock()
        mock.invoke.side_effect = RuntimeError("API unavailable")
        mock_get_llm.return_value = mock

        with self.assertRaises(RuntimeError):
            ai_client.generate_text(self.test_prompt)

    @patch('ai_assistant.ai_client._get_llm')
    def test_generate_text_propagates_timeout(self, mock_get_llm):
        mock = Mock()
        mock.invoke.side_effect = TimeoutError("Request timed out")
        mock_get_llm.return_value = mock

        with self.assertRaises(TimeoutError):
            ai_client.generate_text(self.test_prompt)

    @patch('ai_assistant.ai_client._get_llm')
    def test_generate_text_propagates_connection_error(self, mock_get_llm):
        mock = Mock()
        mock.invoke.side_effect = ConnectionError("Connection refused")
        mock_get_llm.return_value = mock

        with self.assertRaises(ConnectionError):
            ai_client.generate_text(self.test_prompt)

    # ── analyze_image ────────────────────────────────────────────────────────

    @patch('ai_assistant.ai_client._get_llm')
    def test_analyze_image_with_valid_response_returns_text(self, mock_get_llm):
        expected = "Analysis of the image shows maintenance invoice"
        mock_get_llm.return_value = _mock_llm(expected)

        result = ai_client.analyze_image(
            self.test_image_base64,
            self.test_prompt,
            self.test_vision_model,
        )

        self.assertEqual(result, expected)
        mock_get_llm.assert_called_once_with(self.test_vision_model, call_type='image')
        # Verify the LLM was invoked with a multimodal message
        invoke_args = mock_get_llm.return_value.invoke.call_args[0][0]
        msg_content = invoke_args[0].content
        self.assertIsInstance(msg_content, list)
        self.assertEqual(msg_content[0]['type'], 'text')
        self.assertEqual(msg_content[1]['type'], 'image_url')

    @override_settings(AI_VISION_MODEL='custom-vision')
    @patch('ai_assistant.ai_client._get_llm')
    def test_analyze_image_uses_model_from_settings(self, mock_get_llm):
        mock_get_llm.return_value = _mock_llm()

        ai_client.analyze_image(self.test_image_base64, self.test_prompt)

        mock_get_llm.assert_called_once_with('custom-vision', call_type='image')

    @patch('ai_assistant.ai_client._get_llm')
    def test_analyze_image_propagates_llm_exception(self, mock_get_llm):
        mock = Mock()
        mock.invoke.side_effect = RuntimeError("Vision model unavailable")
        mock_get_llm.return_value = mock

        with self.assertRaises(RuntimeError):
            ai_client.analyze_image(self.test_image_base64, self.test_prompt)

    # ── ChatOpenAI instantiation ─────────────────────────────────────────────

    @override_settings(AI_BASE_URL='https://custom-api.example.com')
    @patch('ai_assistant.ai_client.ChatOpenAI')
    def test_get_llm_uses_custom_base_url_from_settings(self, mock_chat_cls):
        mock_chat_cls.return_value = _mock_llm()

        ai_client.generate_text(self.test_prompt)

        call_kwargs = mock_chat_cls.call_args[1]
        self.assertTrue(call_kwargs['base_url'].startswith('https://custom-api.example.com'))

    @patch('ai_assistant.ai_client.ChatOpenAI')
    def test_get_llm_passes_api_key(self, mock_chat_cls):
        mock_chat_cls.return_value = _mock_llm()

        ai_client.generate_text(self.test_prompt)

        call_kwargs = mock_chat_cls.call_args[1]
        self.assertEqual(call_kwargs['api_key'], MOCK_API_KEY)

    @patch('ai_assistant.ai_client.ChatOpenAI')
    def test_get_llm_passes_enable_thinking_false(self, mock_chat_cls):
        mock_chat_cls.return_value = _mock_llm()

        ai_client.generate_text(self.test_prompt)

        call_kwargs = mock_chat_cls.call_args[1]
        extra_body = call_kwargs.get('extra_body', {})
        self.assertFalse(extra_body['chat_template_kwargs']['enable_thinking'])

    # ── _get_base_url / _get_api_key ─────────────────────────────────────────

    def test_get_base_url_returns_string_starting_with_http(self):
        result = ai_client._get_base_url()

        self.assertIsInstance(result, str)
        self.assertTrue(result.startswith('http'))

    def test_get_api_key_raises_when_not_configured(self):
        with self.assertRaises(ValueError) as ctx:
            with self.settings(AI_API_KEY=''):
                ai_client._get_api_key()
        self.assertIn('AI_API_KEY', str(ctx.exception))

    # ── get_embedding ────────────────────────────────────────────────────────

    @patch('ai_assistant.ai_client.OpenAIEmbeddings')
    def test_get_embedding_returns_vector(self, mock_emb_cls):
        expected = [0.1, 0.2, 0.3, 0.4, 0.5]
        mock_emb = Mock()
        mock_emb.embed_query.return_value = expected
        mock_emb_cls.return_value = mock_emb

        result = ai_client.get_embedding("test text")

        self.assertEqual(result, expected)
        mock_emb.embed_query.assert_called_once_with("test text")

    @override_settings(AI_EMBEDDING_MODEL='custom-embedding-model')
    @patch('ai_assistant.ai_client.OpenAIEmbeddings')
    def test_get_embedding_uses_model_from_settings(self, mock_emb_cls):
        mock_emb = Mock()
        mock_emb.embed_query.return_value = [0.1, 0.2]
        mock_emb_cls.return_value = mock_emb

        ai_client.get_embedding("test text")

        call_kwargs = mock_emb_cls.call_args[1]
        self.assertEqual(call_kwargs['model'], 'custom-embedding-model')


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True
)
class TestAnalyzeAttachmentTask(TestCase):
    """Tests for analyze_attachment Celery task."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.vehicle = Vehicle.objects.create(
            user=self.user,
            vehicle_type='motorcycle',
            brand='Honda',
            model='CBR600RR',
            year=2020,
            current_km=15000,
            usage_type='mixed'
        )
        self.event = MaintenanceEvent.objects.create(
            vehicle=self.vehicle,
            task_code='oil_change',
            date='2026-01-15',
            km_at_service=14500,
            notes='Oil change service',
            cost=Decimal('75.50')
        )

    def _create_pdf_attachment(self):
        pdf_content = b'%PDF-1.4 fake pdf content'
        pdf_file = SimpleUploadedFile(
            "invoice.pdf", pdf_content, content_type="application/pdf"
        )
        return EventAttachment.objects.create(
            event=self.event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='invoice.pdf'
        )

    def _create_image_attachment(self):
        image_content = b'\x89PNG\r\n\x1a\n fake png content'
        image_file = SimpleUploadedFile(
            "receipt.png", image_content, content_type="image/png"
        )
        return EventAttachment.objects.create(
            event=self.event,
            file=image_file,
            file_type=EventAttachment.FileType.IMAGE,
            original_filename='receipt.png'
        )

    def test_analyze_attachment_with_nonexistent_id_logs_error_and_returns(self):
        result = analyze_attachment(99999)
        self.assertIsNone(result)

    @patch('ai_assistant.tasks._analyze_pdf')
    def test_analyze_attachment_with_pdf_sets_processing_status(self, mock_analyze_pdf):
        attachment = self._create_pdf_attachment()
        mock_analyze_pdf.return_value = "Analyzed PDF content"

        analyze_attachment(attachment.id)

        attachment.refresh_from_db()
        self.assertEqual(attachment.analysis_status, EventAttachment.AnalysisStatus.COMPLETED)

    @patch('ai_assistant.tasks._analyze_pdf')
    def test_analyze_attachment_with_pdf_success_updates_result(self, mock_analyze_pdf):
        attachment = self._create_pdf_attachment()
        expected_result = "Service type: Oil change\nCost: 75.50 EUR\nDate: 15/01/2026"
        mock_analyze_pdf.return_value = expected_result

        analyze_attachment(attachment.id)

        attachment.refresh_from_db()
        self.assertEqual(attachment.analysis_status, EventAttachment.AnalysisStatus.COMPLETED)
        self.assertEqual(attachment.analysis_result, expected_result)
        self.assertIsNone(attachment.analysis_error)

    @patch('ai_assistant.tasks._analyze_image')
    def test_analyze_attachment_with_image_success_updates_result(self, mock_analyze_image):
        attachment = self._create_image_attachment()
        expected_result = "Invoice from workshop showing brake service"
        mock_analyze_image.return_value = expected_result

        analyze_attachment(attachment.id)

        attachment.refresh_from_db()
        self.assertEqual(attachment.analysis_status, EventAttachment.AnalysisStatus.COMPLETED)
        self.assertEqual(attachment.analysis_result, expected_result)
        self.assertIsNone(attachment.analysis_error)

    @patch('ai_assistant.tasks._analyze_pdf')
    def test_analyze_attachment_with_pdf_failure_sets_failed_status(self, mock_analyze_pdf):
        attachment = self._create_pdf_attachment()
        error_message = "Service unavailable"
        mock_analyze_pdf.side_effect = RuntimeError(error_message)

        with self.assertRaises(RuntimeError):
            analyze_attachment(attachment.id)

        attachment.refresh_from_db()
        self.assertEqual(attachment.analysis_status, EventAttachment.AnalysisStatus.FAILED)
        self.assertIn(error_message, attachment.analysis_error)

    @patch('ai_assistant.tasks._analyze_image')
    def test_analyze_attachment_with_image_failure_sets_failed_status(self, mock_analyze_image):
        attachment = self._create_image_attachment()
        error_message = "Vision model not available"
        mock_analyze_image.side_effect = RuntimeError(error_message)

        with self.assertRaises(RuntimeError):
            analyze_attachment(attachment.id)

        attachment.refresh_from_db()
        self.assertEqual(attachment.analysis_status, EventAttachment.AnalysisStatus.FAILED)
        self.assertIn(error_message, attachment.analysis_error)

    @patch('ai_assistant.tasks._analyze_pdf')
    def test_analyze_attachment_clears_previous_error_on_success(self, mock_analyze_pdf):
        attachment = self._create_pdf_attachment()
        attachment.analysis_status = EventAttachment.AnalysisStatus.FAILED
        attachment.analysis_error = "Previous error"
        attachment.save()

        mock_analyze_pdf.return_value = "Success result"

        analyze_attachment(attachment.id)

        attachment.refresh_from_db()
        self.assertEqual(attachment.analysis_status, EventAttachment.AnalysisStatus.COMPLETED)
        self.assertIsNone(attachment.analysis_error)

    @patch('ai_assistant.tasks.generate_text')
    @patch('ai_assistant.tasks.PdfReader')
    def test_analyze_pdf_with_valid_pdf_extracts_text_and_calls_ai(self, mock_pdf_reader, mock_generate_text):
        attachment = self._create_pdf_attachment()

        mock_page1 = Mock()
        mock_page1.extract_text.return_value = "Invoice for oil change service"
        mock_page2 = Mock()
        mock_page2.extract_text.return_value = "Total: 75.50 EUR"

        mock_reader_instance = Mock()
        mock_reader_instance.pages = [mock_page1, mock_page2]
        mock_pdf_reader.return_value = mock_reader_instance

        expected_ai_response = "Analyzed invoice data"
        mock_generate_text.return_value = expected_ai_response

        result = _analyze_pdf(attachment, "test prompt")

        self.assertEqual(result, expected_ai_response)
        mock_pdf_reader.assert_called_once()
        mock_generate_text.assert_called_once()

        prompt = mock_generate_text.call_args[0][0]
        self.assertIn("Invoice for oil change service", prompt)
        self.assertIn("Total: 75.50 EUR", prompt)

    @patch('ai_assistant.tasks.generate_text')
    @patch('ai_assistant.tasks.PdfReader')
    def test_analyze_pdf_with_empty_pdf_returns_no_text_message(self, mock_pdf_reader, mock_generate_text):
        attachment = self._create_pdf_attachment()

        mock_page = Mock()
        mock_page.extract_text.return_value = ""

        mock_reader_instance = Mock()
        mock_reader_instance.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader_instance

        result = _analyze_pdf(attachment, "test prompt")

        self.assertEqual(result, "No se pudo extraer texto del PDF.")
        mock_generate_text.assert_not_called()

    @patch('ai_assistant.tasks.generate_text')
    @patch('ai_assistant.tasks.PdfReader')
    def test_analyze_pdf_truncates_long_text(self, mock_pdf_reader, mock_generate_text):
        attachment = self._create_pdf_attachment()

        long_text = "A" * 5000
        mock_page = Mock()
        mock_page.extract_text.return_value = long_text

        mock_reader_instance = Mock()
        mock_reader_instance.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader_instance

        mock_generate_text.return_value = "Analysis"

        result = _analyze_pdf(attachment, "test prompt")

        prompt = mock_generate_text.call_args[0][0]
        self.assertIn("[...texto truncado]", prompt)
        self.assertLess(len(prompt), 5500)

    @patch('ai_assistant.tasks.analyze_image')
    @patch('builtins.open', new_callable=mock_open, read_data=b'fake_image_binary_data')
    def test_analyze_image_reads_file_and_calls_vision(self, mock_file, mock_analyze_image):
        attachment = self._create_image_attachment()
        expected_result = "Image shows maintenance receipt"
        mock_analyze_image.return_value = expected_result

        result = _analyze_image(attachment, "test prompt")

        self.assertEqual(result, expected_result)
        mock_analyze_image.assert_called_once()

        image_base64 = mock_analyze_image.call_args[0][0]
        self.assertIsInstance(image_base64, str)
        decoded = base64.b64decode(image_base64)
        self.assertEqual(decoded, b'fake_image_binary_data')


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True
)
class TestRetryFailedAnalysesTask(TestCase):
    """Tests for retry_failed_analyses Celery task."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.vehicle = Vehicle.objects.create(
            user=self.user,
            vehicle_type='motorcycle',
            brand='Yamaha',
            model='MT-07',
            year=2021,
            current_km=8000,
            usage_type='city'
        )
        self.event = MaintenanceEvent.objects.create(
            vehicle=self.vehicle,
            task_code='chain_service',
            date='2026-02-01',
            km_at_service=7800,
            cost=Decimal('45.00')
        )

    def _create_failed_attachment(self):
        pdf_file = SimpleUploadedFile("failed.pdf", b'content', content_type="application/pdf")
        return EventAttachment.objects.create(
            event=self.event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='failed.pdf',
            analysis_status=EventAttachment.AnalysisStatus.FAILED,
            analysis_error='Previous failure'
        )

    def test_retry_failed_analyses_with_no_failed_attachments_does_nothing(self):
        pdf_file = SimpleUploadedFile("success.pdf", b'content', content_type="application/pdf")
        EventAttachment.objects.create(
            event=self.event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='success.pdf',
            analysis_status=EventAttachment.AnalysisStatus.COMPLETED
        )

        with patch('ai_assistant.tasks.analyze_attachment.delay') as mock_delay:
            retry_failed_analyses()
            mock_delay.assert_not_called()

    @patch('ai_assistant.tasks.analyze_attachment.delay')
    def test_retry_failed_analyses_dispatches_task_for_single_failed(self, mock_delay):
        failed_attachment = self._create_failed_attachment()

        retry_failed_analyses()

        mock_delay.assert_called_once_with(failed_attachment.id)

    @patch('ai_assistant.tasks.analyze_attachment.delay')
    def test_retry_failed_analyses_dispatches_tasks_for_multiple_failed(self, mock_delay):
        failed1 = self._create_failed_attachment()

        event2 = MaintenanceEvent.objects.create(
            vehicle=self.vehicle,
            task_code='brake_check',
            date='2026-02-05',
            km_at_service=7900
        )
        pdf_file2 = SimpleUploadedFile("failed2.pdf", b'content2', content_type="application/pdf")
        failed2 = EventAttachment.objects.create(
            event=event2,
            file=pdf_file2,
            file_type=EventAttachment.FileType.PDF,
            original_filename='failed2.pdf',
            analysis_status=EventAttachment.AnalysisStatus.FAILED,
            analysis_error='Another failure'
        )

        retry_failed_analyses()

        self.assertEqual(mock_delay.call_count, 2)
        call_ids = [call[0][0] for call in mock_delay.call_args_list]
        self.assertIn(failed1.id, call_ids)
        self.assertIn(failed2.id, call_ids)

    @patch('ai_assistant.tasks.analyze_attachment.delay')
    def test_retry_failed_analyses_ignores_pending_attachments(self, mock_delay):
        failed_attachment = self._create_failed_attachment()

        pdf_file = SimpleUploadedFile("pending.pdf", b'content', content_type="application/pdf")
        EventAttachment.objects.create(
            event=self.event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='pending.pdf',
            analysis_status=EventAttachment.AnalysisStatus.PENDING
        )

        retry_failed_analyses()

        mock_delay.assert_called_once_with(failed_attachment.id)

    @patch('ai_assistant.tasks.analyze_attachment.delay')
    def test_retry_failed_analyses_ignores_processing_attachments(self, mock_delay):
        failed_attachment = self._create_failed_attachment()

        pdf_file = SimpleUploadedFile("processing.pdf", b'content', content_type="application/pdf")
        EventAttachment.objects.create(
            event=self.event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='processing.pdf',
            analysis_status=EventAttachment.AnalysisStatus.PROCESSING
        )

        retry_failed_analyses()

        mock_delay.assert_called_once_with(failed_attachment.id)


class TestAnalyzeAttachmentEdgeCases(TestCase):
    """Additional edge case tests for attachment analysis."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.vehicle = Vehicle.objects.create(
            user=self.user,
            vehicle_type='motorcycle',
            brand='Kawasaki',
            model='Ninja 650',
            year=2022,
            current_km=5000
        )
        self.event = MaintenanceEvent.objects.create(
            vehicle=self.vehicle,
            task_code='tire_check',
            date='2026-02-10',
            km_at_service=4900
        )

    @patch('ai_assistant.tasks.PdfReader')
    def test_analyze_pdf_with_pdf_reader_exception_raises(self, mock_pdf_reader):
        pdf_file = SimpleUploadedFile("corrupt.pdf", b'corrupt', content_type="application/pdf")
        attachment = EventAttachment.objects.create(
            event=self.event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='corrupt.pdf'
        )

        mock_pdf_reader.side_effect = Exception("PDF is corrupted")

        with self.assertRaises(Exception) as context:
            _analyze_pdf(attachment, "test prompt")

        self.assertIn("PDF is corrupted", str(context.exception))

    @patch('builtins.open')
    def test_analyze_image_with_file_read_error_raises(self, mock_open_file):
        image_file = SimpleUploadedFile("image.png", b'image', content_type="image/png")
        attachment = EventAttachment.objects.create(
            event=self.event,
            file=image_file,
            file_type=EventAttachment.FileType.IMAGE,
            original_filename='image.png'
        )

        mock_open_file.side_effect = IOError("Cannot read file")

        with self.assertRaises(IOError) as context:
            _analyze_image(attachment, "test prompt")

        self.assertIn("Cannot read file", str(context.exception))

    @patch('ai_assistant.tasks.generate_text')
    @patch('ai_assistant.tasks.PdfReader')
    def test_analyze_pdf_with_multiple_empty_pages_returns_no_text(self, mock_pdf_reader, mock_generate_text):
        pdf_file = SimpleUploadedFile("empty.pdf", b'content', content_type="application/pdf")
        attachment = EventAttachment.objects.create(
            event=self.event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='empty.pdf'
        )

        empty_page = Mock()
        empty_page.extract_text.return_value = ""
        mock_reader_instance = Mock()
        mock_reader_instance.pages = [empty_page, empty_page, empty_page]
        mock_pdf_reader.return_value = mock_reader_instance

        result = _analyze_pdf(attachment, "test prompt")

        self.assertEqual(result, "No se pudo extraer texto del PDF.")
        mock_generate_text.assert_not_called()