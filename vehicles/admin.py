from django.contrib import admin

from .models import Vehicle, VehicleDocument, DocumentChunk


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ['brand', 'model', 'year', 'vehicle_type', 'current_km', 'user', 'created_at']
    list_filter = ['vehicle_type', 'usage_type', 'brand']
    search_fields = ['brand', 'model', 'user__email']
    ordering = ['-created_at']
    raw_id_fields = ['user']


class DocumentChunkInline(admin.TabularInline):
    model = DocumentChunk
    extra = 0
    readonly_fields = ['chunk_index', 'text', 'embedding_preview']
    fields = ['chunk_index', 'text', 'embedding_preview']
    can_delete = False

    def embedding_preview(self, obj):
        if obj.embedding is None:
            return '—'
        preview = list(obj.embedding[:4])
        return f"[{', '.join(f'{v:.4f}' for v in preview)}, … ({len(obj.embedding)} dims)]"
    embedding_preview.short_description = 'Embedding (preview)'


@admin.register(VehicleDocument)
class VehicleDocumentAdmin(admin.ModelAdmin):
    list_display = [
        'original_filename', 'description', 'vehicle', 'file_type',
        'extraction_status', 'chunk_count', 'uploaded_at',
    ]
    list_filter = ['file_type', 'extraction_status', 'vehicle__brand']
    search_fields = ['original_filename', 'description', 'vehicle__brand', 'vehicle__model']
    ordering = ['-uploaded_at']
    readonly_fields = ['original_filename', 'file_type', 'extraction_status', 'extraction_error', 'uploaded_at', 'extracted_text']
    raw_id_fields = ['vehicle']
    inlines = [DocumentChunkInline]

    def chunk_count(self, obj):
        return obj.chunks.count()
    chunk_count.short_description = 'Chunks'


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ['id', 'document', 'chunk_index', 'text_preview']
    list_filter = ['document__vehicle__brand']
    search_fields = ['text', 'document__original_filename']
    ordering = ['document', 'chunk_index']
    readonly_fields = ['document', 'chunk_index', 'text', 'embedding']
    raw_id_fields = []

    def text_preview(self, obj):
        return obj.text[:80] + '…' if len(obj.text) > 80 else obj.text
    text_preview.short_description = 'Texto'
