from django.urls import path

from .views import WhatsDueView, WhatsDuePollView

urlpatterns = [
    path('whats-due/<int:vehicle_id>/', WhatsDueView.as_view(), name='whats-due'),
    path('whats-due/<int:vehicle_id>/poll/<str:task_id>/', WhatsDuePollView.as_view(), name='whats-due-poll'),
]
