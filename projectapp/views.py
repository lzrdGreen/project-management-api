import json
from django.db.models.functions import Lower
from django.http import JsonResponse
from django.db.models import Q
from datetime import date
from .models import Project, Task, Tag
from .forms import ProjectForm, TaskForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib import messages


# Home page
def main(request):
    return render(request, 'projectapp/main.html')

# View to create a new project
def project_create(request):
    if not request.user.is_authenticated:          
        return redirect('home_page')
    
    # Permissions logic
    can_add_project = request.user.has_perm('projectapp.add_project')
    can_change_project = request.user.has_perm('projectapp.change_project')
    can_delete_project = request.user.has_perm('projectapp.delete_project')   
    
    if request.method == 'POST':
        if not can_add_project:
            messages.error(request, "Sorry, but a permission is required to create a project")
            return redirect('home_page')        
        
        form = ProjectForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('project_list')
    else:
        form = ProjectForm()
    return render(request, 'projectapp/project_form.html', {
        'form': form,
        'can_add_project': can_add_project,
        'can_change_project': can_change_project
    })

# Edit project
def project_edit(request, id):
    if not request.user.is_authenticated:          
        return redirect('home_page')
    project = get_object_or_404(Project, id=id)

    # Permission check for editing the project
    if not request.user.has_perm('projectapp.change_project'):
        messages.error(request, "You don't have permission to edit this project.")
        return redirect('project_list')
    # Permissions logic
    can_add_project = request.user.has_perm('projectapp.add_project')
    can_change_project = request.user.has_perm('projectapp.change_project')
    can_delete_project = request.user.has_perm('projectapp.delete_project')
    
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            return redirect('project_list')
    else:
        form = ProjectForm(instance=project)
    return render(request, 'projectapp/project_form.html', {
        'form': form,
        'can_add_project': can_add_project,
        'can_change_project': can_change_project
    })

# View to add a new task a task
def task_create(request, project_id):
    if not request.user.is_authenticated:          
        return redirect('home_page')
    
    project = get_object_or_404(Project, id=project_id)
    
    # Permissions logic
    can_add_task = request.user.has_perm('projectapp.add_task')
    can_add_task = request.user.has_perm('projectapp.add_task')
    can_change_task = request.user.has_perm('projectapp.change_task')
    can_delete_task = request.user.has_perm('projectapp.delete_task')
    can_change_project = request.user.has_perm('projectapp.change_project')
    can_delete_project = request.user.has_perm('projectapp.delete_project')
    can_add_project = request.user.has_perm('projectapp.add_project')
    
    if request.method == 'POST':
        if not can_add_task:
            messages.error(request, "Sorry, but a permission is required to create a task.")
            return redirect('home_page')
                
        form = TaskForm(request.POST, project=project)  # Pass project to the form
        if form.is_valid():
            task = form.save(commit=False)  # Don't save to the DB yet
            

            # Validate due date
            if task.due_date < date.today():
                form.add_error('due_date', 'Due date cannot be in the past.')
            else:
                task.project = project  # Explicitly link the task to the current project
                # Process new tags (comma-separated input)
                new_tags = request.POST.get('new_tags', '')
                if new_tags:
                    tags_list = [tag.strip() for tag in new_tags.split(',')]  # Clean up tags
                    task.tag = ','.join(tags_list)  # Save as a comma-separated string
                # If no parent task is provided, default to the project
                if not task.parent_task:
                    task.parent_task = None  # Or handle project as logical parent in some other way if needed
                
                task.save()  # Now save the task with the project linked
                                
                return redirect('project_detail', project.id)
    else:
        form = TaskForm(initial={'project': project}, project=project)  # Pass project to form

    return render(request, 'projectapp/task_form.html', {
        'form': form, 
        'project': project, 
        'can_add_task': can_add_task, 
        'can_change_task': can_change_task
        })

