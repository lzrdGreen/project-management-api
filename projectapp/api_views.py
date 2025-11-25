from rest_framework import viewsets, permissions, status
from django.db.models import Count, Max
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Project, Task, Tag, Milestone
from .serializers import ProjectSerializer, TaskSerializer, TagSerializer, MilestoneSerializer, ProjectListSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly,
        permissions.DjangoModelPermissions,
    ]

    def get_queryset(self):
        queryset = Project.objects.all()

        if self.action == "list":
            # Annotate counts and latest due date
            queryset = queryset.annotate(
                task_count=Count("tasks", distinct=True),
                milestone_count=Count("milestones", distinct=True),
                latest_due_date=Max("tasks__due_date"),
            )
        else:
            queryset = queryset.prefetch_related(
                "tasks",
                "tasks__tags",
                "milestones",
                "tags",
            )

        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return ProjectListSerializer
        return ProjectSerializer

class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.select_related('project', 'parent_task').prefetch_related('tags').all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly,permissions.DjangoModelPermissions]
    
class MilestoneViewSet(viewsets.ModelViewSet):
    queryset = Milestone.objects.select_related('project').prefetch_related('tasks').all()
    serializer_class = MilestoneSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly,permissions.DjangoModelPermissions]


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.select_related('project').all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly,permissions.DjangoModelPermissions]
