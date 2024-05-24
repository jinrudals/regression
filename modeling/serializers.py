from rest_framework.serializers import ModelSerializer, CharField, EmailField, IntegerField
from rest_framework.utils import model_meta
from django.db import transaction

from . import models


class Project(ModelSerializer):
    class Meta:
        model = models.Project
        fields = '__all__'


class Version(ModelSerializer):
    class Meta:
        model = models.Version
        fields = "__all__"


class Group(ModelSerializer):
    class Meta:
        model = models.Group
        fields = '__all__'


class Testcase(ModelSerializer):
    class Meta:
        model = models.Testcase
        fields = '__all__'


class Trial(ModelSerializer):
    command = CharField(source="testcase.command", read_only=True)
    recent = IntegerField(source="testcase.recent.pk", read_only=True)
    owner = EmailField(source="testcase.owner.email", read_only=True)

    project = IntegerField(source='testcase.project.pk', read_only=True)

    class Meta:
        model = models.Trial
        fields = '__all__'


class Snapshot(ModelSerializer):
    class Meta:
        model = models.Snapshot
        fields = '__all__'

    def create(self, validated_data):
        info = model_meta.get_field_info(self.Meta.model)
        for field_name, relation_info in info.relations.items():
            if relation_info.to_many and (field_name in validated_data):
                validated_data.pop(field_name)

        return super().create(validated_data)
