from rest_framework import serializers
from datetime import date
from .models import Project, Task, Tag
# Serializers for the models, used to convert data
# to and from JSON for API requests and responses.

class TagSerializer(serializers.ModelSerializer):
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
            'id', 'title', 'description', 'start_date', 'due_date', 'priority', 'status', 'created_at', 'project', 'project_title', 
            'prerequisite_tasks', 'prerequisite_task_ids', 'prerequisite_titles',
            'tags', 'tag_ids', 'new_tags'
        ]
        
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
            raise serializers.ValidationError("Due date cannot be in the past.")
        return value

    def validate(self, data):
        prerequisites = data.get('prerequisite_tasks', [])
        start_date = data.get('start_date')
        due_date = data.get('due_date')

        # Use instance fallback for partial updates
        if self.instance:
            prerequisites = prerequisites or self.instance.prerequisite_tasks.all()
            start_date = start_date if start_date is not None else self.instance.start_date
            due_date = due_date if due_date is not None else self.instance.due_date

        # Self-dependency check
        if self.instance and self.instance.pk and self.instance in prerequisites:
            raise serializers.ValidationError({
                'prerequisite_tasks': "A task cannot depend on itself."
            })

        # Start < due
        if start_date and due_date and start_date > due_date:
            raise serializers.ValidationError({
                'due_date': "Due date cannot be before the start date."
            })

        # Finish-to-Start rule across all prerequisites
        if prerequisites and start_date:
            latest_prereq_due_date = max(
                [parent.due_date for parent in prerequisites if parent.due_date] or [start_date]
            )

            if start_date < latest_prereq_due_date:
                raise serializers.ValidationError({
                    'start_date': f"Start date must be on or after the latest prerequisite due date ({latest_prereq_due_date})."
                })

        return data

    def create(self, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        prerequisite_tasks = validated_data.pop('prerequisite_tasks', [])
        new_tags_str = self.context['request'].data.get('new_tags', '').strip()

        task = Task.objects.create(**validated_data)

        # Handle M2M fields
        if tag_ids:
            task.tags.set(tag_ids)
        if prerequisite_tasks:
            task.prerequisite_tasks.set(prerequisite_tasks)

        # Handle new tags
        if new_tags_str:
            new_tags = [t.strip() for t in new_tags_str.split(',') if t.strip()]
            for tag_name in new_tags:
                tag, _ = Tag.objects.get_or_create(name=tag_name, project=task.project)
                task.tags.add(tag)

        task.project.calculate_progress()
        return task

    def update(self, instance, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        prerequisite_tasks = validated_data.pop('prerequisite_tasks', [])
        new_tags_str = self.context['request'].data.get('new_tags', '').strip()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Handle M2M relationships
        if tag_ids:
            instance.tags.set(tag_ids)
        if prerequisite_tasks:
            instance.prerequisite_tasks.set(prerequisite_tasks)

        # Handle new tags
        if new_tags_str:
            new_tags = [t.strip() for t in new_tags_str.split(',') if t.strip()]
            for tag_name in new_tags:
                tag, _ = Tag.objects.get_or_create(name=tag_name, project=instance.project)
                instance.tags.add(tag)

        instance.project.calculate_progress()
        return instance


class ProjectSerializer(serializers.ModelSerializer):
    tasks = TaskSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    progress = serializers.FloatField(read_only=True)

    class Meta:
        model = Project
        fields = ['id', 'title', 'description', 'created_at', 'progress', 'tasks', 'tags']
