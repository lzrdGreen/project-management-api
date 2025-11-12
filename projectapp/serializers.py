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
    # ManyToManyField automatically handled by DRF, but let's expose it nicely
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True,
        write_only=True,
        required=False
    )
    new_tags = serializers.CharField(write_only=True, required=False)
    project_title = serializers.ReadOnlyField(source='project.title')
    parent_task_title = serializers.ReadOnlyField(source='parent_task.title')

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'start_date', 'due_date', 'priority', 'status',
            'created_at', 'project', 'project_title', 'parent_task', 'parent_task_title',
            'tags', 'tag_ids', 'new_tags'
        ]

    # Validation logic (equivalent to form clean methods in FBVs)
    def validate_due_date(self, value):
        if value and value < date.today():
            raise serializers.ValidationError("Due date cannot be in the past.")
        return value

    def validate(self, data):
        parent_task = data.get('parent_task')
        start_date = data.get('start_date')
        due_date = data.get('due_date')
        
        # If updating, use the instance's current value if a field is not provided (partial update)
        if self.instance:
            parent_task = parent_task if parent_task is not None else self.instance.parent_task
            start_date = start_date if start_date is not None else self.instance.start_date
            due_date = due_date if due_date is not None else self.instance.due_date

        # 1. Self-Dependency Check (Moved here from validate_parent_task)
        # Note: self.instance is the existing object, so this only runs on UPDATE
        if parent_task and self.instance and parent_task.id == self.instance.id:
            raise serializers.ValidationError({'parent_task': "A task cannot depend on itself."})

        # 2. Basic Start/Due Integrity
        if start_date and due_date and start_date > due_date:
            raise serializers.ValidationError({'due_date': "Due date cannot be before the start date."})
            
        # 3. Finish-to-Start (FS) Dependency Rule (CRITICAL)
        if parent_task and start_date:
            # Child's Start Date must be on or after Parent's Due Date
            if start_date < parent_task.due_date:
                raise serializers.ValidationError({
                    'start_date': f"Start date must be on or after the parent task's due date ({parent_task.due_date})."
                })

        return data

    def create(self, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        new_tags_str = self.context['request'].data.get('new_tags', '').strip()
        task = Task.objects.create(**validated_data)

        # Handle existing tags
        if tag_ids:
            task.tags.set(tag_ids)

        # Handle new tags (like in your form)
        if new_tags_str:
            new_tags = [t.strip() for t in new_tags_str.split(',') if t.strip()]
            for tag_name in new_tags:
                tag, _ = Tag.objects.get_or_create(name=tag_name, project=task.project)
                task.tags.add(tag)

        task.project.calculate_progress()
        return task

    def update(self, instance, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        new_tags_str = self.context['request'].data.get('new_tags', '').strip()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if tag_ids:
            instance.tags.set(tag_ids)

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
