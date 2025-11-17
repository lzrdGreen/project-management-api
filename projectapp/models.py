from django.db import models
from datetime import date
from django.core.exceptions import ValidationError

# Create your models here.

class Project(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    progress = models.FloatField(default=0.0) # Percentage completion (used in views)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title

    def calculate_progress(self):
        total_tasks = self.tasks.count()
        if total_tasks == 0:
            self.progress = 0
            self.save()
            return 0

        milestones = self.milestones.all()

        if milestones.exists():
            milestone_completion_ratio = (
                sum(1 for m in milestones if m.is_complete) / milestones.count()
            )

            # If all tasks done → full completion
            if not self.tasks.exclude(status='done').exists():
                self.progress = 100.0
            else:
                # Otherwise milestone progress dominates
                self.progress = round(milestone_completion_ratio * 90.0, 2)

        else:
            # fallback to pure task logic
            done = self.tasks.filter(status='done').count()
            self.progress = round(
                (done  / total_tasks * 100), 2
            )

        self.save()
        return self.progress

class Tag(models.Model):
    name = models.CharField(max_length=127)
    project = models.ForeignKey(Project, related_name='tags', on_delete=models.CASCADE)
    
    def __str__(self):
        return self.name


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
    
    def __str__(self):
        prereqs = self.prerequisite_tasks.all()
        prereq_count = prereqs.count()
        
        if prereq_count > 0:
            # Find the latest due date among all prerequisites
            latest_prereq_due = max(prereq.due_date for prereq in prereqs)
            parent_info = f"Prereqs: {prereq_count}, Latest Due Date: {latest_prereq_due}"
        else:
            parent_info = "No Prerequisites"
            
        return f'{self.title} (Due: {self.due_date}, {parent_info})'
      
    def is_overdue(self):
        return self.due_date < date.today() and self.status != 'done'
    def clean(self):
        super().clean()
        
        if not self.project_id:
            return
        
        if self.milestone and self.milestone.project_id != self.project_id:
            raise ValidationError("The milestone must belong to the same project as the task.")


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
        default='',  # Sets the default value in the database to blank/empty string
        help_text="Designate if this is a formal client gate, Sponsor Sign-off or an internal checkpoint."
    )

    def __str__(self):
        return f"{self.name} ({self.project.title})"

    @property
    def is_complete(self):
        """A Milestone is complete only if ALL linked tasks are in the 'done' status."""
        # Access tasks using the related_name 'tasks' from the ForeignKey on the Task model.
        return not self.tasks.filter(~models.Q(status='done')).exists()
    
    def latest_due_date(self):
        """Returns the latest due date among all tasks linked to this milestone."""
        # Uses aggregation for efficiency
        latest_date = self.tasks.aggregate(max_date=models.Max('due_date'))['max_date']
        return latest_date or self.due_date
    
    