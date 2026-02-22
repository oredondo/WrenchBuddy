from django.urls import path

from .views import WhatsDueView

urlpatterns = [
    path('whats-due/<int:vehicle_id>/', WhatsDueView.as_view(), name='whats-due'),
]