# Edit task
def task_edit(request, task_id):
    if not request.user.is_authenticated:          
        return redirect('home_page')
    
    task = get_object_or_404(Task, id=task_id)
    project = task.project  # Get the project the task belongs to
    
    # Permission check for editing the task
    if not request.user.has_perm('projectapp.change_task'):
        messages.error(request, "You don't have permission to edit this task.")
        return redirect('home_page')
    # Permissions logic
    can_add_task = request.user.has_perm('projectapp.add_task')
    can_change_task = request.user.has_perm('projectapp.change_task')
    can_delete_task = request.user.has_perm('projectapp.delete_task')
    can_change_project = request.user.has_perm('projectapp.change_project')
    can_delete_project = request.user.has_perm('projectapp.delete_project')
    can_add_project = request.user.has_perm('projectapp.add_project')
    
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task, project=project)  # Pass project to form
        if form.is_valid():
            task = form.save(commit=False)
            
            # Update the tags if necessary
            new_tags = request.POST.get('new_tags', '')
            if new_tags:
                tags_list = [tag.strip() for tag in new_tags.split(',')]  # Clean up tags
                task.tag = ','.join(tags_list)  # Save as a comma-separated string
            
            task.save()
            return redirect('project_detail', id=project.id)
    else:
        form = TaskForm(instance=task, project=project)  # Pass project to form

    return render(request, 'projectapp/task_form.html', {
        'form': form, 
        'project': project,
        'task': task, ################## 
        'can_add_task': can_add_task, 
        'can_change_task': can_change_task
        })

# Delete task
def task_delete(request, id):
    if not request.user.is_authenticated:          
        return redirect('home_page')
    task = get_object_or_404(Task, pk=id)

    # Permission check for deleting the task
    if not request.user.has_perm('projectapp.delete_task'):
        messages.error(request, "You don't have permission to delete this task.")
        return redirect('home_page')

    if request.method == 'POST':
        task.delete()
        return redirect('project_detail', id=task.project.id)  

    return render(request, 'projectapp/task_confirm_delete.html', {'task': task})

# Delete project
def project_delete(request, id):
    if not request.user.is_authenticated:          
        return redirect('home_page')
    project = get_object_or_404(Project, pk=id)

    # Permission check for deleting the project
    if not request.user.has_perm('projectapp.delete_project'):
        messages.error(request, "You don't have permission to delete this project.")
        return redirect('home_page')

    if request.method == 'POST':
        project.delete()
        return redirect('project_list')

    return render(request, 'projectapp/project_confirm_delete.html', {'project': project})




# View to list all projects
def project_list(request):
    if not request.user.is_authenticated:
        return redirect('home_page')

    sort_by = request.GET.get('sort', 'title')  # Default sorting by title

    # Base query for projects and tasks
    project_results = Project.objects.prefetch_related('tasks').all()

    # Apply sorting if applicable
    if sort_by == 'priority':
        project_results = project_results.order_by('tasks__priority')
    elif sort_by == 'due_date':
        project_results = project_results.order_by('tasks__due_date')
    else:
        project_results = project_results.order_by('title')  # Default sorting by title

    # Calculate progress for each project
    for project in project_results:
        project.progress = project.calculate_progress()
        
    
    # Permissions logic
    can_add_task = request.user.has_perm('projectapp.add_task')
    can_change_task = request.user.has_perm('projectapp.change_task')
    can_delete_task = request.user.has_perm('projectapp.delete_task')
    can_change_project = request.user.has_perm('projectapp.change_project')
    can_delete_project = request.user.has_perm('projectapp.delete_project')
    can_add_project = request.user.has_perm('projectapp.add_project')

    context = {
        'project_results': project_results.distinct(),
        'sort_by': sort_by,        
        'can_add_task': can_add_task,
        'can_change_task': can_change_task,
        'can_delete_task': can_delete_task,
        'can_change_project': can_change_project,
        'can_delete_project': can_delete_project,
        'can_add_project': can_add_project,
    }

    return render(request, 'projectapp/project_list_new.html', context)

def search(request):       
    if not request.user.is_authenticated:
        return redirect('home_page')

    query = request.GET.get('search')
    sort_by = request.GET.get('sort', 'title')

    # Base query for projects and tasks
    project_results = Project.objects.all()
    task_results = Task.objects.all()

    # Apply search filtering if a query is provided
    if query:
        project_filter = Q(title__icontains=query) | Q(description__icontains=query)
        task_filter = Q(title__icontains=query) | Q(description__icontains=query)

        project_results = project_results.filter(project_filter).distinct()
        task_results = task_results.filter(task_filter).distinct()

    # Apply sorting after filtering, without resetting the queryset
    if sort_by == 'priority':
        project_results = project_results.order_by('tasks__priority')
        task_results = task_results.order_by('priority')
    elif sort_by == 'due_date':
        project_results = project_results.order_by('tasks__due_date')
        task_results = task_results.order_by('due_date')

    # Permissions logic
    can_add_task = request.user.has_perm('projectapp.add_task')
    can_change_task = request.user.has_perm('projectapp.change_task')
    can_delete_task = request.user.has_perm('projectapp.delete_task')
    can_change_project = request.user.has_perm('projectapp.change_project')
    can_delete_project = request.user.has_perm('projectapp.delete_project')

    context = {
        'project_results': project_results.distinct(),  # Changed to project_results
        'task_results': task_results.distinct(),        # Added task_results
        'sort_by': sort_by,
        'query': query,  # Carry the query value to the template
        'can_add_task': can_add_task,
        'can_change_task': can_change_task,
        'can_delete_task': can_delete_task,
        'can_change_project': can_change_project,
        'can_delete_project': can_delete_project,
    }
    return render(request, 'projectapp/search_results.html', context)


