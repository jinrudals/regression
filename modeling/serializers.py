from rest_framework.serializers import ModelSerializer
from rest_framework.utils import model_meta
from django.db import transaction

from . import models


class Project(ModelSerializer):
    class Meta:
        model = models.Project
        fields = '__all__'


class Group(ModelSerializer):
    class Meta:
        model = models.Group
        fields = '__all__'


class Testcase(ModelSerializer):
    class Meta:
        model = models.Testcase
        fields = '__all__'


class Trial(ModelSerializer):
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
