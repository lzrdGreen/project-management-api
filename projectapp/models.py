from django.db import models, transaction
from datetime import date
from django.core.exceptions import ValidationError
from django.db.models import Max, Count

# Create your models here.

class Project(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    #progress = models.FloatField(default=0.0) # Percentage completion (used in views)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title

    def _calculate_progress_value(self):
        """Calculates the project progress value without saving."""
        total_tasks = self.tasks.count()
        if total_tasks == 0:
            return 0.0

        milestones = self.milestones.all()

        if milestones.exists():
            if not self.tasks.exclude(status='done').exists():
                return 100.0  
            completed_milestones = sum(1 for m in milestones if m.is_complete)
            milestone_completion_ratio = completed_milestones / milestones.count()
           
            total_stray_tasks = self.tasks.filter(milestone__isnull=True).count()
            done_stray_tasks = self.tasks.filter(milestone__isnull=True, status='done').count()
            if total_stray_tasks == 0:
                progress = milestone_completion_ratio * 100.0          
            else:
                stray_task_ratio = (done_stray_tasks / total_stray_tasks) if total_stray_tasks > 0 else 0.0            
                progress = (milestone_completion_ratio * 90.0) + (stray_task_ratio * 10.0)
            return round(min(progress, 100.0), 2)

        else:            
            done = self.tasks.filter(status='done').count()
            return round((done / total_tasks * 100), 2)
        
    @property
    def progress(self):
        """Public access to the always up-to-date progress value."""
        return self._calculate_progress_value()

class Tag(models.Model):
    name = models.CharField(max_length=127)
    project = models.ForeignKey(Project, related_name='tags', on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ('name', 'project')
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} on {self.project.title}"


class Task(models.Model):
    STATUS_CHOICES = [
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    ]
    
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    PRIORITY_CHOICES = [
        (LOW, 'Low'),
        (MEDIUM, 'Medium'),
        (HIGH, 'High'),
    ]   

    project = models.ForeignKey(Project, related_name='tasks', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField()
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=MEDIUM)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='todo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # --- WBS Hierarchy Link ---
    milestone = models.ForeignKey(
        'Milestone',
        on_delete=models.SET_NULL, # Tasks are retained (become project-level) if the Milestone is deleted.
        related_name='tasks',      # Allows retrieval of tasks via milestone.tasks.all()
        null=True,                 # Allows tasks to be created without being assigned to a milestone.
        blank=True                 # Allows the field to be optional in forms/admin.
    )
    prerequisite_tasks = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='dependents',
    )
    tags = models.ManyToManyField(Tag, related_name='tasks', blank=True)
    
    class Meta:
        ordering = ["due_date", "-priority"]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_due_date = self.due_date
        self._original_milestone_id = self.milestone_id
    
    def __str__(self):
        prereqs = self.prerequisite_tasks.all()

        if prereqs.exists():
            latest_due = prereqs.aggregate(max_due=Max('due_date')).get('max_due')

            if latest_due:
                latest_str = latest_due.strftime('%Y-%m-%d')
            else:
                latest_str = "No date"  # Should never happen

            return (
                f"{self.title} (Due: {self.due_date}, "
                f"Prereqs: {prereqs.count()}, Latest Due Date: {latest_str})"
            )

        return f"{self.title} (Due: {self.due_date}, No Prerequisites)"

      
    def is_overdue(self):
        return self.due_date < date.today() and self.status != 'done'
    
    def has_cycle(self, parent, target_id, visited=None):
        if visited is None:
            visited = set()

        if parent.pk == target_id:
            return True

        if parent.pk in visited:
            return False

        visited.add(parent.pk)

        for grandparent in parent.prerequisite_tasks.all():
            if self.has_cycle(grandparent, target_id, visited):
                return True

        return False
    
    def clean(self):
        super().clean()
        
        if not self.project_id:
            return
        
        if self.milestone and self.milestone.project_id != self.project_id:
            raise ValidationError("The milestone must belong to the same project as the task.")

        # Circular dependency logic
        if self.pk:            
            for parent in self.prerequisite_tasks.all():
                if parent.pk == self.pk:
                    raise ValidationError(
                        {"prerequisite_tasks": "A task cannot be its own prerequisite."}
                    )
                if parent.pk and self.has_cycle(parent, self.pk):
                    raise ValidationError(
                        {"prerequisite_tasks": f"Circular dependency: cannot depend on '{parent.title}'."}
                    )
    
    def save(self, *args, **kwargs):
        from .models import Milestone  # local import avoids circular issues

        old_milestone_id = self._original_milestone_id
        old_due = self._original_due_date

        milestone_changed = (self.milestone_id != old_milestone_id)
        date_changed = (self.due_date != old_due)

        with transaction.atomic():
            # long-running queries, sending emails, or anything external!
            super().save(*args, **kwargs)

            # 1. New milestone receives recalculation
            if self.milestone_id and (milestone_changed or date_changed):
                self.milestone.recalculate_and_save_date()

            # 2. Old milestone needs recalculation if task was moved away
            if milestone_changed and old_milestone_id is not None:
                try:
                    old_ms = Milestone.objects.get(pk=old_milestone_id)
                    old_ms.recalculate_and_save_date()
                except Milestone.DoesNotExist:
                    pass

            # Update tracking values
            self._original_milestone_id = self.milestone_id
            self._original_due_date = self.due_date

class Milestone(models.Model):
    project = models.ForeignKey(
        'Project',
        related_name='milestones',
        on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    # the target deadline set by the project manager:
    due_date = models.DateField()
    
    # Tasks are linked to a Milestone via a ForeignKey on the Task model.
    # The related_name 'tasks' will be used to retrieve them (e.g., milestone.tasks.all()).

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    MILESTONE_TYPES = [
        # (Database Value, Human-readable Label)
        ('SIGN_OFF', 'Sponsor Sign-off'),
        ('GATE', 'Client Gate'),
        ('INTERNAL', 'Internal Team Checkpoint'),
    ]

    milestone_type = models.CharField(
        max_length=10,
        choices=MILESTONE_TYPES,
        blank=True,  # Allows a blank selection in forms
        null=True,   # Allows NULL in the database (for default=None)
        default=None,  # Sets the default value in the database to blank/empty string
        help_text="Designate if this is a formal client gate, Sponsor Sign-off or an internal checkpoint."
    )

    def __str__(self):
        return f"{self.name} ({self.project.title})"

    @property
    def is_complete(self):
        """A Milestone is complete only if ALL linked tasks are in the 'done' status."""
        # Access tasks using the related_name 'tasks' from the ForeignKey on the Task model.
        return not self.tasks.exclude(status='done').exists()
    
    def latest_due_date(self):
        """Returns the latest due date among all tasks linked to this milestone."""
        # Uses aggregation for efficiency
        latest_date = self.tasks.aggregate(max_date=models.Max('due_date'))['max_date']
        return latest_date or self.due_date
    
    def recalculate_and_save_date(self):
        """
        Recalculate the milestone due_date from linked tasks and save if different.
        Keeps behaviour simple: set milestone.due_date = max(task.due_date) if any tasks exist.
        """
        latest = self.tasks.aggregate(max_date=models.Max('due_date'))['max_date']
        # If there are no tasks, we keep the existing due_date (same as current behavior)
        if latest is None:
            return

        if latest != self.due_date:
            # update only the due_date field to avoid touching other fields/side-effects
            self.due_date = latest
            self.save(update_fields=['due_date'])
    