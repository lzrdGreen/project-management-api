from rest_framework import serializers
from datetime import date
from .models import Project, Task, Milestone, Tag
from django.db.models import Count, Max
from rest_framework.exceptions import ValidationError

# Serializers for the models, used to convert data
# to and from JSON for API requests and responses.

class TagSerializer(serializers.ModelSerializer):
    project = serializers.SlugRelatedField(
        slug_field='title',  # Use the 'title' attribute of the Project model
        queryset=Project.objects.all()
    )
    class Meta:
        model = Tag
        fields = ['id', 'name', 'project']


class TaskSerializer(serializers.ModelSerializer):
    # --- Tag fields ---
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True,
        write_only=True,
        required=False
    )
    new_tags = serializers.CharField(write_only=True, required=False)
    
    # --- Project info ---
    project_title = serializers.ReadOnlyField(source='project.title')
    
    milestone = serializers.PrimaryKeyRelatedField(
        queryset=Milestone.objects.all(),
        allow_null=True,
        required=False,        
    )
    
    # --- Prerequisite tasks ---
    prerequisite_tasks = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(),
        many=True,
        required=False,
        write_only=True
    )
    prerequisite_task_ids = serializers.SerializerMethodField()
    prerequisite_titles = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'start_date', 'due_date', 'priority', 'status', 'created_at', 'project', 'project_title', 'milestone',
            'prerequisite_tasks', 'prerequisite_task_ids', 'prerequisite_titles',
            'tags', 'tag_ids', 'new_tags'
        ]
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        request = self.context.get("request")
        
        # Only proceed if we have request context and the field exists
        if not request or "prerequisite_tasks" not in self.fields:
            return

        project = None
        if self.instance:
            # Case 1: Updating existing Task
            project = self.instance.project
        elif request.data.get("project"):
            # Case 2: Creating new Task (project is in request data)
            try:
                project = Project.objects.get(id=request.data["project"])
            except Project.DoesNotExist:
                # Let general validation catch invalid project ID later
                pass
        
        if project:
            # Filter prerequisite tasks to same-project only
            self.fields["prerequisite_tasks"].queryset = Task.objects.filter(project=project)
        else:
            # Prevent selection if project is undetermined
            self.fields["prerequisite_tasks"].queryset = Task.objects.none()
        
    # -----------------------------
    # Helper method for read-only representations
    # -----------------------------
    def get_prerequisite_titles(self, obj):
        """Returns a list of titles for all prerequisite tasks."""
        return [task.title for task in obj.prerequisite_tasks.all()]

    def get_prerequisite_task_ids(self, obj):
        """Returns a list of IDs for all prerequisite tasks."""
        return [task.id for task in obj.prerequisite_tasks.all()]

    
    # Validation 
    def validate_due_date(self, value):
        if value and value < date.today():
            raise ValidationError("Due date cannot be in the past.")
        return value

    def validate(self, data):
        prerequisites = data.get('prerequisite_tasks', [])
        start_date = data.get('start_date')
        due_date = data.get('due_date')
        project = data.get("project") or self.instance.project
        milestone = data.get("milestone") if "milestone" in data else (
            self.instance.milestone if self.instance else None
        )
        instance = self.instance
        
        if milestone and milestone.project != project:
            raise ValidationError({
                "milestone": "Milestone must belong to the same project as the task."
            })

        # Use instance fallback for partial updates
        if self.instance:
            prerequisites = prerequisites or self.instance.prerequisite_tasks.all()
            start_date = start_date if start_date is not None else self.instance.start_date
            due_date = due_date if due_date is not None else self.instance.due_date

        for prereq in prerequisites:
            if prereq.project != project:
                raise ValidationError({
                    "prerequisite_tasks": "All prerequisite tasks must belong to the same project."
                })
        
        # Self-dependency check
        if self.instance and self.instance.pk and self.instance in prerequisites:
            raise ValidationError({
                'prerequisite_tasks': "A task cannot depend on itself."
            })
            
        # The check only runs when UPDATING an existing task (where a cycle is possible)
        if instance: 
            target_id = instance.pk
            
            for proposed_prerequisite in prerequisites:
                # We check only prerequisites that are saved objects (i.e., have a PK)
                if proposed_prerequisite.pk and instance.has_cycle(proposed_prerequisite, target_id):
                    raise ValidationError({
                        "prerequisite_tasks": f"Dependency cycle detected. Task cannot depend on {proposed_prerequisite.title}."
                    })
        
        # Start < due
        if start_date and due_date and start_date > due_date:
            raise ValidationError({
                'due_date': "Due date cannot be before the start date."
            })

        # Finish-to-Start rule across all prerequisites
        if prerequisites and start_date:
            latest_prereq_due_date = max(
                [parent.due_date for parent in prerequisites if parent.due_date] or [start_date]
            )

            if start_date < latest_prereq_due_date:
                raise ValidationError({
                    'start_date': f"Start date must be on or after the latest prerequisite due date ({latest_prereq_due_date})."
                })

        return data

    def create(self, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        prerequisite_tasks = validated_data.pop('prerequisite_tasks', [])
        new_tags_str = validated_data.pop('new_tags', '').strip()

        task = Task(**validated_data)
        
        # just in case:
        task._old_milestone_id = None
        task._original_milestone_id = None

        # AUTHORITATIVE VALIDATION
        task.full_clean()  # <-- this enforces Task.clean()

        task.save()

        # M2M handling (safe because instance.pk exists)
        if tag_ids:
            task.tags.set(tag_ids)
        if prerequisite_tasks:
            task.prerequisite_tasks.set(prerequisite_tasks)

        if new_tags_str:
            new_tags = [t.strip() for t in new_tags_str.split(',') if t.strip()]
            for tag_name in new_tags:
                tag, _ = Tag.objects.get_or_create(name=tag_name, project=task.project)
                task.tags.add(tag)

        return task

    def update(self, instance, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        prerequisite_tasks = validated_data.pop('prerequisite_tasks', [])
        new_tags_str = validated_data.pop('new_tags', '').strip()
        
        # This preserves the "old" milestone id for validation and for save() logic.
        try:
            # Use a fast DB hit to get the current milestone_id (or None)
            old_milestone_id = Task.objects.filter(pk=instance.pk).values_list('milestone_id', flat=True).first()
        except Exception:
            old_milestone_id = getattr(instance, 'milestone_id', None)

        # Attach both tracking attributes used by your model/save/signals.
        # Only set them if they are not already present (safeguard).
        if not hasattr(instance, '_old_milestone_id'):
            instance._old_milestone_id = old_milestone_id
        # _original_milestone_id is used inside Task.save() implementation
        if not hasattr(instance, '_original_milestone_id'):
            instance._original_milestone_id = old_milestone_id

        # Assign fields (now safe: we have the old milestone stored)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Assign fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # AUTHORITATIVE VALIDATION
        instance.full_clean()  # <-- this enforces Task.clean()

        instance.save()

        # M2M handling
        if tag_ids:
            instance.tags.set(tag_ids)
        if prerequisite_tasks:
            instance.prerequisite_tasks.set(prerequisite_tasks)

        if new_tags_str:
            new_tags = [t.strip() for t in new_tags_str.split(',') if t.strip()]
            for tag_name in new_tags:
                tag, _ = Tag.objects.get_or_create(name=tag_name, project=instance.project)
                instance.tags.add(tag)

        return instance


class MilestoneSerializer(serializers.ModelSerializer):
    # Read-only field derived from the @property in the Milestone model
    is_complete = serializers.ReadOnlyField() 
    
    # Read-only titles for ease of display (e.g., in a dropdown on the client)
    project_title = serializers.ReadOnlyField(source='project.title')

    class Meta:
        model = Milestone
        fields = [
            'id', 'project', 'project_title', 'name', 'description', 
            'due_date', 'milestone_type', 'is_complete', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'project']

    # --- Validation ---
    
    def validate_due_date(self, value):
        """Validates that the due date is not in the past."""
        from django.utils import timezone
        if value and value < timezone.now().date():
            raise serializers.ValidationError("Milestone due date cannot be in the past.")
        return value

    def validate(self, data):
        """Performs validation that requires access to multiple fields."""
        
        # 1. Project Context Check (Crucial for WBS integrity)
        # Ensure that when updating, the project FK cannot be changed (if necessary)
        if self.instance and 'project' in data and data['project'] != self.instance.project:
            raise serializers.ValidationError({"project": "Cannot change the project of an existing milestone."})        
        
        return data

class ProjectSerializer(serializers.ModelSerializer):
    tasks = TaskSerializer(many=True, read_only=True)
    milestones = MilestoneSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    progress = serializers.FloatField(read_only=True)

    class Meta:
        model = Project
        fields = ['id', 'title', 'description', 'created_at', 'progress', 'tasks', 'tags', 'milestones']

class ProjectListSerializer(serializers.ModelSerializer):
    task_count = serializers.IntegerField(read_only=True)
    milestone_count = serializers.IntegerField(read_only=True)
    latest_due_date = serializers.DateField(read_only=True)
    progress = serializers.FloatField(read_only=True)

    class Meta:
        model = Project
        fields = [
            'id',
            'title',
            'description',
            'created_at',
            'progress',
            'task_count',
            'milestone_count',
            'latest_due_date',
        ]