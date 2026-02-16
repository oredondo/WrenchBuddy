import base64
import json
from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import Mock, patch, MagicMock, mock_open

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from requests.exceptions import RequestException, Timeout, HTTPError

from ai_assistant import ollama_client
from ai_assistant.handlers import handle_analysis_completed
from ai_assistant.parsers import parse_analysis_result, ParsedAnalysis
from ai_assistant.signals import attachment_analysis_completed
from ai_assistant.tasks import analyze_attachment, retry_failed_analyses, _analyze_pdf, _analyze_image
from maintenance.models import EventAttachment, MaintenanceEvent
from users.models import CustomUser
from vehicles.models import Vehicle


def _mock_openai_response(content, status_code=200):
    """Helper to create a mock OpenAI-compatible response."""
    mock_response = Mock()
    mock_response.status_code = status_code
    mock_response.json.return_value = {
        'choices': [{'message': {'content': content}}]
    }
    mock_response.raise_for_status = Mock()
    return mock_response


def _mock_login_response(token='fake-jwt-token'):
    """Helper to create a mock login response."""
    mock_response = Mock()
    mock_response.json.return_value = {'token': token}
    mock_response.raise_for_status = Mock()
    return mock_response


# Patch _get_token in most tests to avoid login calls
MOCK_TOKEN = 'test-jwt-token'


@override_settings(OPENWEBUI_EMAIL='test@example.com', OPENWEBUI_PASSWORD='testpass')
class TestOpenWebUIClient(TestCase):
    """Tests for ollama_client module (Open WebUI integration)."""

    def setUp(self):
        self.test_prompt = "Test prompt for generation"
        self.test_model = "qwen2.5:7b-instruct"
        self.test_vision_model = "llava:7b"
        self.test_image_base64 = base64.b64encode(b"fake_image_data").decode('utf-8')
        # Reset token cache between tests
        ollama_client._token_cache['token'] = None

    @patch('ai_assistant.ollama_client._get_token', return_value=MOCK_TOKEN)
    @patch('ai_assistant.ollama_client.requests.post')
    def test_generate_text_with_valid_response_returns_text(self, mock_post, _):
        expected_response = "This is the generated response text"
        mock_post.return_value = _mock_openai_response(expected_response)

        result = ollama_client.generate_text(self.test_prompt, self.test_model)

        self.assertEqual(result, expected_response)
        call_args = mock_post.call_args
        self.assertIn('/api/chat/completions', call_args[0][0])
        payload = call_args[1]['json']
        self.assertEqual(payload['model'], self.test_model)
        self.assertEqual(payload['messages'][0]['role'], 'user')
        self.assertEqual(payload['messages'][0]['content'], self.test_prompt)

    @override_settings(OPENWEBUI_TEXT_MODEL='custom-model')
    @patch('ai_assistant.ollama_client._get_token', return_value=MOCK_TOKEN)
    @patch('ai_assistant.ollama_client.requests.post')
    def test_generate_text_uses_model_from_settings(self, mock_post, _):
        mock_post.return_value = _mock_openai_response('test')

        ollama_client.generate_text(self.test_prompt)

        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['model'], 'custom-model')

    @patch('ai_assistant.ollama_client._get_token', return_value=MOCK_TOKEN)
    @patch('ai_assistant.ollama_client.requests.post')
    def test_generate_text_with_http_error_raises_exception(self, mock_post, _):
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = HTTPError("500 Server Error")
        mock_post.return_value = mock_response

        with self.assertRaises(HTTPError):
            ollama_client.generate_text(self.test_prompt)

    @patch('ai_assistant.ollama_client._get_token', return_value=MOCK_TOKEN)
    @patch('ai_assistant.ollama_client.requests.post')
    def test_generate_text_with_timeout_raises_exception(self, mock_post, _):
        mock_post.side_effect = Timeout("Request timed out")

        with self.assertRaises(Timeout):
            ollama_client.generate_text(self.test_prompt)

    @patch('ai_assistant.ollama_client._get_token', return_value=MOCK_TOKEN)
    @patch('ai_assistant.ollama_client.requests.post')
    def test_generate_text_with_connection_error_raises_exception(self, mock_post, _):
        mock_post.side_effect = RequestException("Connection refused")

        with self.assertRaises(RequestException):
            ollama_client.generate_text(self.test_prompt)

    @patch('ai_assistant.ollama_client._get_token', return_value=MOCK_TOKEN)
    @patch('ai_assistant.ollama_client.requests.post')
    def test_analyze_image_with_valid_response_returns_text(self, mock_post, _):
        expected_response = "Analysis of the image shows maintenance invoice"
        mock_post.return_value = _mock_openai_response(expected_response)

        result = ollama_client.analyze_image(
            self.test_image_base64,
            self.test_prompt,
            self.test_vision_model
        )

        self.assertEqual(result, expected_response)
        call_args = mock_post.call_args
        self.assertIn('/api/chat/completions', call_args[0][0])
        payload = call_args[1]['json']
        self.assertEqual(payload['model'], self.test_vision_model)
        content = payload['messages'][0]['content']
        self.assertIsInstance(content, list)
        self.assertEqual(content[0]['type'], 'text')
        self.assertEqual(content[1]['type'], 'image_url')

    @override_settings(OPENWEBUI_VISION_MODEL='custom-vision')
    @patch('ai_assistant.ollama_client._get_token', return_value=MOCK_TOKEN)
    @patch('ai_assistant.ollama_client.requests.post')
    def test_analyze_image_uses_model_from_settings(self, mock_post, _):
        mock_post.return_value = _mock_openai_response('test')

        ollama_client.analyze_image(self.test_image_base64, self.test_prompt)

        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['model'], 'custom-vision')

    @patch('ai_assistant.ollama_client._get_token', return_value=MOCK_TOKEN)
    @patch('ai_assistant.ollama_client.requests.post')
    def test_analyze_image_with_http_error_raises_exception(self, mock_post, _):
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = HTTPError("503 Service Unavailable")
        mock_post.return_value = mock_response

        with self.assertRaises(HTTPError):
            ollama_client.analyze_image(self.test_image_base64, self.test_prompt)

    @override_settings(OPENWEBUI_BASE_URL='https://custom-webui.example.com')
    @patch('ai_assistant.ollama_client._get_token', return_value=MOCK_TOKEN)
    @patch('ai_assistant.ollama_client.requests.post')
    def test_generate_text_uses_custom_base_url_from_settings(self, mock_post, _):
        mock_post.return_value = _mock_openai_response('test')

        ollama_client.generate_text(self.test_prompt)

        call_url = mock_post.call_args[0][0]
        self.assertTrue(call_url.startswith('https://custom-webui.example.com'))

    @patch('ai_assistant.ollama_client._get_token', return_value=MOCK_TOKEN)
    @patch('ai_assistant.ollama_client.requests.post')
    def test_generate_text_sends_bearer_token(self, mock_post, _):
        mock_post.return_value = _mock_openai_response('test')

        ollama_client.generate_text(self.test_prompt)

        headers = mock_post.call_args[1]['headers']
        self.assertEqual(headers['Authorization'], f'Bearer {MOCK_TOKEN}')

    def test_get_base_url_returns_default_when_setting_not_configured(self):
        result = ollama_client._get_base_url()

        self.assertIsInstance(result, str)
        self.assertTrue(result.startswith('http'))


