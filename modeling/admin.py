from django.contrib import admin
from . import models


class SnapshotAdmin(admin.ModelAdmin):
    pass


# Register your models here.
admin.site.register(models.Project)
admin.site.register(models.Group)
admin.site.register(models.Testcase)
admin.site.register(models.Trial)
admin.site.register(models.Snapshot, SnapshotAdmin)
