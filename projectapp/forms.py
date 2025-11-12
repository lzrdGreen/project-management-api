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
        fields = ['project', 'title', 'description', 'start_date', 'due_date', 'priority', 'status', 'prerequisite_tasks', 'tags']

        widgets = {
            'priority': forms.Select(choices=Task.PRIORITY_CHOICES),
        }

    def __init__(self, *args, **kwargs):
        project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)

        # Filter available tags and prerequisite tasks to the same project
        if project:
            self.fields['tags'].queryset = project.tags.all()
            self.fields['prerequisite_tasks'].queryset = (
                Task.objects.filter(project=project)
                .exclude(id=self.instance.id)
                .order_by('due_date')
            )
        else:
            self.fields['tags'].queryset = Tag.objects.none()
            self.fields['prerequisite_tasks'].queryset = Task.objects.none()

        self.fields['prerequisite_tasks'].help_text = (
            "Select one or more tasks that must finish before this task starts. "
            "If none selected, it depends on the project itself."
        )
            
    def clean(self):
        cleaned_data = super().clean()
        prerequisites = cleaned_data.get('prerequisite_tasks', [])
        start_date = cleaned_data.get('start_date')
        due_date = cleaned_data.get('due_date')

        # Self-dependency check
        if self.instance and self.instance.pk and self.instance in prerequisites:
            self.add_error('prerequisite_tasks', "A task cannot depend on itself.")
            return cleaned_data

        # Finish-to-Start (FS) dependency check for multiple parents
        if prerequisites and start_date:
            # Find the latest due date among all selected prerequisites
            latest_prereq_due_date = max(
                [p.due_date for p in prerequisites if p.due_date] or [start_date]
            )
            
            if start_date < latest_prereq_due_date:
                self.add_error(
                    'start_date',
                    f"Start date must be on or after the latest prerequisite due date ({latest_prereq_due_date})."
                )

        # Basic start < due validation
        if start_date and due_date and start_date > due_date:
            self.add_error('due_date', "Due date cannot be before the start date.")

        return cleaned_data
    
    def save(self, commit=True):
        # Let Django handle instance creation and initial save
        task = super().save(commit=commit)

        # Only handle ManyToMany after commit (when PK exists)
        if commit:
            # --- prerequisite tasks ---
            prerequisites = self.cleaned_data.get('prerequisite_tasks')
            if prerequisites is not None:
                task.prerequisite_tasks.set(prerequisites)

            # --- tags ---
            tags = self.cleaned_data.get('tags')
            if tags is not None:
                task.tags.set(tags)

            # --- new tags ---
            new_tags = self.cleaned_data.get('new_tags', '')
            if new_tags:
                new_tags_list = [t.strip() for t in new_tags.split(',') if t.strip()]
                for tag_name in new_tags_list:
                    tag, _ = Tag.objects.get_or_create(name=tag_name, project=task.project)
                    task.tags.add(tag)

        return task


