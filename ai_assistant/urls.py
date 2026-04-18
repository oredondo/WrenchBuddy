from django.urls import path

from .views import AIChatView

urlpatterns = [
    path('chat/<int:vehicle_id>/', AIChatView.as_view(), name='ai-chat'),
]
