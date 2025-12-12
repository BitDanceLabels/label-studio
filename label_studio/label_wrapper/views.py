"""API endpoints that wrap Label Studio REST calls for external RAG systems."""
import logging
import os
from typing import Dict, List, Tuple

import requests
from django.conf import settings
from requests import RequestException
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


logger = logging.getLogger(__name__)

DEFAULT_LABEL_CONFIG = (
    "<View>"
    "<Text name=\"text\" value=\"$text\"/>"
    "<Textarea name=\"label\" toName=\"text\" label=\"Label\"/>"
    "</View>"
)


class ProjectCreateSerializer(serializers.Serializer):
    name = serializers.CharField(help_text='Project name')
    description = serializers.CharField(help_text='Project description', required=False, allow_blank=True, default='')
    label_config = serializers.CharField(help_text='Optional label config override', required=False, allow_blank=True)


class TaskSampleSerializer(serializers.Serializer):
    data = serializers.DictField(help_text='Task payload for Label Studio')
    meta = serializers.DictField(help_text='Optional task metadata', required=False)
    predictions = serializers.ListField(
        child=serializers.DictField(),
        help_text='Optional predictions to attach',
        required=False,
        allow_empty=True,
    )


class TasksCreateSerializer(serializers.Serializer):
    project_id = serializers.IntegerField(help_text='Target project id')
    samples = serializers.ListField(
        child=TaskSampleSerializer(), allow_empty=False, help_text='List of tasks in Label Studio format'
    )
    dataset_id = serializers.CharField(help_text='Dataset identifier stored in task.meta', required=False, allow_blank=True)
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text='Tags applied to every task (stored in task.meta.tags when provided)',
    )


class LabelStudioWrapperMixin(APIView):
    permission_classes = [AllowAny]
    authentication_classes = ()
    timeout_seconds = 60

    def _get_base_and_headers(self) -> Tuple[str, Dict[str, str]]:
        base = os.getenv('LABEL_STUDIO_BASE') or os.getenv('LABEL_STUDIO_URL') or settings.HOSTNAME
        token = (
            os.getenv('LABEL_STUDIO_TOKEN')
            or os.getenv('LABEL_STUDIO_API_KEY')
            or os.getenv('LABEL_STUDIO_USER_TOKEN')
        )
        if not base or not token:
            raise ValueError('LABEL_STUDIO_BASE and LABEL_STUDIO_TOKEN environment variables are required')

        return base.rstrip('/'), {'Authorization': f'Token {token}'}

    def _handle_request_error(self, exc: Exception) -> Response:
        logger.exception('Label Studio wrapper request failed: %s', exc)
        return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


class LabelProjectsAPI(LabelStudioWrapperMixin):
    """
    Create or list Label Studio projects using environment-supplied credentials.
    """

    def post(self, request):
        serializer = ProjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            base_url, headers = self._get_base_and_headers()
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        payload = {
            'title': serializer.validated_data['name'],
            'description': serializer.validated_data.get('description', ''),
            'label_config': serializer.validated_data.get('label_config') or DEFAULT_LABEL_CONFIG,
        }

        try:
            resp = requests.post(
                f'{base_url}/api/projects', json=payload, headers=headers, timeout=self.timeout_seconds
            )
            resp.raise_for_status()
        except RequestException as exc:
            return self._handle_request_error(exc)

        data = resp.json()
        return Response({'project_id': data.get('id')}, status=status.HTTP_201_CREATED)

    def get(self, request):
        try:
            base_url, headers = self._get_base_and_headers()
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            resp = requests.get(f'{base_url}/api/projects', headers=headers, timeout=self.timeout_seconds)
            resp.raise_for_status()
        except RequestException as exc:
            return self._handle_request_error(exc)

        payload = resp.json()
        if isinstance(payload, list):
            results = payload
        elif isinstance(payload, dict):
            results = payload.get('results', [])
        else:
            results = []
        projects = [
            {'id': project.get('id'), 'name': project.get('title'), 'description': project.get('description', '')}
            for project in results
        ]
        return Response({'projects': projects})


class LabelTasksAPI(LabelStudioWrapperMixin):
    """
    Create or list tasks for a Label Studio project using environment-supplied credentials.
    """

    def post(self, request):
        serializer = TasksCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            base_url, headers = self._get_base_and_headers()
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        project_id = serializer.validated_data['project_id']
        dataset_id = serializer.validated_data.get('dataset_id')
        tags = serializer.validated_data.get('tags') or []

        tasks_payload: List[Dict] = []
        for sample in serializer.validated_data['samples']:
            task_payload = {'data': sample['data']}

            meta = dict(sample.get('meta') or {})
            if dataset_id and 'dataset_id' not in meta:
                meta['dataset_id'] = dataset_id
            if tags and 'tags' not in meta:
                meta['tags'] = tags

            if meta:
                task_payload['meta'] = meta

            # Pass through predictions when provided to pre-label tasks
            if predictions := sample.get('predictions'):
                task_payload['predictions'] = predictions

            tasks_payload.append(task_payload)

        try:
            resp = requests.post(
                f'{base_url}/api/projects/{project_id}/import',
                params={'return_task_ids': 'true'},
                json=tasks_payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            resp.raise_for_status()
        except RequestException as exc:
            return self._handle_request_error(exc)

        data = resp.json()
        imported_count = len(data.get('task_ids', [])) or data.get('task_count', len(tasks_payload))
        return Response({'imported': imported_count, 'project_id': project_id}, status=status.HTTP_201_CREATED)

    def get(self, request):
        project_id = request.query_params.get('project_id')
        if not project_id:
            return Response({'detail': 'project_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            base_url, headers = self._get_base_and_headers()
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            resp = requests.get(
                f'{base_url}/api/tasks', params={'project': project_id}, headers=headers, timeout=self.timeout_seconds
            )
            resp.raise_for_status()
        except RequestException as exc:
            return self._handle_request_error(exc)

        return Response(resp.json())