# View to Board
def project_board(request, id):
    if not request.user.is_authenticated:          
        return redirect('home_page')
    project = get_object_or_404(Project, id=id)
    tasks = {
        'todo': project.tasks.filter(status='todo'),
        'in_progress': project.tasks.filter(status='in_progress'),
        'done': project.tasks.filter(status='done')
    }    

    can_edit = request.user.has_perm('projectapp.change_task')

    return render(request, 'projectapp/project_board.html', {'project': project, 'tasks': tasks, 'can_edit': can_edit})

# View the details of the project
def project_detail(request, id):
    if not request.user.is_authenticated:          
        return redirect('home_page')
    project = get_object_or_404(Project, id=id)

    # Check permissions
    can_add_task = request.user.has_perm('projectapp.add_task')
    can_change_task = request.user.has_perm('projectapp.change_task')
    can_delete_task = request.user.has_perm('projectapp.delete_task')
    can_change_project = request.user.has_perm('projectapp.change_project')
    can_delete_project = request.user.has_perm('projectapp.delete_project')

    sort_by = request.GET.get('sort', 'title') 
    if sort_by == 'priority':
        tasks = project.tasks.all().order_by('-priority')
    elif sort_by == 'due_date':
        tasks = project.tasks.all().order_by('due_date')
    elif sort_by == 'title':
        # tasks = project.tasks.all().order_by(('title').lower())
        tasks = project.tasks.all().annotate(lower_title=Lower('title')).order_by('lower_title')
    else:
        tasks = project.tasks.all()
    
    # Check for overdue tasks
    for task in tasks:
        task.overdue = task.is_overdue()
    
    project_progress = project.calculate_progress()    
    
    return render(request, 'projectapp/project_detail.html', {
        'project': project,
        'tasks': tasks,        
        'project_progress': project_progress,
        'can_add_task': can_add_task,
        'can_change_task': can_change_task,
        'can_delete_task': can_delete_task,
        'can_change_project': can_change_project,
        'can_delete_project': can_delete_project,        
    })


# Handling Task Movement
def task_move(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        task_id = data.get('task_id')
        new_status = data.get('status')

        task = get_object_or_404(Task, id=task_id)
        if new_status in ['todo', 'in_progress', 'done']:
            task.status = new_status
            task.save()
            return JsonResponse({'success': True})

    return JsonResponse({'success': False}, status=400)


    #return render(request, 'projectapp/project_detail.html', {'project': project, 'tasks': tasks, 'sort_by': sort_by})

# Task detail view
def task_detail(request, id):
    if not request.user.is_authenticated:          
        return redirect('home_page')
    task = get_object_or_404(Task, id=id)
    task.overdue = task.is_overdue()  # Check if the task is overdue
    # Check permissions for the current user
    project = task.project
    can_edit_task = request.user.has_perm('projectapp.change_task')
    can_delete_task = request.user.has_perm('projectapp.delete_task')
    return render(request, 'projectapp/task_detail.html', {
        'task': task,
        'project': project,
        'can_edit_task': can_edit_task,
        'can_delete_task': can_delete_task
    })

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Automatically log in the user after registration
            messages.success(request, 'Registration successful!')
            return redirect('home_page')  # Redirect to a home page or dashboard
    else:
        form = UserCreationForm()
    return render(request, 'projectapp/register.html', {'form': form})

def hint(request):
    return render(request, 'projectapp/hint.html', {})

def tasks_by_tag(request, id, tag_id):
    project = get_object_or_404(Project, id=id)
    
    # Filter tasks by the selected tag
    tasks = project.tasks.filter(tags__id=tag_id).distinct()

    # Check for overdue tasks
    for task in tasks:
        task.overdue = task.is_overdue()

    return render(request, 'projectapp/tasks_by_tag.html', {
        'project': project,
        'tasks': tasks,
        'tag': get_object_or_404(Tag, id=tag_id),
    })

