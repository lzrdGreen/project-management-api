from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Max, Q
from django.db import transaction
from django.utils import timezone
from .models import Project, Task, Tag, Milestone

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['title', 'description']
    
class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name']

    def __init__(self, *args, **kwargs):
        project = kwargs.pop('project', None)
        super(TagForm, self).__init__(*args, **kwargs)
        self.project = project
        
        if self.project is None:
            raise ValueError("TagForm requires a 'project' instance.")
        
    def clean_name(self):
        """
        Validates tag name uniqueness within the project 
        to prevent IntegrityError (500 error) on duplicate submission.
        """
        name = self.cleaned_data['name']
        
        # Check for duplicates, excluding the current instance if we are editing
        qs = Tag.objects.filter(name__iexact=name, project=self.project)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
            
        if qs.exists():
            raise ValidationError(f"A tag named '{name}' already exists in this project.")
            
        return name
    
    def save(self, commit=True):            
        tag_instance = super().save(commit=False)            
        tag_instance.project = self.project            
        if commit:
            tag_instance.save()                
        return tag_instance


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
        fields = [
            'title', 
            'description', 
            'start_date', 
            'due_date', 
            'priority', 
            'status', 
            'milestone',
            'tags',
            'prerequisite_tasks',
        ] 
        labels = {
            'title': 'Task Title', 
            'status': 'Completion Status',
        }

        widgets = {
            'priority': forms.Select(choices=Task.PRIORITY_CHOICES),
            'start_date': forms.DateInput(attrs={'type': 'date'}), 
            'due_date': forms.DateInput(attrs={'type': 'date'}), 
        }

    def __init__(self, *args, **kwargs):
        project = kwargs.pop('project', None)
        self.project = project
        super().__init__(*args, **kwargs)
                
        if self.project:
            self.fields['tags'].queryset = self.project.tags.all()
            self.fields['milestone'].queryset = Milestone.objects.filter(project=self.project)
            self.fields['prerequisite_tasks'].queryset = (
                Task.objects.filter(project=self.project)
                .exclude(id=self.instance.id)
                .order_by('due_date')
            )
        else:
            self.fields['tags'].queryset = Tag.objects.none()
            self.fields['milestone'].queryset = Milestone.objects.none() 
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
        milestone = cleaned_data.get("milestone")
        project_instance = self.project
        instance = self.instance
        
        
        if instance and instance.pk and prerequisites: 
            target_id = instance.pk 
    
            for proposed_prerequisite in prerequisites:
                # We call the model's authoritative method.
                if proposed_prerequisite.pk and instance.has_cycle(proposed_prerequisite, target_id):
                    self.add_error(
                        "prerequisite_tasks", 
                        f"Dependency cycle detected. Task cannot depend on {proposed_prerequisite.title}."
                    )
        
        # Self-dependency check (Ensuring we don't return early)
        if instance and instance.pk and instance in prerequisites:
            self.add_error('prerequisite_tasks', "A task cannot depend on itself.")
            

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
        
            
        # Milestone Project Consistency
        if milestone and milestone.project != project_instance:
             self.add_error("milestone", "Selected milestone does not belong to this project.")
             
        return cleaned_data
    
    def save(self, commit=True):
        # Let Django handle instance creation and initial save
        task = super().save(commit=False)
        if self.project and not task.project_id:
            task.project = self.project

        # Only handle ManyToMany after commit (when PK exists)
        if commit:
            # Note: For creation, the M2M relations are applied after this save, 
            # meaning the model's clean() will only catch the cycle on the next save/update.
            task.save() 
            
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
    
class MilestoneForm(forms.ModelForm):
    tasks = forms.ModelMultipleChoiceField(
        queryset=Task.objects.none(), 
        required=False,
        label="Associate Tasks",
        help_text="Select all tasks that should be tracked under this milestone.",        
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2'})
    )    
      
    class Meta:
        model = Milestone
        # Fields the user needs to set:
        fields = ['name', 'description', 'milestone_type', 'due_date']          

    def __init__(self, *args, **kwargs):        
        project = kwargs.pop('project', None)
        self.project = project
        
        super().__init__(*args, **kwargs)
        
        self.fields['tasks'].widget = forms.SelectMultiple(
            attrs={
                'class': 'form-control select2',
                'id': 'id_tasks'
            }
        )
        
        self.fields['due_date'].widget = forms.DateInput(
            attrs={'type': 'date'}
        )
            
        if self.project and not self.instance.pk:
            latest_task_date = self.project.tasks.filter(milestone__isnull=True).aggregate(Max('due_date'))['due_date__max']
            
            if latest_task_date and not self.initial.get('due_date'):
                self.fields['due_date'].initial = latest_task_date     

        if self.project: 
            #tasks_qs = self.project.tasks.all()
            unassigned_tasks = self.project.tasks.filter(milestone__isnull=True)
            
            if self.instance and self.instance.pk:
                current_tasks = self.instance.tasks.all() 
                
                qs = (unassigned_tasks | current_tasks).distinct().order_by('due_date')

                self.fields["tasks"].queryset = qs
                self.fields["tasks"].initial = current_tasks.values_list('id', flat=True)
            else:
                self.fields['tasks'].queryset = unassigned_tasks.distinct().order_by('due_date')
                
        else:
            self.fields['tasks'].queryset = Task.objects.none()

    def clean(self):
        cleaned = super().clean()
        tasks = cleaned.get("tasks")
        due_date = cleaned.get("due_date")

        if tasks and tasks.exists():
            latest_task_date = tasks.aggregate(Max("due_date"))["due_date__max"]

            if due_date and due_date < latest_task_date:
                raise ValidationError(
                    f"The target date cannot be earlier than the latest task due date ({latest_task_date})."
                )

        return cleaned
    
    def save(self, commit=True):
        with transaction.atomic():
            milestone = super().save(commit=False)
            if not milestone.pk:
                milestone.project = self.project
            if commit:
                milestone.save()
                
                # Handle task assignment
                selected_tasks = self.cleaned_data.get("tasks")            
                
                if selected_tasks is not None:
                    # Convert to IDs (empty list if no tasks selected)
                    selected_task_ids = list(selected_tasks.values_list('id', flat=True))

                    # Remove milestone from tasks that are no longer selected
                    Task.objects.filter(milestone=milestone)\
                        .exclude(id__in=selected_task_ids)\
                        .update(milestone=None)

                    # Assign milestone to selected tasks
                    if selected_task_ids:
                        Task.objects.filter(id__in=selected_task_ids)\
                            .update(milestone=milestone)
                        
        return milestone

