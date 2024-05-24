from django.http import HttpResponse
from rest_framework.viewsets import ModelViewSet
from rest_framework.routers import DefaultRouter
from rest_framework.views import APIView

from . import models
from . import serializers
# Create your views here.

router = DefaultRouter()


class MetaClass(type):
    def __new__(cls, name, bases, attrs, **kwargs):
        instance = super().__new__(cls, name, bases, attrs)
        if name != 'Base' and name != 'MetaClass':
            instance.queryset = getattr(models, name).objects.all()
            instance.serializer_class = getattr(serializers, name)

            router.register(name.lower(), instance, basename=name.lower())
        return instance


class Base(ModelViewSet, metaclass=MetaClass):
    pass


class Project(Base):
    pass


class Group(Base):
    pass


class Testcase(Base):
    pass


class Trial(Base):
    partial = True
    pass


class Snapshot(Base):
    pass


class Version(Base):
    pass


class Temp(APIView):
    def get(self, request):
        project = models.Project.objects.first()
        models.Snapshot.objects.create(project=project)
        return HttpResponse("?")
