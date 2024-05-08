from django.urls import path, include
from . import views

# router = DefaultRouter()
# router.register(
#     'project', views.Project, basename='project'
# )
urlpatterns = [path('test', views.Temp.as_view())]

urlpatterns += views.router.urls
