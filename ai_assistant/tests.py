import base64
import json
from decimal import Decimal
from io import BytesIO
from unittest.mock import Mock, patch, MagicMock, mock_open

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from requests.exceptions import RequestException, Timeout, HTTPError

from ai_assistant import ollama_client
from ai_assistant.tasks import analyze_attachment, retry_failed_analyses, _analyze_pdf, _analyze_image
from maintenance.models import EventAttachment, MaintenanceEvent
from users.models import CustomUser
from vehicles.models import Vehicle


class TestOllamaClient(TestCase):
    """Tests for ollama_client module functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_prompt = "Test prompt for generation"
        self.test_model = "qwen2.5:7b-instruct"
        self.test_vision_model = "llava:7b"
        self.test_image_base64 = base64.b64encode(b"fake_image_data").decode('utf-8')

    @patch('ai_assistant.ollama_client.requests.post')
    def test_generate_text_with_valid_response_returns_text(self, mock_post):
        # Arrange
        expected_response = "This is the generated response text"
        mock_response = Mock()
        mock_response.json.return_value = {'response': expected_response}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        # Act
        result = ollama_client.generate_text(self.test_prompt, self.test_model)

        # Assert
        self.assertEqual(result, expected_response)
        mock_post.assert_called_once_with(
            f"{ollama_client._get_base_url()}/api/generate",
            json={
                'model': self.test_model,
                'prompt': self.test_prompt,
                'stream': False,
            },
            timeout=300
        )

    @patch('ai_assistant.ollama_client.requests.post')
    def test_generate_text_uses_default_model(self, mock_post):
        # Arrange
        mock_response = Mock()
        mock_response.json.return_value = {'response': 'test'}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        # Act
        ollama_client.generate_text(self.test_prompt)

        # Assert
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]['json']['model'], 'qwen2.5:7b-instruct')

    @patch('ai_assistant.ollama_client.requests.post')
    def test_generate_text_with_http_error_raises_exception(self, mock_post):
        # Arrange
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = HTTPError("500 Server Error")
        mock_post.return_value = mock_response

        # Act & Assert
        with self.assertRaises(HTTPError):
            ollama_client.generate_text(self.test_prompt)

    @patch('ai_assistant.ollama_client.requests.post')
    def test_generate_text_with_timeout_raises_exception(self, mock_post):
        # Arrange
        mock_post.side_effect = Timeout("Request timed out")

        # Act & Assert
        with self.assertRaises(Timeout):
            ollama_client.generate_text(self.test_prompt)

    @patch('ai_assistant.ollama_client.requests.post')
    def test_generate_text_with_connection_error_raises_exception(self, mock_post):
        # Arrange
        mock_post.side_effect = RequestException("Connection refused")

        # Act & Assert
        with self.assertRaises(RequestException):
            ollama_client.generate_text(self.test_prompt)

    @patch('ai_assistant.ollama_client.requests.post')
    def test_analyze_image_with_valid_response_returns_text(self, mock_post):
        # Arrange
        expected_response = "Analysis of the image shows maintenance invoice"
        mock_response = Mock()
        mock_response.json.return_value = {'response': expected_response}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        # Act
        result = ollama_client.analyze_image(
            self.test_image_base64,
            self.test_prompt,
            self.test_vision_model
        )

        # Assert
        self.assertEqual(result, expected_response)
        mock_post.assert_called_once_with(
            f"{ollama_client._get_base_url()}/api/generate",
            json={
                'model': self.test_vision_model,
                'prompt': self.test_prompt,
                'images': [self.test_image_base64],
                'stream': False,
            },
            timeout=300
        )

    @patch('ai_assistant.ollama_client.requests.post')
    def test_analyze_image_uses_default_vision_model(self, mock_post):
        # Arrange
        mock_response = Mock()
        mock_response.json.return_value = {'response': 'test'}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        # Act
        ollama_client.analyze_image(self.test_image_base64, self.test_prompt)

        # Assert
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]['json']['model'], 'llava:7b')

    @patch('ai_assistant.ollama_client.requests.post')
    def test_analyze_image_with_http_error_raises_exception(self, mock_post):
        # Arrange
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = HTTPError("503 Service Unavailable")
        mock_post.return_value = mock_response

        # Act & Assert
        with self.assertRaises(HTTPError):
            ollama_client.analyze_image(self.test_image_base64, self.test_prompt)

    @override_settings(OLLAMA_BASE_URL='http://custom-ollama:8080')
    @patch('ai_assistant.ollama_client.requests.post')
    def test_generate_text_uses_custom_base_url_from_settings(self, mock_post):
        # Arrange
        mock_response = Mock()
        mock_response.json.return_value = {'response': 'test'}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        # Act
        ollama_client.generate_text(self.test_prompt)

        # Assert
        call_args = mock_post.call_args
        self.assertTrue(call_args[0][0].startswith('http://custom-ollama:8080'))

    def test_get_base_url_returns_default_when_setting_not_configured(self):
        # Act
        result = ollama_client._get_base_url()

        # Assert
        # Should return default or configured value
        self.assertIsInstance(result, str)
        self.assertTrue(result.startswith('http'))


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True
)
class TestAnalyzeAttachmentTask(TestCase):
    """Tests for analyze_attachment Celery task."""

    def setUp(self):
        """Set up test data for attachment analysis."""
        # Create user
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create vehicle
        self.vehicle = Vehicle.objects.create(
            user=self.user,
            vehicle_type='motorcycle',
            brand='Honda',
            model='CBR600RR',
            year=2020,
            current_km=15000,
            usage_type='mixed'
        )

        # Create maintenance event
        self.event = MaintenanceEvent.objects.create(
            vehicle=self.vehicle,
            task_code='oil_change',
            date='2026-01-15',
            km_at_service=14500,
            notes='Oil change service',
            cost=Decimal('75.50')
        )

    def _create_pdf_attachment(self):
        """Helper to create a PDF attachment."""
        pdf_content = b'%PDF-1.4 fake pdf content'
        pdf_file = SimpleUploadedFile(
            "invoice.pdf",
            pdf_content,
            content_type="application/pdf"
        )
        return EventAttachment.objects.create(
            event=self.event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='invoice.pdf'
        )

    def _create_image_attachment(self):
        """Helper to create an image attachment."""
        image_content = b'\x89PNG\r\n\x1a\n fake png content'
        image_file = SimpleUploadedFile(
            "receipt.png",
            image_content,
            content_type="image/png"
        )
        return EventAttachment.objects.create(
            event=self.event,
            file=image_file,
            file_type=EventAttachment.FileType.IMAGE,
            original_filename='receipt.png'
        )

    def test_analyze_attachment_with_nonexistent_id_logs_error_and_returns(self):
        # Arrange
        nonexistent_id = 99999

        # Act
        result = analyze_attachment(nonexistent_id)

        # Assert
        self.assertIsNone(result)
        # Task should not crash, just log and return

    @patch('ai_assistant.tasks._analyze_pdf')
    def test_analyze_attachment_with_pdf_sets_processing_status(self, mock_analyze_pdf):
        # Arrange
        attachment = self._create_pdf_attachment()
        mock_analyze_pdf.return_value = "Analyzed PDF content"

        # Act
        analyze_attachment(attachment.id)

        # Assert
        attachment.refresh_from_db()
        self.assertEqual(attachment.analysis_status, EventAttachment.AnalysisStatus.COMPLETED)

    @patch('ai_assistant.tasks._analyze_pdf')
    def test_analyze_attachment_with_pdf_success_updates_result(self, mock_analyze_pdf):
        # Arrange
        attachment = self._create_pdf_attachment()
        expected_result = "Service type: Oil change\nCost: 75.50 EUR\nDate: 15/01/2026"
        mock_analyze_pdf.return_value = expected_result

        # Act
        analyze_attachment(attachment.id)

        # Assert
        attachment.refresh_from_db()
        self.assertEqual(attachment.analysis_status, EventAttachment.AnalysisStatus.COMPLETED)
        self.assertEqual(attachment.analysis_result, expected_result)
        self.assertIsNone(attachment.analysis_error)

    @patch('ai_assistant.tasks._analyze_image')
    def test_analyze_attachment_with_image_success_updates_result(self, mock_analyze_image):
        # Arrange
        attachment = self._create_image_attachment()
        expected_result = "Invoice from workshop showing brake service"
        mock_analyze_image.return_value = expected_result

        # Act
        analyze_attachment(attachment.id)

        # Assert
        attachment.refresh_from_db()
        self.assertEqual(attachment.analysis_status, EventAttachment.AnalysisStatus.COMPLETED)
        self.assertEqual(attachment.analysis_result, expected_result)
        self.assertIsNone(attachment.analysis_error)

    @patch('ai_assistant.tasks._analyze_pdf')
    def test_analyze_attachment_with_pdf_failure_sets_failed_status(self, mock_analyze_pdf):
        # Arrange
        attachment = self._create_pdf_attachment()
        error_message = "Ollama service unavailable"
        mock_analyze_pdf.side_effect = RequestException(error_message)

        # Act & Assert
        # Task will retry and eventually raise, but in eager mode it propagates
        with self.assertRaises(RequestException):
            analyze_attachment(attachment.id)

        attachment.refresh_from_db()
        self.assertEqual(attachment.analysis_status, EventAttachment.AnalysisStatus.FAILED)
        self.assertIn(error_message, attachment.analysis_error)

    @patch('ai_assistant.tasks._analyze_image')
    def test_analyze_attachment_with_image_failure_sets_failed_status(self, mock_analyze_image):
        # Arrange
        attachment = self._create_image_attachment()
        error_message = "Vision model not available"
        mock_analyze_image.side_effect = HTTPError(error_message)

        # Act & Assert
        with self.assertRaises(HTTPError):
            analyze_attachment(attachment.id)

        attachment.refresh_from_db()
        self.assertEqual(attachment.analysis_status, EventAttachment.AnalysisStatus.FAILED)
        self.assertIn(error_message, attachment.analysis_error)

    @patch('ai_assistant.tasks._analyze_pdf')
    def test_analyze_attachment_clears_previous_error_on_success(self, mock_analyze_pdf):
        # Arrange
        attachment = self._create_pdf_attachment()
        attachment.analysis_status = EventAttachment.AnalysisStatus.FAILED
        attachment.analysis_error = "Previous error"
        attachment.save()

        mock_analyze_pdf.return_value = "Success result"

        # Act
        analyze_attachment(attachment.id)

        # Assert
        attachment.refresh_from_db()
        self.assertEqual(attachment.analysis_status, EventAttachment.AnalysisStatus.COMPLETED)
        self.assertIsNone(attachment.analysis_error)

    @patch('ai_assistant.tasks.generate_text')
    @patch('ai_assistant.tasks.PdfReader')
    def test_analyze_pdf_with_valid_pdf_extracts_text_and_calls_ollama(self, mock_pdf_reader, mock_generate_text):
        # Arrange
        attachment = self._create_pdf_attachment()

        # Mock PDF reader
        mock_page1 = Mock()
        mock_page1.extract_text.return_value = "Invoice for oil change service"
        mock_page2 = Mock()
        mock_page2.extract_text.return_value = "Total: 75.50 EUR"

        mock_reader_instance = Mock()
        mock_reader_instance.pages = [mock_page1, mock_page2]
        mock_pdf_reader.return_value = mock_reader_instance

        expected_ai_response = "Analyzed invoice data"
        mock_generate_text.return_value = expected_ai_response

        # Act
        result = _analyze_pdf(attachment)

        # Assert
        self.assertEqual(result, expected_ai_response)
        mock_pdf_reader.assert_called_once()
        mock_generate_text.assert_called_once()

        # Check that prompt contains extracted text
        call_args = mock_generate_text.call_args
        prompt = call_args[0][0]
        self.assertIn("Invoice for oil change service", prompt)
        self.assertIn("Total: 75.50 EUR", prompt)

    @patch('ai_assistant.tasks.generate_text')
    @patch('ai_assistant.tasks.PdfReader')
    def test_analyze_pdf_with_empty_pdf_returns_no_text_message(self, mock_pdf_reader, mock_generate_text):
        # Arrange
        attachment = self._create_pdf_attachment()

        # Mock PDF with no extractable text
        mock_page = Mock()
        mock_page.extract_text.return_value = ""

        mock_reader_instance = Mock()
        mock_reader_instance.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader_instance

        # Act
        result = _analyze_pdf(attachment)

        # Assert
        self.assertEqual(result, "No se pudo extraer texto del PDF.")
        mock_generate_text.assert_not_called()

    @patch('ai_assistant.tasks.generate_text')
    @patch('ai_assistant.tasks.PdfReader')
    def test_analyze_pdf_truncates_long_text(self, mock_pdf_reader, mock_generate_text):
        # Arrange
        attachment = self._create_pdf_attachment()

        # Create very long text (over 4000 chars)
        long_text = "A" * 5000
        mock_page = Mock()
        mock_page.extract_text.return_value = long_text

        mock_reader_instance = Mock()
        mock_reader_instance.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader_instance

        mock_generate_text.return_value = "Analysis"

        # Act
        result = _analyze_pdf(attachment)

        # Assert
        call_args = mock_generate_text.call_args
        prompt = call_args[0][0]
        # Should contain truncation marker
        self.assertIn("[...texto truncado]", prompt)
        # Should not contain full original text
        self.assertLess(len(prompt), 5500)

    @patch('ai_assistant.tasks.ollama_analyze_image')
    @patch('builtins.open', new_callable=mock_open, read_data=b'fake_image_binary_data')
    def test_analyze_image_reads_file_and_calls_ollama(self, mock_file, mock_analyze_image):
        # Arrange
        attachment = self._create_image_attachment()
        expected_result = "Image shows maintenance receipt"
        mock_analyze_image.return_value = expected_result

        # Act
        result = _analyze_image(attachment)

        # Assert
        self.assertEqual(result, expected_result)
        mock_analyze_image.assert_called_once()

        # Verify base64 encoding was called
        call_args = mock_analyze_image.call_args
        image_base64 = call_args[0][0]
        self.assertIsInstance(image_base64, str)
        # Should be valid base64
        decoded = base64.b64decode(image_base64)
        self.assertEqual(decoded, b'fake_image_binary_data')


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True
)
class TestRetryFailedAnalysesTask(TestCase):
    """Tests for retry_failed_analyses Celery task."""

    def setUp(self):
        """Set up test data."""
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
        """Helper to create a failed attachment."""
        pdf_file = SimpleUploadedFile("failed.pdf", b'content', content_type="application/pdf")
        attachment = EventAttachment.objects.create(
            event=self.event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='failed.pdf',
            analysis_status=EventAttachment.AnalysisStatus.FAILED,
            analysis_error='Previous failure'
        )
        return attachment

    def test_retry_failed_analyses_with_no_failed_attachments_does_nothing(self):
        # Arrange
        # Create a completed attachment
        pdf_file = SimpleUploadedFile("success.pdf", b'content', content_type="application/pdf")
        EventAttachment.objects.create(
            event=self.event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='success.pdf',
            analysis_status=EventAttachment.AnalysisStatus.COMPLETED
        )

        # Act
        with patch('ai_assistant.tasks.analyze_attachment.delay') as mock_delay:
            retry_failed_analyses()

            # Assert
            mock_delay.assert_not_called()

    @patch('ai_assistant.tasks.analyze_attachment.delay')
    def test_retry_failed_analyses_dispatches_task_for_single_failed_attachment(self, mock_delay):
        # Arrange
        failed_attachment = self._create_failed_attachment()

        # Act
        retry_failed_analyses()

        # Assert
        mock_delay.assert_called_once_with(failed_attachment.id)

    @patch('ai_assistant.tasks.analyze_attachment.delay')
    def test_retry_failed_analyses_dispatches_tasks_for_multiple_failed_attachments(self, mock_delay):
        # Arrange
        failed1 = self._create_failed_attachment()

        # Create second event and failed attachment
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

        # Act
        retry_failed_analyses()

        # Assert
        self.assertEqual(mock_delay.call_count, 2)
        call_ids = [call[0][0] for call in mock_delay.call_args_list]
        self.assertIn(failed1.id, call_ids)
        self.assertIn(failed2.id, call_ids)

    @patch('ai_assistant.tasks.analyze_attachment.delay')
    def test_retry_failed_analyses_ignores_pending_attachments(self, mock_delay):
        # Arrange
        failed_attachment = self._create_failed_attachment()

        # Create pending attachment
        pdf_file = SimpleUploadedFile("pending.pdf", b'content', content_type="application/pdf")
        EventAttachment.objects.create(
            event=self.event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='pending.pdf',
            analysis_status=EventAttachment.AnalysisStatus.PENDING
        )

        # Act
        retry_failed_analyses()

        # Assert
        # Should only retry the failed one, not pending
        mock_delay.assert_called_once_with(failed_attachment.id)

    @patch('ai_assistant.tasks.analyze_attachment.delay')
    def test_retry_failed_analyses_ignores_processing_attachments(self, mock_delay):
        # Arrange
        failed_attachment = self._create_failed_attachment()

        # Create processing attachment
        pdf_file = SimpleUploadedFile("processing.pdf", b'content', content_type="application/pdf")
        EventAttachment.objects.create(
            event=self.event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='processing.pdf',
            analysis_status=EventAttachment.AnalysisStatus.PROCESSING
        )

        # Act
        retry_failed_analyses()

        # Assert
        # Should only retry the failed one, not processing
        mock_delay.assert_called_once_with(failed_attachment.id)


class TestAnalyzeAttachmentEdgeCases(TestCase):
    """Additional edge case tests for attachment analysis."""

    def setUp(self):
        """Set up minimal test data."""
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
        # Arrange
        pdf_file = SimpleUploadedFile("corrupt.pdf", b'corrupt', content_type="application/pdf")
        attachment = EventAttachment.objects.create(
            event=self.event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='corrupt.pdf'
        )

        mock_pdf_reader.side_effect = Exception("PDF is corrupted")

        # Act & Assert
        with self.assertRaises(Exception) as context:
            _analyze_pdf(attachment)

        self.assertIn("PDF is corrupted", str(context.exception))

    @patch('builtins.open')
    def test_analyze_image_with_file_read_error_raises(self, mock_open_file):
        # Arrange
        image_file = SimpleUploadedFile("image.png", b'image', content_type="image/png")
        attachment = EventAttachment.objects.create(
            event=self.event,
            file=image_file,
            file_type=EventAttachment.FileType.IMAGE,
            original_filename='image.png'
        )

        mock_open_file.side_effect = IOError("Cannot read file")

        # Act & Assert
        with self.assertRaises(IOError) as context:
            _analyze_image(attachment)

        self.assertIn("Cannot read file", str(context.exception))

    @patch('ai_assistant.tasks.generate_text')
    @patch('ai_assistant.tasks.PdfReader')
    def test_analyze_pdf_with_multiple_empty_pages_returns_no_text(self, mock_pdf_reader, mock_generate_text):
        # Arrange
        pdf_file = SimpleUploadedFile("empty.pdf", b'empty', content_type="application/pdf")
        attachment = EventAttachment.objects.create(
            event=self.event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='empty.pdf'
        )

        # Create multiple pages with no text
        mock_pages = [Mock() for _ in range(5)]
        for page in mock_pages:
            page.extract_text.return_value = None

        mock_reader_instance = Mock()
        mock_reader_instance.pages = mock_pages
        mock_pdf_reader.return_value = mock_reader_instance

        # Act
        result = _analyze_pdf(attachment)

        # Assert
        self.assertEqual(result, "No se pudo extraer texto del PDF.")
        mock_generate_text.assert_not_called()

    @patch('ai_assistant.tasks.generate_text')
    @patch('ai_assistant.tasks.PdfReader')
    def test_analyze_pdf_with_mixed_empty_and_filled_pages_extracts_only_filled(self, mock_pdf_reader, mock_generate_text):
        # Arrange
        pdf_file = SimpleUploadedFile("mixed.pdf", b'mixed', content_type="application/pdf")
        attachment = EventAttachment.objects.create(
            event=self.event,
            file=pdf_file,
            file_type=EventAttachment.FileType.PDF,
            original_filename='mixed.pdf'
        )

        # Page 1: empty, Page 2: has text, Page 3: empty, Page 4: has text
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

        # Act
        result = _analyze_pdf(attachment)

        # Assert
        self.assertEqual(result, "Analysis complete")
        call_args = mock_generate_text.call_args
        prompt = call_args[0][0]
        self.assertIn("Invoice details", prompt)
        self.assertIn("Total cost", prompt)
