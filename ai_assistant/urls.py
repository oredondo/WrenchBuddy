from django.urls import path

from ai_assistant.views import recommendation_view

urlpatterns = [
    path('recommendations/<int:vehicle_id>/', recommendation_view, name='ai-recommendations'),
]
