# Generated by Django 5.0.6 on 2024-05-24 07:04

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('modeling', '0002_workspace_stub_trial_workspace_stub_unique__stub'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stub',
            name='workspace',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stubs', to='modeling.workspace'),
        ),
    ]