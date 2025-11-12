from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Project, Task, Tag

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['title', 'description']
    
class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['project', 'name']

    def __init__(self, *args, **kwargs):
        project = kwargs.pop('project', None)
        super(TagForm, self).__init__(*args, **kwargs)


class TaskForm(forms.ModelForm):
    new_tags = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'Add new tags (comma-separated)'}),
        required=False
    )

    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.none(),  # Start with an empty queryset
        widget=forms.CheckboxSelectMultiple,
        required=False
    )


    class Meta:
        model = Task
        fields = ['project', 'title', 'description', 'start_date', 'due_date', 'priority', 'status', 'parent_task', 'tags']

        widgets = {
            'priority': forms.Select(choices=Task.PRIORITY_CHOICES),
        }

    def __init__(self, *args, **kwargs):
        project = kwargs.pop('project', None)  # Extract project passed from view
        super(TaskForm, self).__init__(*args, **kwargs)

        # Only show the tags that are associated with the project
        if project:
            self.fields['tags'].queryset = project.tags.all()

        if project:
            # Filter to only include tasks from the same project and exclude the task being edited
            self.fields['parent_task'].queryset = Task.objects.filter(project=project).exclude(id=self.instance.id)
            self.fields['parent_task'].empty_label = f"Depends on project: {project.title}"           
            
        else:
            # If no project, don't show any tasks in parent_task dropdown
            self.fields['parent_task'].queryset = Task.objects.none()
            self.fields['tags'].widget = forms.Select(choices=[])
            
    def clean(self):
        cleaned_data = super().clean()
        parent_task = cleaned_data.get('parent_task')
        start_date = cleaned_data.get('start_date')
        due_date = cleaned_data.get('due_date')

        # 1. Self-Dependency Check (Already implemented, but good to include here)
        if parent_task and self.instance and parent_task.id == self.instance.id:
            self.add_error('parent_task', "A task cannot depend on itself.")
            
        # 2. Finish-to-Start (FS) Dependency Check
        if parent_task and start_date:
            # Check if the child task's start date is BEFORE the parent's due date.
            if start_date < parent_task.due_date:
                self.add_error(
                    'start_date',
                    f"The start date must be on or after the parent task's due date ({parent_task.due_date})."
                )

        # 3. Basic Start/Due Integrity (Optional, but recommended)
        if start_date and due_date and start_date > due_date:
            self.add_error('due_date', "Due date cannot be before the start date.")
            
        return cleaned_data
    
    def save(self, commit=True):
        # Save the task without committing any many-to-many relationships yet
        task = super().save(commit=False)  # Get the Task instance but don't save

        # Save the task first to make sure it gets a valid primary key (ID)
        task.save()  # This ensures task has an ID, crucial for many-to-many relationships

        # Now handle the tags (Many-to-Many field)
        tags = self.cleaned_data.get('tags')
        if tags:
            task.tags.set(tags)  # Set the tags (many-to-many) after saving the task
        
        # Handle new tags input
        new_tags = self.cleaned_data.get('new_tags')
        if new_tags:
            new_tags_list = [tag.strip() for tag in new_tags.split(',')]
            for tag_name in new_tags_list:
                tag, created = Tag.objects.get_or_create(name=tag_name, project=task.project)
                task.tags.add(tag)  # Add the new tag to the task's tags

        if commit:
            task.save()  # Commit changes after handling the tags

        return task

    
    


