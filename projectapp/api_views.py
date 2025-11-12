from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Project, Task, Tag
from .serializers import ProjectSerializer, TaskSerializer, TagSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.prefetch_related('tasks', 'tags').all()
    serializer_class = ProjectSerializer
    permission_classes = [permissions.DjangoModelPermissions]

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def board(self, request, pk=None):
        """Return project tasks grouped by status (like your project_board template)."""
        project = self.get_object()
        data = {
            'todo': TaskSerializer(project.tasks.filter(status='todo'), many=True).data,
            'in_progress': TaskSerializer(project.tasks.filter(status='in_progress'), many=True).data,
            'done': TaskSerializer(project.tasks.filter(status='done'), many=True).data,
        }
        return Response(data)


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.select_related('project', 'parent_task').prefetch_related('tags').all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.DjangoModelPermissions]

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def move(self, request):
        """Custom endpoint for task_move (Kanban drag-drop updates)."""
        task_id = request.data.get('task_id')
        new_status = request.data.get('status')
        task = get_object_or_404(Task, id=task_id)

        if new_status not in dict(Task.STATUS_CHOICES):
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)

        task.status = new_status
        task.save()
        task.project.calculate_progress()
        return Response({'success': True})


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.select_related('project').all()
    serializer_class = TagSerializer
    permission_classes = [permissions.DjangoModelPermissions]