@override_settings(OPENWEBUI_EMAIL='user@example.com', OPENWEBUI_PASSWORD='secret123')
class TestOpenWebUILogin(TestCase):
    """Tests for login and token caching."""

    def setUp(self):
        ollama_client._token_cache['token'] = None

    @patch('ai_assistant.ollama_client.requests.post')
    def test_login_sends_email_and_password(self, mock_post):
        mock_post.return_value = _mock_login_response('my-jwt-token')

        token = ollama_client._login()

        self.assertEqual(token, 'my-jwt-token')
        call_args = mock_post.call_args
        self.assertIn('/api/v1/auths/signin', call_args[0][0])
        self.assertEqual(call_args[1]['json'], {
            'email': 'user@example.com',
            'password': 'secret123',
        })

    @patch('ai_assistant.ollama_client.requests.post')
    def test_get_token_caches_after_first_login(self, mock_post):
        mock_post.return_value = _mock_login_response('cached-token')

        token1 = ollama_client._get_token()
        token2 = ollama_client._get_token()

        self.assertEqual(token1, 'cached-token')
        self.assertEqual(token2, 'cached-token')
        # Login should only be called once
        mock_post.assert_called_once()

    @patch('ai_assistant.ollama_client.requests.post')
    def test_invalidate_token_clears_cache(self, mock_post):
        mock_post.return_value = _mock_login_response('token-1')
        ollama_client._get_token()

        ollama_client.invalidate_token()

        mock_post.return_value = _mock_login_response('token-2')
        token = ollama_client._get_token()
        self.assertEqual(token, 'token-2')
        self.assertEqual(mock_post.call_count, 2)

    @override_settings(OPENWEBUI_EMAIL='', OPENWEBUI_PASSWORD='')
    def test_login_raises_when_credentials_not_configured(self):
        with self.assertRaises(ValueError) as ctx:
            ollama_client._login()
        self.assertIn('OPENWEBUI_EMAIL', str(ctx.exception))

    @patch('ai_assistant.ollama_client.requests.post')
    def test_login_raises_on_invalid_credentials(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = HTTPError("401 Unauthorized")
        mock_post.return_value = mock_response

        with self.assertRaises(HTTPError):
            ollama_client._login()

    @patch('ai_assistant.ollama_client.requests.post')
    def test_post_with_retry_re_authenticates_on_401(self, mock_post):
        """Test that a 401 triggers re-login and retries the request."""
        # First call: login succeeds
        login_response = _mock_login_response('token-1')
        # Second call: API returns 401
        unauthorized_response = Mock()
        unauthorized_response.status_code = 401
        # Third call: re-login succeeds
        relogin_response = _mock_login_response('token-2')
        # Fourth call: API succeeds
        success_response = _mock_openai_response('result')

        mock_post.side_effect = [
            login_response,       # initial login
            unauthorized_response, # first API call → 401
            relogin_response,     # re-login
            success_response,     # retry API call → success
        ]

        result = ollama_client.generate_text("test prompt")

        self.assertEqual(result, 'result')
        self.assertEqual(mock_post.call_count, 4)


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
        mock_analyze_pdf.side_effect = RequestException(error_message)

        with self.assertRaises(RequestException):
            analyze_attachment(attachment.id)

        attachment.refresh_from_db()
        self.assertEqual(attachment.analysis_status, EventAttachment.AnalysisStatus.FAILED)
        self.assertIn(error_message, attachment.analysis_error)

    @patch('ai_assistant.tasks._analyze_image')
    def test_analyze_attachment_with_image_failure_sets_failed_status(self, mock_analyze_image):
        attachment = self._create_image_attachment()
        error_message = "Vision model not available"
        mock_analyze_image.side_effect = HTTPError(error_message)

        with self.assertRaises(HTTPError):
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

        result = _analyze_pdf(attachment)

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

        result = _analyze_pdf(attachment)

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

        result = _analyze_pdf(attachment)

        prompt = mock_generate_text.call_args[0][0]
        self.assertIn("[...texto truncado]", prompt)
        self.assertLess(len(prompt), 5500)

    @patch('ai_assistant.tasks.ollama_analyze_image')
    @patch('builtins.open', new_callable=mock_open, read_data=b'fake_image_binary_data')
    def test_analyze_image_reads_file_and_calls_vision(self, mock_file, mock_analyze_image):
        attachment = self._create_image_attachment()
        expected_result = "Image shows maintenance receipt"
        mock_analyze_image.return_value = expected_result

        result = _analyze_image(attachment)

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
            _analyze_pdf(attachment)

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
            _analyze_image(attachment)

        self.assertIn("Cannot read file", str(context.exception))

    @patch('ai_assistant.tasks.generate_text')
    @patch('ai_assistant.tasks.PdfReader')
    def test_analyze_pdf_with_multiple_empty_pages_returns_no_text(self, mock_pdf_reader, mock_generate_text):
        pdf_file = SimpleUploadedFile("empty.pdf", b'empty', content_type="application/pdf")
        attachment = EventAttachment.objects.create(
            event=self.event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='empty.pdf'
        )

        mock_pages = [Mock() for _ in range(5)]
        for page in mock_pages:
            page.extract_text.return_value = None

        mock_reader_instance = Mock()
        mock_reader_instance.pages = mock_pages
        mock_pdf_reader.return_value = mock_reader_instance

        result = _analyze_pdf(attachment)

        self.assertEqual(result, "No se pudo extraer texto del PDF.")
        mock_generate_text.assert_not_called()

    @patch('ai_assistant.tasks.generate_text')
    @patch('ai_assistant.tasks.PdfReader')
    def test_analyze_pdf_with_mixed_pages_extracts_only_filled(self, mock_pdf_reader, mock_generate_text):
        pdf_file = SimpleUploadedFile("mixed.pdf", b'mixed', content_type="application/pdf")
        attachment = EventAttachment.objects.create(
            event=self.event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='mixed.pdf'
        )

        mock_page1 = Mock()
        mock_page1.extract_text.return_value = None
        mock_page2 = Mock()
        mock_page2.extract_text.return_value = "Invoice details"
        mock_page3 = Mock()
        mock_page3.extract_text.return_value = ""
        mock_page4 = Mock()
        mock_page4.extract_text.return_value = "Total cost"

        mock_reader_instance = Mock()
        mock_reader_instance.pages = [mock_page1, mock_page2, mock_page3, mock_page4]
        mock_pdf_reader.return_value = mock_reader_instance

        mock_generate_text.return_value = "Analysis complete"

        result = _analyze_pdf(attachment)

        self.assertEqual(result, "Analysis complete")
        prompt = mock_generate_text.call_args[0][0]
        self.assertIn("Invoice details", prompt)
        self.assertIn("Total cost", prompt)


class TestParseAnalysisResult(TestCase):
    """Tests for parse_analysis_result parser."""

    def test_valid_json_parses_all_fields(self):
        text = json.dumps({
            "tipo_servicio": "Cambio de aceite",
            "task_codes": ["oil_change"],
            "km": 15000,
            "coste_total": 75.50,
            "fecha": "2026-01-15",
            "taller": "Taller Pepe",
            "piezas": ["Filtro aceite", "Aceite 10W40"],
            "observaciones": "Todo correcto"
        })
        result = parse_analysis_result(text)

        self.assertEqual(result.task_codes, ["oil_change"])
        self.assertEqual(result.km, 15000)
        self.assertEqual(result.cost, Decimal("75.50"))
        self.assertEqual(result.date, date(2026, 1, 15))
        self.assertIn("Taller: Taller Pepe", result.notes_extra)
        self.assertIn("Filtro aceite", result.notes_extra)
        self.assertIn("Todo correcto", result.notes_extra)

    def test_json_with_code_fences_parses(self):
        text = '```json\n{"task_codes": ["brake_check"], "km": 8000, "coste_total": 120, "fecha": "2026-03-01", "taller": "No disponible", "piezas": "No disponible", "observaciones": "No disponible"}\n```'
        result = parse_analysis_result(text)

        self.assertEqual(result.task_codes, ["brake_check"])
        self.assertEqual(result.km, 8000)
        self.assertEqual(result.cost, Decimal("120.00"))

    def test_json_with_no_disponible_fields(self):
        text = json.dumps({
            "tipo_servicio": "Revisión",
            "task_codes": [],
            "km": "No disponible",
            "coste_total": "No disponible",
            "fecha": "No disponible",
            "taller": "No disponible",
            "piezas": "No disponible",
            "observaciones": "No disponible"
        })
        result = parse_analysis_result(text)

        self.assertIsNone(result.km)
        self.assertIsNone(result.cost)
        self.assertIsNone(result.date)
        self.assertEqual(result.notes_extra, '')

    def test_json_infers_task_code_from_tipo_servicio(self):
        text = json.dumps({
            "tipo_servicio": "Cambio de aceite y filtro",
            "task_codes": [],
            "km": None,
            "coste_total": None,
            "fecha": None,
            "taller": None,
            "piezas": None,
            "observaciones": None
        })
        result = parse_analysis_result(text)
        self.assertIn("oil_change", result.task_codes)

    def test_regex_fallback_extracts_cost_and_km(self):
        text = "Factura del taller.\nKm: 23000 km\nTotal: 95,50 €\nFecha: 15/03/2026"
        result = parse_analysis_result(text)

        self.assertEqual(result.km, 23000)
        self.assertEqual(result.cost, Decimal("95.50"))
        self.assertEqual(result.date, date(2026, 3, 15))

    def test_regex_fallback_detects_keywords(self):
        text = "Se realizó cambio de aceite y revisión de frenos. Total: 150 EUR"
        result = parse_analysis_result(text)

        self.assertIn("oil_change", result.task_codes)
        self.assertIn("brake_check", result.task_codes)
        self.assertEqual(result.cost, Decimal("150.00"))

    def test_invalid_json_falls_back_to_regex(self):
        text = "Not valid JSON at all {broken"
        result = parse_analysis_result(text)
        self.assertIsInstance(result, ParsedAnalysis)

    def test_json_filters_invalid_task_codes(self):
        text = json.dumps({
            "task_codes": ["oil_change", "invalid_code", "brake_check"],
            "km": None, "coste_total": None, "fecha": None,
            "taller": None, "piezas": None, "observaciones": None
        })
        result = parse_analysis_result(text)
        self.assertEqual(result.task_codes, ["oil_change", "brake_check"])

    def test_european_cost_format(self):
        text = json.dumps({
            "task_codes": [], "km": None, "coste_total": "1.234,56",
            "fecha": None, "taller": None, "piezas": None, "observaciones": None
        })
        result = parse_analysis_result(text)
        self.assertEqual(result.cost, Decimal("1234.56"))


class TestHandleAnalysisCompleted(TestCase):
    """Tests for handle_analysis_completed signal handler."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testhandler',
            email='handler@example.com',
            password='testpass123'
        )
        self.vehicle = Vehicle.objects.create(
            user=self.user,
            vehicle_type='motorcycle',
            brand='Honda',
            model='CB500F',
            year=2021,
            current_km=10000,
            usage_type='mixed'
        )

    def _create_event_with_attachment(self, **event_kwargs):
        defaults = {
            'vehicle': self.vehicle,
            'task_code': 'oil_change',
            'date': '2026-01-01',
            'km_at_service': 9000,
        }
        defaults.update(event_kwargs)
        event = MaintenanceEvent.objects.create(**defaults)
        pdf_file = SimpleUploadedFile("test.pdf", b'%PDF', content_type="application/pdf")
        attachment = EventAttachment.objects.create(
            event=event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='test.pdf'
        )
        return event, attachment

    def test_handler_overwrites_cost(self):
        event, attachment = self._create_event_with_attachment(cost=Decimal('50.00'))
        analysis = json.dumps({
            "task_codes": [], "km": None, "coste_total": 120.00,
            "fecha": None, "taller": None, "piezas": None, "observaciones": None
        })

        handle_analysis_completed(sender=None, attachment_id=attachment.id, analysis_result=analysis)

        event.refresh_from_db()
        self.assertEqual(event.cost, Decimal("120.00"))

    def test_handler_fills_empty_cost(self):
        event, attachment = self._create_event_with_attachment(cost=None)
        analysis = json.dumps({
            "task_codes": [], "km": None, "coste_total": 85.00,
            "fecha": None, "taller": None, "piezas": None, "observaciones": None
        })

        handle_analysis_completed(sender=None, attachment_id=attachment.id, analysis_result=analysis)

        event.refresh_from_db()
        self.assertEqual(event.cost, Decimal("85.00"))

    def test_handler_overwrites_km(self):
        event, attachment = self._create_event_with_attachment(km_at_service=9000)
        analysis = json.dumps({
            "task_codes": [], "km": 9500, "coste_total": None,
            "fecha": None, "taller": None, "piezas": None, "observaciones": None
        })

        handle_analysis_completed(sender=None, attachment_id=attachment.id, analysis_result=analysis)

        event.refresh_from_db()
        self.assertEqual(event.km_at_service, 9500)

    def test_handler_overwrites_date(self):
        event, attachment = self._create_event_with_attachment(date='2026-01-01')
        analysis = json.dumps({
            "task_codes": [], "km": None, "coste_total": None,
            "fecha": "2026-02-15", "taller": None, "piezas": None, "observaciones": None
        })

        handle_analysis_completed(sender=None, attachment_id=attachment.id, analysis_result=analysis)

        event.refresh_from_db()
        self.assertEqual(str(event.date), '2026-02-15')

    def test_handler_overwrites_task_code(self):
        event, attachment = self._create_event_with_attachment(task_code='oil_change')
        analysis = json.dumps({
            "task_codes": ["brake_check"], "km": None, "coste_total": None,
            "fecha": None, "taller": None, "piezas": None, "observaciones": None
        })

        handle_analysis_completed(sender=None, attachment_id=attachment.id, analysis_result=analysis)

        event.refresh_from_db()
        self.assertEqual(event.task_code, 'brake_check')

    def test_handler_appends_notes_with_separator(self):
        event, attachment = self._create_event_with_attachment(notes='Notas originales')
        analysis = json.dumps({
            "task_codes": [], "km": None, "coste_total": None,
            "fecha": None, "taller": "Taller ABC", "piezas": None,
            "observaciones": None
        })

        handle_analysis_completed(sender=None, attachment_id=attachment.id, analysis_result=analysis)

        event.refresh_from_db()
        self.assertIn('Notas originales', event.notes)
        self.assertIn('--- Análisis adjunto ---', event.notes)
        self.assertIn('Taller: Taller ABC', event.notes)

    def test_handler_sets_notes_when_empty(self):
        event, attachment = self._create_event_with_attachment(notes='')
        analysis = json.dumps({
            "task_codes": [], "km": None, "coste_total": None,
            "fecha": None, "taller": "MotoShop", "piezas": None,
            "observaciones": None
        })

        handle_analysis_completed(sender=None, attachment_id=attachment.id, analysis_result=analysis)

        event.refresh_from_db()
        self.assertIn('Taller: MotoShop', event.notes)
        self.assertNotIn('--- Análisis adjunto ---', event.notes)

    def test_handler_no_update_when_no_data(self):
        event, attachment = self._create_event_with_attachment(
            cost=Decimal('50.00'), notes='Original'
        )
        analysis = json.dumps({
            "task_codes": [], "km": None, "coste_total": None,
            "fecha": None, "taller": "No disponible", "piezas": "No disponible",
            "observaciones": "No disponible"
        })

        handle_analysis_completed(sender=None, attachment_id=attachment.id, analysis_result=analysis)

        event.refresh_from_db()
        self.assertEqual(event.cost, Decimal('50.00'))
        self.assertEqual(event.notes, 'Original')

    def test_handler_nonexistent_attachment_does_not_crash(self):
        handle_analysis_completed(sender=None, attachment_id=99999, analysis_result='{}')


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True
)
class TestSignalIntegration(TestCase):
    """Tests that the signal fires from analyze_attachment task."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='signaluser',
            email='signal@example.com',
            password='testpass123'
        )
        self.vehicle = Vehicle.objects.create(
            user=self.user,
            vehicle_type='motorcycle',
            brand='Suzuki',
            model='GSX-R750',
            year=2023,
            current_km=3000,
            usage_type='mixed'
        )
        self.event = MaintenanceEvent.objects.create(
            vehicle=self.vehicle,
            task_code='oil_change',
            date='2026-01-01',
            km_at_service=2500,
        )

    @patch('ai_assistant.tasks._analyze_pdf')
    def test_signal_fires_on_successful_analysis(self, mock_analyze_pdf):
        analysis_json = json.dumps({
            "task_codes": ["oil_change"], "km": 3000, "coste_total": 65.00,
            "fecha": "2026-01-20", "taller": "Moto Center",
            "piezas": ["Aceite 10W40"], "observaciones": None
        })
        mock_analyze_pdf.return_value = analysis_json

        pdf_file = SimpleUploadedFile("invoice.pdf", b'%PDF', content_type="application/pdf")
        attachment = EventAttachment.objects.create(
            event=self.event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='invoice.pdf'
        )

        received = []

        def signal_receiver(sender, attachment_id, analysis_result, **kwargs):
            received.append({'attachment_id': attachment_id, 'analysis_result': analysis_result})

        attachment_analysis_completed.connect(signal_receiver)
        try:
            analyze_attachment(attachment.id)
        finally:
            attachment_analysis_completed.disconnect(signal_receiver)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]['attachment_id'], attachment.id)
        self.assertEqual(received[0]['analysis_result'], analysis_json)

    @patch('ai_assistant.tasks._analyze_pdf')
    def test_signal_not_fired_on_failed_analysis(self, mock_analyze_pdf):
        mock_analyze_pdf.side_effect = Exception("Analysis failed")

        pdf_file = SimpleUploadedFile("fail.pdf", b'%PDF', content_type="application/pdf")
        attachment = EventAttachment.objects.create(
            event=self.event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='fail.pdf'
        )

        received = []

        def signal_receiver(sender, attachment_id, analysis_result, **kwargs):
            received.append(True)

        attachment_analysis_completed.connect(signal_receiver)
        try:
            with self.assertRaises(Exception):
                analyze_attachment(attachment.id)
        finally:
            attachment_analysis_completed.disconnect(signal_receiver)

        self.assertEqual(len(received), 0)


