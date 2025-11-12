from django.db import models
from datetime import date

# Create your models here.

class Project(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    progress = models.FloatField(default=0)
    

    def __str__(self):
        return self.title
       
    def calculate_progress(self):
        total_tasks = self.tasks.count()
        if total_tasks == 0:
            return 0
        done_tasks = self.tasks.filter(status='done').count()
        in_progress_tasks = self.tasks.filter(status='in_progress').count()

        progress = (done_tasks + 0.2 * in_progress_tasks) / total_tasks
        self.progress = round(progress * 100, 2)
        self.save()  # Save to the database
        return self.progress  # %

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
    