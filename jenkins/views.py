import logging
from django.http import HttpRequest
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from modeling.models import Project, Testcase, Trial, Version, Workspace
from modeling import models
from modeling import serializers as ser

# Create your views here.
logger = logging.getLogger(__name__)


class CreateTrial(APIView):
    '''Create Trial with build number and process'''

    def post(self, request: HttpRequest):
        logger.info("Create Trials")
        message = request.data
        project: int | str = message.get('project')
        build_number: int = message.get('BUILD_NUMBER')
        version: int | str = message.get('version')
        directory: str = message.get('path')

        logger.debug(f"Create Trials with {message}")

        try:
            if isinstance(project, str):
                project = Project.objects.get(name=project)
            elif isinstance(project, int):
                project = Project.objects.get(pk=project)
            else:
                logger.error(f"Wrong project specifier: {project}")
                return Response(
                    {"error":
                        "Invalid project specifier. Either name or pk should be given"},
                    status=status.HTTP_400_BAD_REQUEST)
        except Project.DoesNotExist:
            logger.error(f"Cannot find project with given {project}")
            return Response({"error": f"Cannot find project with given {project}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if isinstance(version, str):
                version = Version.objects.get(
                    project=project,
                    name=version
                )
            elif isinstance(version, int):
                version = Version.objects.get(
                    project=project,
                    pk=version
                )
            else:
                logger.error(f"Wrong version specifier: {version}")
                return Response(
                    {"error": "Invalid version specifier. Either name or pk should be given"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Version.DoesNotExist:
            logger.error(f"Cannot get version with given {version}")
            return Response({
                "error": f"Cannot get version with given {version}"
            }, status=status.HTTP_400_BAD_REQUEST)

        testcases = Testcase.objects.filter(
            project=project,
            status__in=['candidate', 'candidate2'],
            recent=None
        )
        trials = [
            Trial(
                testcase=tc,
                version=version,
                directory=directory,
                BUILD_NUMBER=build_number,
            )
            for tc in testcases
        ]
        Trial.objects.bulk_create(trials)
        serializer = ser.Trial(trials, many=True)
        logger.debug(f"Created Trials : {serializer.data}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PostWorkspace(APIView):
    def post(self, requset: HttpRequest):
        message: dict = requset.data
        path = message.get('path')

        logger.debug(f"{path} has been received")
        workspace, _ = Workspace.objects.get_or_create(defaults={
            "path": path
        })

        logger.info(f"Workspace({workspace.pk}) has been created")
        stub = message.get('stub')
        project = message.get('project')

        stub, _ = models.Stub.objects.get_or_create(
            project=models.Project.objects.get(pk=project),
            name=stub,
            defaults={
                "workspace": workspace
            }
        )

        logger.info(
            f"Stub({stub.pk}) has been updated to use Workspace({workspace.pk})")

        build_number = message.get('BUILD_NUMBER')

        trials = Trial.objects.filter(
            BUILD_NUMBER=build_number,
            testcase__project=models.Project.objects.get(pk=project),
            testcase__command__startswith=stub.name
        )

        logger.debug(f"{len(trials)} Trials are found")
        trials.update(workspace=workspace)
        logger.debug(f"{len(trials)} Trials are now using {workspace.pk}")

        serializer = ser.Trial(trials, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class FinishStub(APIView):
    def patch(self, requset: HttpRequest):
        message: dict = requset.data

        stub = message.get("stub")
        build_number = message.get("BUILD_NUMBER")

        trials = Trial.objects.filter(
            testcase__command__contains=stub,
            BUILD_NUMBER=build_number,
            status='compiling'
        )
        for each in trials:
            each.status = 'pending'
            each.save()
        trials.update(status='pending')
        message["trials"] = str(trials)
        return Response(message)
    pass
