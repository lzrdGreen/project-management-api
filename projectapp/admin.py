from django.contrib import admin
from .models import Project, Task, Tag, Milestone
# Register your models here.

class TaskInline(admin.TabularInline):
    """Allows editing Tasks directly within the Milestone admin page."""
    model = Task
    
    # The Task model now has the 'milestone' ForeignKey, making it accessible here.
    # Note:'assignee' and 'owner' don't exist yet.
    fields = ['title', 'status', 'due_date'] 
    
    extra = 1 # Show one extra blank form to add a new task
    show_change_link = True


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'progress', 'created_at', 'updated_at')
    search_fields = ('title', 'description')

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'milestone', 'due_date', 'priority', 'status', 'updated_at')
    search_fields = ('title', 'description')
    list_filter = ('project', 'milestone', 'priority', 'status')
    # Add project and milestone fields to the detail view fields list:
    fields = ('project', 'milestone', 'title', 'description', 'start_date', 'due_date', 'priority', 'status', 'prerequisite_tasks', 'tags')
    
@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'project', 'due_date', 'milestone_type', 'is_complete']
    search_fields = ['name', 'description']
    list_filter = ['project', 'milestone_type', 'due_date']
    
    fieldsets = (
        (None, {
            'fields': ('project', 'name', 'description', 'due_date')
        }),
        ('WBS Configuration', {
            # Use 'milestone_type' field defined in your model
            'fields': ('milestone_type',), 
            'description': 'Configuration for how this milestone relates to project governance.'
        }),
    )
    
    inlines = [TaskInline]

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'project')
    search_fields = ('name',)
    list_filter = ('project',)
