from django.urls import path
from . import views
urlpatterns = [
    path('create/trials/', views.CreateTrial.as_view()),
    path('create/workspace/', views.PostWorkspace.as_view()),
    path('stub/finish/', views.FinishStub.as_view()),
]
