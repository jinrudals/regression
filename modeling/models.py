from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from typing import Iterable
from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone

# Create your models here.


class Project(models.Model):
    '''
    Project Model
    name : string
    url  : string (SSH format)
    '''
    name = models.CharField(max_length=255)
    url = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('url',), name='unique__url')
        ]


class Group(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='+')
    name = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('project', 'name'), name='unique__group__name__per_project')
        ]


class Testcase(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='testcases'
    )

    owner = models.ForeignKey(
        get_user_model(), on_delete=models.SET_NULL, null=True
    )

    timeout = models.IntegerField(default=-1, null=False, blank=False)
    command = models.TextField(null=False, blank=False)
    key = models.CharField(null=False, blank=False, max_length=255)

    group = models.ForeignKey(
        Group, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('project', 'key'), name='unique__testcase__key__per__project')
        ]

    _STATUS = [
        ('passed', 'passed'),
        ('failed', 'failed'),
        ('todo', 'todo'),
        ('candidate', 'candidate'),
        ('candidate2', 'candidate2')
    ]
    status = models.CharField(
        max_length=len('candidate2'),
        choices=_STATUS,
        default='candidate'
    )

    recent = models.ForeignKey(
        'Trial', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    def save(self, force_insert: bool = False, force_update: bool = False, using: str | None = None, update_fields: Iterable[str] | None = None) -> None:
        if self.pk:  # if it existed
            obj = Testcase.objects.get(pk=self.pk)
            if self.command != obj.command or self.timeout != obj.timeout:
                self.status = 'candidate'
            if self.status in ['candidate', 'candidate2'] and obj.status in ['passed', 'failed']:
                # if the previous status in passed / failed and current status is candidate
                # clean the latest trial
                self.recent = None
        return super().save(force_insert, force_update, using, update_fields)


@receiver(post_save, sender=Testcase)
def signal_handler(sender, instance: Testcase, created, **kwargs):
    with transaction.atomic():
        try:
            snapshot = Snapshot.objects.filter(
                project=instance.project,
            ).order_by('-id').first()
        except:
            snapshot = Snapshot.objects.create(project=instance.project)
        # Mapping of status to Snapshot relation
        status_map = {
            'passed': snapshot.passed,
            'failed': snapshot.failed,
            'todo': snapshot.todo,
            'candidate': snapshot.unverified,
            'candidate2': snapshot.unverified
        }

        if created:
            status_map[instance.status].add(instance)
        else:
            # Update status changes by removing from all other and adding to new one if not exists
            current_relation = status_map[instance.status]
            for status, relation in status_map.items():
                if relation != current_relation and relation.filter(pk=instance.pk).exists():
                    relation.remove(instance)
            if not current_relation.filter(pk=instance.pk).exists():
                current_relation.add(instance)


class Trial(models.Model):
    testcase = models.ForeignKey(
        Testcase, on_delete=models.CASCADE, related_name='trials')
    directory = models.TextField(null=False, blank=False)
    _STATUS = (
        ('compiling', 'compiling'),
        ('pending', 'pending'),
        ('running', 'running'),
        ('failed', 'failed'),
        ('passed', 'passed')
    )
    status = models.CharField(
        max_length=len('compiling'),
        choices=_STATUS,
        default='compiling'
    )
    backup = models.TextField(null=True, blank=True)

    BUILD_NUMBER = models.IntegerField(null=True, blank=True)

    def save(self, force_insert: bool = False, force_update: bool = False, using: str | None = None, update_fields: Iterable[str] | None = None) -> None:
        if not self.pk:
            super().save(force_insert, force_update, using, update_fields)
            self.testcase.recent = self
            self.testcase.save()
        if self.status in ['failed', 'passed']:
            self.testcase.status = self.status
            self.testcase.save()
        return super().save(force_insert, force_update, using, update_fields)


class Snapshot(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='snapshots')
    date = models.DateField(auto_now_add=True)
    passed = models.ManyToManyField(
        'Testcase', blank=True, related_name='passed_snapshots')
    failed = models.ManyToManyField(
        'Testcase', blank=True, related_name='failed_snapshots')
    todo = models.ManyToManyField(
        'Testcase', blank=True, related_name='todo_snapshots')
    unverified = models.ManyToManyField(
        'Testcase', blank=True, related_name='unverified_snapshots')

    def __str__(self) -> str:
        return f"Snashot({self.project}, {self.date})"

    @property
    def total(self):
        # Create individual querysets for each test case status
        passed_qs = self.passed.all()
        failed_qs = self.failed.all()
        todo_qs = self.todo.all()
        unverified_qs = self.unverified.all()

        # Combine all querysets into a single queryset using `union`
        # The `distinct=True` parameter ensures that duplicates are removed
        total_qs = passed_qs.union(failed_qs, todo_qs, unverified_qs, all=True)
        return total_qs

    def save(self, *args, **kwargs):
        # Wrap the saving and M2M operations in a transaction
        with transaction.atomic():
            created = not self.pk
            super().save(*args, **kwargs)  # Ensure instance is saved and pk is set

            if created:
                self.setup_testcase_relations()

    def setup_testcase_relations(self):
        testcases = self.project.testcases.all()
        self.passed.set(testcases.filter(status='passed'))
        self.failed.set(testcases.filter(status='failed'))
        self.unverified.set(testcases.filter(
            status__in=['candidate', 'candidate2']))
        self.todo.set(testcases.filter(status='todo'))
