from django.conf import settings
import asyncio
from . import models
from regression.ws import Websocket
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from typing import Iterable
from django.db import models
from django.contrib.auth import get_user_model
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone

import json
import logging

# Create your models here.
logger = logging.getLogger(__name__)


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

    def __str__(self) -> str:
        return f"Project({self.name})"


class Group(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='+')
    name = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('project', 'name'), name='unique__group__name__per_project')
        ]


class Version(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='versions')
    name = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('project', 'name'), name='unique__version__name__per_project')
        ]

    def __str__(self) -> str:
        return self.name


@receiver(post_save, sender=Version)
def signal_handler_version(sender, instance: Version, created, **kwargs):
    if created:
        testcases = instance.project.testcases.all()
        passed = testcases.filter(status='passed')
        failed = testcases.filter(status='failed')
        unverified = testcases.filter(status__in=['candidate', 'candidate2'])

        with transaction.atomic():
            for each in passed:
                each.status = 'candidate2'
                each.save()
            for each in failed:
                each.status = 'candidate'
                each.save()
            for each in unverified:
                if each.recent:
                    each.recent.delete()
            Snapshot.objects.get_or_create(
                version=instance
            )


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
                logger.debug(
                    f"Command or Timeout has been changed for {self.pk}")
                self.status = 'candidate'
            if self.status in ['candidate', 'candidate2'] and obj.status in ['passed', 'failed']:
                logger.debug(f"Clean Recent Value for {self.pk}")
                self.recent = None
        return super().save(force_insert, force_update, using, update_fields)

    def __str__(self) -> str:
        return f"Testcase({self.key}, {self.project})"


@receiver(post_save, sender=Testcase)
def signal_handler(sender, instance: Testcase, created, **kwargs):
    with transaction.atomic():
        version = instance.project.versions.all().order_by('-id').first()
        snapshot, _ = Snapshot.objects.get_or_create(
            version=version,
            defaults={
                'date': timezone.now()
            }
        )

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
    version = models.ForeignKey(
        Version, on_delete=models.CASCADE
    )
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
    workspace = models.ForeignKey(
        'Workspace', on_delete=models.SET_NULL, blank=True, null=True, related_name='trials')

    def save(self, force_insert: bool = False, force_update: bool = False, using: str | None = None, update_fields: Iterable[str] | None = None) -> None:
        if not self.pk:
            instance = super().save(force_insert, force_update, using, update_fields)
            logger.debug(
                f"Set Trial({self.pk}) as recent of TestCase({self.testcase.pk})")
            self.testcase.recent = self
            self.testcase.save()
            return instance
        if self.status in ['failed', 'passed']:
            self.testcase.status = self.status
            self.testcase.save()
        return super().save(force_insert, force_update, using, update_fields)


@receiver(post_save, sender=Trial)
def signal_handler_trial(sender, instance: Trial, created, **kwargs):
    if instance.status in ['passed', 'failed']:
        workspace = instance.workspace
        if not workspace:
            return
        # Flag 1
        trials = workspace.trials.all().filter(
            status__in=['pending', 'compiling', 'running'])

        if not workspace.stubs:
            pass
        # Flag 2
        # Stub.objects.filter(workspace=workspace)
        if not trials.exist() and not workspace.stubs:
            # Delete Workspace
            pass
    pass


@receiver(post_save, sender=Trial)
def handle_trial_on_pending(sender, instance: Trial, created, **kwargs):
    if instance.status == "pending":
        logger.debug(f"Trial({instance.pk}) has been pended")
        loop = settings.LOOP
        loop.create_task(
            send_message(json.dumps(
                {
                    "action": "add",
                    "owner": instance.testcase.owner.email,
                    "project": instance.testcase.project.pk,
                    "command": instance.testcase.command,
                    "build": instance.BUILD_NUMBER,
                    "pk": instance.pk
                }
            ))
        )


# @receiver(post_save, sender=Trial)
# def handle_trial_on_running(sender, instance: Trial, created, **kwargs):
#     if instance.status == "running":
#         loop = settings.LOOP
#         loop.create_task(send_message_to_jenkins(instance))
#         pass


# async def send_message_to_jenkins(instance: Trial):
#     from .serializers import Trial as ser
#     channel = get_channel_layer()
#     project = instance.testcase.project.pk
#     build = instance.BUILD_NUMBER

#     serializer = await sync_to_async(ser)(instance)

#     logger.debug(f"Serialized data is {serializer}")
#     await channel.group_send(
#         f'{project}_{build}',
#         {
#             'type': f'messaging',
#             "message": json.dumps(serializer.data)
#         }
#     )


async def send_message(message):
    logger.debug("Send Message to task Manager")
    if Websocket.instance == None:
        await Websocket.create()
    await Websocket().connection.send(str(message))
    logger.info(f"Message is sent to TM: {message}")


@receiver(post_save, sender=Trial)
def handle_trial_on_passed_failed(sender, instance: Trial, created, **kwargs):
    if instance.status in ['passed', 'failed']:
        loop = settings.LOOP
        loop.create_task(
            send_message(json.dumps({
                "action": "complete",
                "project": instance.testcase.project.pk,
                "command": instance.testcase.command,
                "build": instance.BUILD_NUMBER
            })))


class Stub(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='stubs')
    name = models.CharField(max_length=255)
    workspace = models.ForeignKey(
        'Workspace', null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('project', 'name'), name='unique__stub')
        ]


class Workspace(models.Model):
    '''
    Compile Workspace
    '''
    path = models.TextField(null=False, blank=False, unique=True)

    def try_delete_workspace(self):
        trials = self.trials.all().filter(
            status__in=['compiling', 'pending', 'running'])
        stubs = self.stubs

        if not trials.exist and not stubs:
            self.delete()


class Snapshot(models.Model):
    version = models.ForeignKey(
        Version, on_delete=models.CASCADE, related_name='snapshots')
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
        return f"Snashot({self.version.project},{self.version},{self.date})"

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
        testcases = self.version.project.testcases.all()
        self.passed.set(testcases.filter(status='passed'))
        self.failed.set(testcases.filter(status='failed'))
        self.unverified.set(testcases.filter(
            status__in=['candidate', 'candidate2']))
        self.todo.set(testcases.filter(status='todo'))

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('version', 'date'), name='unique__snapshot__per_date')
        ]