# ============================================================================
# Tests for "Qué me toca ahora" — AI Recommendations
# ============================================================================

from ai_assistant.context_builder import build_vehicle_context
from ai_assistant.recommendation_prompt import (
    parse_recommendations, build_recommendation_prompt, RecommendationItem,
)
from ai_assistant.services import generate_recommendations
from maintenance.models import TaskCatalog, MaintenanceTask


class _RecommendationTestBase(TestCase):
    """Shared setup for recommendation tests."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='rectest', email='rectest@example.com', password='testpass123'
        )
        self.vehicle = Vehicle.objects.create(
            user=self.user,
            vehicle_type='motorcycle',
            brand='Yamaha',
            model='MT-07',
            year=2022,
            current_km=15000,
            displacement=689,
            usage_type='mixed',
        )
        # Create catalog entries
        self.catalog_oil = TaskCatalog.objects.create(
            task_code='oil_change',
            vehicle_type='motorcycle',
            name='Cambio aceite',
            default_interval_km=5000,
            default_interval_months=12,
            is_safety_critical=False,
        )
        self.catalog_chain = TaskCatalog.objects.create(
            task_code='chain_service',
            vehicle_type='motorcycle',
            name='Servicio cadena',
            default_interval_km=1000,
            default_interval_months=3,
            is_safety_critical=False,
        )
        self.catalog_brakes = TaskCatalog.objects.create(
            task_code='brake_check',
            vehicle_type='motorcycle',
            name='Revisión frenos',
            default_interval_km=10000,
            default_interval_months=12,
            is_safety_critical=True,
        )
        # Car catalog entry — should NOT appear for motorcycle
        TaskCatalog.objects.create(
            task_code='itv',
            vehicle_type='car',
            name='ITV Coche',
            default_interval_km=None,
            default_interval_months=24,
            is_safety_critical=False,
        )


class TestBuildVehicleContext(_RecommendationTestBase):
    """Tests for context_builder.build_vehicle_context."""

    def test_vehicle_info_included(self):
        ctx = build_vehicle_context(self.vehicle.id)
        info = ctx['vehicle_info']
        self.assertEqual(info['brand'], 'Yamaha')
        self.assertEqual(info['model'], 'MT-07')
        self.assertEqual(info['current_km'], 15000)
        self.assertEqual(info['displacement'], 689)
        self.assertEqual(info['usage_type'], 'mixed')

    def test_catalog_filtered_by_vehicle_type(self):
        ctx = build_vehicle_context(self.vehicle.id)
        codes = [e['task_code'] for e in ctx['catalog_entries']]
        self.assertIn('oil_change', codes)
        self.assertIn('chain_service', codes)
        self.assertIn('brake_check', codes)
        # Car-only entry should NOT be included
        self.assertNotIn('itv', codes)

    def test_catalog_text_format(self):
        ctx = build_vehicle_context(self.vehicle.id)
        self.assertIn('oil_change', ctx['catalog_text'])
        self.assertIn('every 5000 km', ctx['catalog_text'])
        self.assertIn('[SAFETY CRITICAL]', ctx['catalog_text'])

    def test_no_events_returns_empty_list(self):
        ctx = build_vehicle_context(self.vehicle.id)
        self.assertEqual(ctx['last_events'], [])
        self.assertIn('No maintenance history', ctx['full_prompt_context'])

    def test_last_event_per_task_code(self):
        # Create two oil_change events — only the latest should appear
        MaintenanceEvent.objects.create(
            vehicle=self.vehicle, task_code='oil_change',
            date=date(2025, 1, 1), km_at_service=5000,
        )
        MaintenanceEvent.objects.create(
            vehicle=self.vehicle, task_code='oil_change',
            date=date(2025, 6, 1), km_at_service=10000,
        )
        MaintenanceEvent.objects.create(
            vehicle=self.vehicle, task_code='chain_service',
            date=date(2025, 3, 1), km_at_service=7000,
        )

        ctx = build_vehicle_context(self.vehicle.id)
        events = ctx['last_events']
        self.assertEqual(len(events), 2)

        oil_event = next(e for e in events if e['task_code'] == 'oil_change')
        self.assertEqual(oil_event['km_at_service'], 10000)
        self.assertEqual(oil_event['km_ago'], 5000)

        chain_event = next(e for e in events if e['task_code'] == 'chain_service')
        self.assertEqual(chain_event['km_at_service'], 7000)

    def test_vehicle_not_found_raises(self):
        with self.assertRaises(Vehicle.DoesNotExist):
            build_vehicle_context(99999)

    def test_full_prompt_context_contains_all_sections(self):
        ctx = build_vehicle_context(self.vehicle.id)
        prompt = ctx['full_prompt_context']
        self.assertIn('=== VEHICLE ===', prompt)
        self.assertIn('=== MAINTENANCE CATALOG ===', prompt)
        self.assertIn('=== LAST MAINTENANCE PER TASK ===', prompt)
        self.assertIn('=== CURRENT PENDING TASKS ===', prompt)
        self.assertIn('Yamaha MT-07', prompt)
        self.assertIn('689cc', prompt)

    def test_pending_tasks_included(self):
        MaintenanceTask.objects.create(
            vehicle=self.vehicle, task_code='oil_change',
            priority='high', due_km=15000, status='pending',
        )
        ctx = build_vehicle_context(self.vehicle.id)
        self.assertIn('oil_change', ctx['pending_tasks_text'])
        self.assertEqual(len(ctx['pending_tasks']), 1)


class TestParseRecommendations(TestCase):
    """Tests for recommendation_prompt.parse_recommendations."""

    def test_valid_json_array(self):
        raw = json.dumps([
            {
                'task_code': 'oil_change',
                'priority': 'high',
                'due_km': 15000,
                'due_date': '2026-03-01',
                'explanation': 'Overdue',
                'estimated_cost': 45.00,
            },
            {
                'task_code': 'chain_service',
                'priority': 'low',
                'explanation': 'Upcoming',
            },
        ])
        items = parse_recommendations(raw)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].task_code, 'oil_change')
        self.assertEqual(items[0].priority, 'high')
        self.assertEqual(items[0].due_km, 15000)
        self.assertEqual(items[0].due_date, date(2026, 3, 1))
        self.assertEqual(items[0].estimated_cost, Decimal('45.00'))
        self.assertEqual(items[1].task_code, 'chain_service')

    def test_json_with_markdown_fences(self):
        raw = '```json\n[{"task_code": "oil_change", "priority": "high"}]\n```'
        items = parse_recommendations(raw)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].task_code, 'oil_change')

    def test_invalid_task_code_filtered(self):
        raw = json.dumps([
            {'task_code': 'oil_change', 'priority': 'high'},
            {'task_code': 'fake_task', 'priority': 'low'},
        ])
        items = parse_recommendations(raw)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].task_code, 'oil_change')

    def test_empty_array(self):
        items = parse_recommendations('[]')
        self.assertEqual(items, [])

    def test_unparseable_text(self):
        items = parse_recommendations('I cannot generate recommendations right now.')
        self.assertEqual(items, [])

    def test_invalid_priority_defaults_to_medium(self):
        raw = json.dumps([{'task_code': 'oil_change', 'priority': 'critical'}])
        items = parse_recommendations(raw)
        self.assertEqual(items[0].priority, 'medium')

    def test_json_embedded_in_text(self):
        raw = 'Here are the recommendations:\n[{"task_code": "brake_check", "priority": "high"}]\nHope this helps!'
        items = parse_recommendations(raw)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].task_code, 'brake_check')

    def test_json_object_with_recommendations_key(self):
        raw = json.dumps({
            'recommendations': [
                {'task_code': 'oil_change', 'priority': 'high'},
            ]
        })
        items = parse_recommendations(raw)
        self.assertEqual(len(items), 1)

    def test_missing_optional_fields(self):
        raw = json.dumps([{'task_code': 'oil_change', 'priority': 'low'}])
        items = parse_recommendations(raw)
        self.assertIsNone(items[0].due_km)
        self.assertIsNone(items[0].due_date)
        self.assertIsNone(items[0].estimated_cost)
        self.assertEqual(items[0].explanation, '')

    def test_build_recommendation_prompt_includes_context(self):
        prompt = build_recommendation_prompt('test context here')
        self.assertIn('test context here', prompt)
        self.assertIn('task_code', prompt)


class TestGenerateRecommendations(_RecommendationTestBase):
    """Tests for services.generate_recommendations."""

    @patch('ai_assistant.services.generate_text')
    def test_creates_tasks_from_ai_response(self, mock_generate):
        mock_generate.return_value = json.dumps([
            {
                'task_code': 'oil_change',
                'priority': 'high',
                'due_km': 15000,
                'due_date': '2026-03-01',
                'explanation': 'Overdue oil change',
                'estimated_cost': 45.00,
            },
            {
                'task_code': 'chain_service',
                'priority': 'medium',
                'explanation': 'Due soon',
            },
        ])

        tasks = generate_recommendations(self.vehicle.id)
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0].task_code, 'oil_change')
        self.assertEqual(tasks[0].priority, 'high')
        self.assertEqual(tasks[0].due_km, 15000)
        self.assertEqual(tasks[0].vehicle_id, self.vehicle.id)
        self.assertEqual(tasks[0].status, 'pending')

        # Verify persisted in DB
        db_tasks = MaintenanceTask.objects.filter(
            vehicle=self.vehicle, status='pending'
        )
        self.assertEqual(db_tasks.count(), 2)

    @patch('ai_assistant.services.generate_text')
    def test_replaces_pending_tasks(self, mock_generate):
        # Pre-existing pending task
        MaintenanceTask.objects.create(
            vehicle=self.vehicle, task_code='oil_change',
            priority='low', status='pending',
        )
        mock_generate.return_value = json.dumps([
            {'task_code': 'chain_service', 'priority': 'high'},
        ])

        tasks = generate_recommendations(self.vehicle.id)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].task_code, 'chain_service')

        # Old pending task should be gone
        pending = MaintenanceTask.objects.filter(
            vehicle=self.vehicle, status='pending'
        )
        self.assertEqual(pending.count(), 1)
        self.assertEqual(pending.first().task_code, 'chain_service')

    @patch('ai_assistant.services.generate_text')
    def test_does_not_delete_completed_or_dismissed(self, mock_generate):
        MaintenanceTask.objects.create(
            vehicle=self.vehicle, task_code='oil_change',
            priority='high', status='completed',
        )
        MaintenanceTask.objects.create(
            vehicle=self.vehicle, task_code='chain_service',
            priority='medium', status='dismissed',
        )
        mock_generate.return_value = '[]'

        generate_recommendations(self.vehicle.id)

        self.assertEqual(
            MaintenanceTask.objects.filter(vehicle=self.vehicle, status='completed').count(), 1
        )
        self.assertEqual(
            MaintenanceTask.objects.filter(vehicle=self.vehicle, status='dismissed').count(), 1
        )

    @patch('ai_assistant.services.generate_text')
    def test_empty_response_clears_pending(self, mock_generate):
        MaintenanceTask.objects.create(
            vehicle=self.vehicle, task_code='oil_change',
            priority='high', status='pending',
        )
        mock_generate.return_value = '[]'

        tasks = generate_recommendations(self.vehicle.id)
        self.assertEqual(len(tasks), 0)
        self.assertEqual(
            MaintenanceTask.objects.filter(vehicle=self.vehicle, status='pending').count(), 0
        )

    @patch('ai_assistant.services.generate_text')
    def test_ai_failure_propagates(self, mock_generate):
        mock_generate.side_effect = Exception("AI unavailable")
        with self.assertRaises(Exception):
            generate_recommendations(self.vehicle.id)


class TestRecommendationView(_RecommendationTestBase):
    """Tests for the recommendation API endpoint."""

    def setUp(self):
        super().setUp()
        self.url = f'/api/ai/recommendations/{self.vehicle.id}/'

    @patch('ai_assistant.services.generate_text')
    def test_returns_recommendations(self, mock_generate):
        mock_generate.return_value = json.dumps([
            {
                'task_code': 'oil_change',
                'priority': 'high',
                'due_km': 15000,
                'explanation': 'Overdue',
                'estimated_cost': 45.00,
            },
        ])
        self.client.force_login(self.user)
        response = self.client.post(self.url, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(len(data['recommendations']), 1)
        self.assertEqual(data['recommendations'][0]['task_code'], 'oil_change')
        self.assertEqual(data['recommendations'][0]['task_name'], 'Cambio aceite')

    def test_404_for_other_users_vehicle(self):
        other_user = CustomUser.objects.create_user(
            username='otheruser', email='other@example.com', password='testpass123'
        )
        self.client.force_login(other_user)
        response = self.client.post(self.url, content_type='application/json')
        self.assertEqual(response.status_code, 404)

    def test_404_for_nonexistent_vehicle(self):
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/ai/recommendations/99999/',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    @patch('ai_assistant.services.generate_recommendations')
    def test_503_on_ai_failure(self, mock_gen):
        mock_gen.side_effect = Exception("AI down")
        self.client.force_login(self.user)
        response = self.client.post(self.url, content_type='application/json')
        self.assertEqual(response.status_code, 503)
        self.assertIn('error', response.json())

    def test_401_without_auth(self):
        response = self.client.post(self.url, content_type='application/json')
        self.assertIn(response.status_code, [401, 403])
