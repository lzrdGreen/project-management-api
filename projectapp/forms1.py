from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Max, Q
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
            #'project',  
            'title', 
            'description', 
            'start_date', 
            'due_date', 
            'priority', 
            'status', 
            'milestone', 
            'prerequisite_tasks',
        ] 
        labels = {
            'title': 'Task Title', 
            'status': 'Completion Status', # Renamed from 'is_completed'
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
                
        # Filter available fields based on the project context
        if self.project:
            # Filter available tags to the same project
            self.fields['tags'].queryset = self.project.tags.all()
            
            # Filter available milestones to the same project
            self.fields['milestone'].queryset = Milestone.objects.filter(project=self.project)
            
            # Filter prerequisite tasks to the same project (excluding the current task itself)
            self.fields['prerequisite_tasks'].queryset = (
                Task.objects.filter(project=self.project)
                .exclude(id=self.instance.id)
                .order_by('due_date')
            )
        else:
            # If project is not set, set querysets to empty to prevent any selection
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
        instance = self.instance # This is None during creation!
        
        def has_cycle(start_task, target_task_id, visited=None):
            """
            Checks if a path exists from start_task to target_task_id in the existing graph.
            The start_task is a proposed prerequisite. The target_task is the current task.
            """
            if visited is None:
                visited = set()
            
            if start_task.pk == target_task_id:
                # We found the current task in the dependency chain of one of its parents. CYCLE!
                return True
            
            if start_task.pk in visited:
                return False # Already checked this path
            
            visited.add(start_task.pk)
            
            # We trace backward: check all parents of the start_task
            for parent in start_task.prerequisite_tasks.all():
                if has_cycle(parent, target_task_id, visited):
                    return True
            
            return False
        
        if instance and instance.pk: 
            target_id = instance.pk 
    
            for proposed_prerequisite in prerequisites:
                # We only check prerequisites that are saved objects (i.e., have a PK)
                if proposed_prerequisite.pk and has_cycle(proposed_prerequisite, target_id):
                    self.add_error(
                        "prerequisite_tasks", 
                        f"Dependency cycle detected. Task cannot depend on {proposed_prerequisite.title}."
                    )

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
        
            
        if milestone and milestone.project != project_instance:
            self.add_error("milestone", "Selected milestone does not belong to this project.")
            
        
        #if project_instance and 'project' not in cleaned_data:
             #cleaned_data['project'] = project_instance
        
        return cleaned_data
    
    def save(self, commit=True):
        # Let Django handle instance creation and initial save
        task = super().save(commit=False)
        if self.project and not task.project_id:
            task.project = self.project

        # Only handle ManyToMany after commit (when PK exists)
        if commit:
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
        fields = ['project', 'name', 'description', 'milestone_type', 'due_date']          

    def __init__(self, *args, **kwargs):
        # 1. Safely pop the 'project' argument. Use .pop('project', None)
        #    instead of just .pop('project') to prevent KeyError if the view changes.
        project = kwargs.pop('project', None)
        self.project = project
        
        # 2. Call super().__init__ to build the form fields based on the model.
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

        # 3. Hide the 'project' field since the view handles its value.
        if 'project' in self.fields:
            self.fields['project'].widget = forms.HiddenInput()
            if self.project:
                self.fields['project'].initial = self.project.pk
                 
        if self.project and not self.instance.pk:
            latest_task_date = self.project.tasks.filter(milestone__isnull=True).aggregate(Max('due_date'))['due_date__max']
            
            # Only set initial date if the calculation returned a value
            if latest_task_date and not self.initial.get('due_date'):
                # This pre-fills the form field, allowing the PM to change it.
                self.fields['due_date'].initial = latest_task_date        

        # 4. Only attempt to filter querysets if the project instance exists.
        if self.project: 
            # Get all tasks for this project
            tasks_qs = self.project.tasks.all() 
            
            # --- Queryset Filtering Logic ---
            
            # If we are editing an existing milestone
            if self.instance and self.instance.pk:
                # Tasks currently assigned to THIS milestone (reverse relationship)
                current_tasks = self.instance.tasks.all() 
                
                # Queryset includes tasks with no milestone OR tasks already assigned to this one
                qs = tasks_qs.filter(
                    Q(milestone__isnull=True) | Q(milestone=self.instance)
                ).distinct()
                self.fields["tasks"].queryset = qs
                
                # Set the initial tasks for the form when editing
                self.fields['tasks'].initial = current_tasks.values_list('id', flat=True)
            else:
                # For creation: only show tasks not yet assigned to any milestone
                self.fields['tasks'].queryset = tasks_qs.filter(milestone__isnull=True).distinct()
                
            # --- End Queryset Filtering Logic ---
            
        else:
            # Fallback: If no project is provided, set the task queryset to empty to prevent errors.
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

