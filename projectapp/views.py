import json
from datetime import date
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404
from django.contrib import messages
from django.urls import reverse_lazy
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, View
)
from .models import Project, Task, Tag, Milestone
from .forms import ProjectForm, TaskForm, MilestoneForm


# ---------- STATIC VIEWS ----------
def main(request):
    return render(request, 'projectapp/main.html')


def hint(request):
    return render(request, 'projectapp/hint.html', {})


def register(request):
    """Kept as FBV for now (simple user registration).
    Later can be moved to a FormView."""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('home_page')
    else:
        form = UserCreationForm()
    return render(request, 'projectapp/register.html', {'form': form})


# ---------- MIXINS FOR COMMON PERMISSION LOGIC ----------
class PermissionMixin(UserPassesTestMixin):
    """Reusable permission mixin for CRUD checks."""
    permission_required = None

    def test_func(self):
        return self.request.user.has_perm(self.permission_required)

    def handle_no_permission(self):
        messages.error(self.request, "You don’t have permission to perform this action.")
        return redirect('home_page')


# ---------- PROJECT VIEWS ----------
class ProjectListView(ListView):
    model = Project
    template_name = 'projectapp/project_list_new.html'
    context_object_name = 'project_results'

    def get_queryset(self):
        sort_by = self.request.GET.get('sort', 'title')
        qs = Project.objects.prefetch_related('tasks').all()

        if sort_by == 'priority':
            qs = qs.order_by('tasks__priority')
        elif sort_by == 'due_date':
            qs = qs.order_by('tasks__due_date')
        else:
            qs = qs.order_by('title')

        
        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        u = self.request.user
        context.update({
            'sort_by': self.request.GET.get('sort', 'title'),
            'can_add_task': u.has_perm('projectapp.add_task'),
            'can_change_task': u.has_perm('projectapp.change_task'),
            'can_delete_task': u.has_perm('projectapp.delete_task'),
            'can_change_project': u.has_perm('projectapp.change_project'),
            'can_delete_project': u.has_perm('projectapp.delete_project'),
            'can_add_project': u.has_perm('projectapp.add_project'),
        })
        return context


class ProjectCreateView(CreateView):
    model = Project
    form_class = ProjectForm
    template_name = 'projectapp/project_form.html'
    success_url = reverse_lazy('project_list')
    permission_required = 'projectapp.add_project'
    
    def dispatch(self, request, *args, **kwargs):
        if request.method == 'POST':
            # Check if the user is logged in AND has the required permission
            if not request.user.is_authenticated or \
               not request.user.has_perm(self.permission_required):                
                messages.error(request, "You must be logged in and have permission to create a project.")
                return redirect('project_list')
        
        # Allow GET requests (and authorized POST requests) to proceed
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        u = self.request.user
        context.update({
            'can_add_project': u.has_perm('projectapp.add_project'),
            'can_change_project': u.has_perm('projectapp.change_project'),
            'can_delete_project': u.has_perm('projectapp.delete_project'),
        })
        return context


class ProjectUpdateView(LoginRequiredMixin, PermissionMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = 'projectapp/project_form.html'
    permission_required = 'projectapp.change_project'

    def get_success_url(self):
        return reverse_lazy('project_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        u = self.request.user
        context.update({
            'can_add_project': u.has_perm('projectapp.add_project'),
            'can_change_project': u.has_perm('projectapp.change_project'),
            'can_delete_project': u.has_perm('projectapp.delete_project'),
        })
        return context

class ProjectDeleteView(LoginRequiredMixin, PermissionMixin, DeleteView):
    model = Project
    template_name = 'projectapp/project_confirm_delete.html'
    success_url = reverse_lazy('project_list')
    permission_required = 'projectapp.delete_project'


class ProjectDetailView(DetailView):
    model = Project
    template_name = 'projectapp/project_detail.html'
    context_object_name = 'project'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        sort_by = self.request.GET.get('sort', 'title')
        if sort_by == 'priority':
            tasks = project.tasks.all().select_related('milestone').order_by('-priority')
        elif sort_by == 'due_date':
            tasks = project.tasks.all().select_related('milestone').order_by('due_date')
        elif sort_by == 'title':
            tasks = project.tasks.all().annotate(lower_title=Lower('title')).select_related('milestone').order_by('lower_title')
        else:
            tasks = project.tasks.all().select_related('milestone')

        for task in tasks:
            task.overdue = task.is_overdue()

        u = self.request.user
        context.update({
            'tasks': tasks,
            'project_progress': project.progress,
            'can_add_task': u.has_perm('projectapp.add_task'),
            'can_change_task': u.has_perm('projectapp.change_task'),
            'can_delete_task': u.has_perm('projectapp.delete_task'),
            'can_change_project': u.has_perm('projectapp.change_project'),
            'can_delete_project': u.has_perm('projectapp.delete_project'),
            'can_add_milestone': u.has_perm('projectapp.add_milestone'),
            'can_change_milestone': u.has_perm('projectapp.change_milestone'),
            'can_delete_milestone': u.has_perm('projectapp.delete_milestone'),
        })
        return context


# ---------- TASK VIEWS ----------
class TaskCreateView(LoginRequiredMixin, PermissionMixin, CreateView):
    model = Task
    form_class = TaskForm
    template_name = 'projectapp/task_form.html'
    permission_required = 'projectapp.add_task'

    def dispatch(self, request, *args, **kwargs):
        self.project = get_object_or_404(Project, id=kwargs['project_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['project'] = self.project
        return kwargs

    def form_valid(self, form):
        task = form.save(commit=False)
        task.project = self.project
        task.save()
        form.save_m2m()

        new_tags_str = self.request.POST.get('new_tags', '').strip()
        if new_tags_str:
            new_tags_list = [t.strip() for t in new_tags_str.split(',') if t.strip()]
            
            for tag_name in new_tags_list:
                # Create the tag if it doesn't exist, linked to the project
                tag, created = Tag.objects.get_or_create(name=tag_name, project=task.project)
                # Assign the newly created/found tag to the task
                task.tags.add(tag)

        
        messages.success(self.request, f"Task '{task.title}' created successfully.")
        return redirect('project_detail', pk=self.project.id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        u = self.request.user
        context.update({
            'project': self.project,
            'can_add_task': u.has_perm('projectapp.add_task'),
            'can_change_task': u.has_perm('projectapp.change_task'),
        })
        return context


class TaskUpdateView(LoginRequiredMixin, PermissionMixin, UpdateView):
    model = Task
    form_class = TaskForm
    template_name = 'projectapp/task_form.html'
    permission_required = 'projectapp.change_task'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['project'] = Project.objects.get(pk=self.object.project_id)
        return kwargs
    
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not obj.project_id:
            raise Http404("Task is missing a project assignment.")
        return obj

    def form_valid(self, form):
        current_project = Project.objects.get(pk=self.object.project_id)
        task = form.save(commit=False)
        if not task.project_id: ###
            task.project = current_project ###
        task.save()
        form.save_m2m()
        
        new_tags_str = self.request.POST.get('new_tags', '').strip()
        if new_tags_str:
            new_tags_list = [t.strip() for t in new_tags_str.split(',') if t.strip()]
            
            for tag_name in new_tags_list:
                # Get or create the tag, linked to the project (using task.project which is the existing project)
                tag, created = Tag.objects.get_or_create(name=tag_name, project=task.project)
                # Assign the newly created/found tag to the task
                task.tags.add(tag)
        
        
        messages.success(self.request, f"Task '{task.title}' updated successfully.")
        return redirect('project_detail', pk=task.project.id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        u = self.request.user
        project = Project.objects.get(pk=self.object.project_id)
        context.update({
            'project': project,
            'task': self.object,
            'can_add_task': u.has_perm('projectapp.add_task'),
            'can_change_task': u.has_perm('projectapp.change_task'),
        })
        return context


class TaskDeleteView(LoginRequiredMixin, PermissionMixin, DeleteView):
    model = Task
    template_name = 'projectapp/task_confirm_delete.html'
    permission_required = 'projectapp.delete_task'

    def get_success_url(self):
        return reverse_lazy('project_detail', kwargs={'pk': self.object.project.id})


class TaskDetailView(DetailView):
    model = Task
    template_name = 'projectapp/task_detail.html'
    context_object_name = 'task'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task = self.object
        task.overdue = task.is_overdue()
        u = self.request.user
        context.update({
            'project': task.project,
            'can_edit_task': u.has_perm('projectapp.change_task'),
            'can_delete_task': u.has_perm('projectapp.delete_task'),
        })
        return context


# ---------- MILESTONE VIEWS ----------
class MilestoneCreateView(LoginRequiredMixin, PermissionMixin, CreateView):
    model = Milestone
    form_class = MilestoneForm
    template_name = 'projectapp/milestone_form.html'
    permission_required = 'projectapp.add_milestone' 

    def dispatch(self, request, *args, **kwargs):
        self.project = get_object_or_404(Project, id=kwargs['project_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['project'] = self.project        
        return kwargs

    def form_valid(self, form):
        form.instance.project = self.project
        response = super().form_valid(form)  # This calls form.save()
        
        
        messages.success(self.request, f"Milestone '{form.instance.name}' created successfully.")
        
        return response

    def get_success_url(self):
        return reverse_lazy('project_detail', kwargs={'pk': self.project.id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['project'] = self.project
        context['can_add_milestone'] = self.request.user.has_perm(self.permission_required)
        return context
    
class MilestoneUpdateView(LoginRequiredMixin, PermissionMixin, UpdateView):
    model = Milestone
    form_class = MilestoneForm
    template_name = 'projectapp/milestone_form.html'
    permission_required = 'projectapp.change_milestone'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['project'] = self.object.project
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['project'] = self.object.project
        context['can_delete_milestone'] = self.request.user.has_perm('projectapp.delete_milestone')
        context['can_change_milestone'] = self.request.user.has_perm(self.permission_required)
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)  # This calls form.save()
        
        
        messages.success(self.request, f"Milestone '{form.instance.name}' updated successfully.")
        
        return response

    def get_success_url(self):
        return reverse_lazy('project_detail', kwargs={'pk': self.object.project.id})


class MilestoneDeleteView(LoginRequiredMixin, PermissionMixin, DeleteView):
    """
    Handles the deletion of an existing Milestone.
    """
    model = Milestone
    template_name = 'projectapp/milestone_confirm_delete.html'
    permission_required = 'projectapp.delete_milestone'

    def get_success_url(self):
        # Store project ID before deletion
        project_id = self.object.project.id
        return reverse_lazy('project_detail', kwargs={'pk': project_id})
    
    def form_valid(self, form):
        project = self.object.project
        milestone_title = self.object.name

        response = super().form_valid(form)
        

        messages.success(self.request, f"Milestone '{milestone_title}' deleted successfully.")
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object_type'] = 'Milestone'
        # Pass parent object ID for the cancel link in confirm_delete.html
        context['parent_object_id'] = self.object.project.id 
        context['can_delete_milestone'] = self.request.user.has_perm(self.permission_required)
        return context
    
class MilestoneDetailView(DetailView):
    """
    Displays the detail of a single Milestone.
    Includes permission checks for editing/deleting the milestone.
    """
    model = Milestone
    template_name = 'projectapp/milestone_detail.html'
    context_object_name = 'milestone'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        milestone = self.object
        u = self.request.user
        
        context.update({
            # Tasks linked via the related_name 'tasks' on the Milestone model
            'tasks': milestone.tasks.all().select_related('milestone').order_by('due_date'),
            
            # Permission Checks (following the pattern used in ProjectDetailView)
            'can_view_milestone': u.has_perm('projectapp.view_milestone'), # Good practice
            'can_change_milestone': u.has_perm('projectapp.change_milestone'),
            'can_delete_milestone': u.has_perm('projectapp.delete_milestone'),
            
            # Additional context for linked tasks
            'can_add_task': u.has_perm('projectapp.add_task'),
            'can_change_task': u.has_perm('projectapp.change_task'),
            
            # Pass the project object itself
            'project': milestone.project,
        })
        return context

# ---------- OTHER FUNCTIONAL VIEWS ----------

def project_board(request, pk):
    project = get_object_or_404(Project, pk=pk)

    all_tasks = project.tasks.all().select_related('milestone')

    tasks = {
        'todo': all_tasks.filter(status='todo').order_by('priority', 'due_date'),
        'in_progress': all_tasks.filter(status='in_progress').order_by('priority', 'due_date'),
        'done': all_tasks.filter(status='done').order_by('-updated_at'),
    }

    can_edit = request.user.has_perm('projectapp.change_task')
    can_add_milestone = request.user.has_perm('projectapp.add_milestone')

    return render(request, 'projectapp/project_board.html', {
        'project': project,
        'tasks': tasks,
        'can_edit': can_edit,
        'can_add_milestone': can_add_milestone,
    })

#@login_required
def task_move(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        task_id = data.get('task_id')
        new_status = data.get('status')

        task = get_object_or_404(Task, id=task_id)
        if not request.user.has_perm('projectapp.change_task'):
            return JsonResponse({'success': False}, status=403) # Forbidden
        if new_status in ['todo', 'in_progress', 'done']:
            task.status = new_status
            task.save()
            return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)


def search(request):
    query = request.GET.get('search')
    sort_by = request.GET.get('sort', 'title')

    project_results = Project.objects.all()
    task_results = Task.objects.all()

    if query:
        project_filter = Q(title__icontains=query) | Q(description__icontains=query)
        task_filter = Q(title__icontains=query) | Q(description__icontains=query)
        project_results = project_results.filter(project_filter).distinct()
        task_results = task_results.filter(task_filter).distinct()

    if sort_by == 'priority':
        project_results = project_results.order_by('tasks__priority')
        task_results = task_results.order_by('priority')
    elif sort_by == 'due_date':
        project_results = project_results.order_by('tasks__due_date')
        task_results = task_results.order_by('due_date')

    u = request.user
    context = {
        'project_results': project_results,
        'task_results': task_results,
        'sort_by': sort_by,
        'query': query,
        'can_add_task': u.has_perm('projectapp.add_task'),
        'can_change_task': u.has_perm('projectapp.change_task'),
        'can_delete_task': u.has_perm('projectapp.delete_task'),
        'can_change_project': u.has_perm('projectapp.change_project'),
        'can_delete_project': u.has_perm('projectapp.delete_project'),
    }
    return render(request, 'projectapp/search_results.html', context)


def tasks_by_tag(request, id, tag_id):
    project = get_object_or_404(Project, id=id)
    tasks = project.tasks.filter(tags__id=tag_id).distinct()
    for task in tasks:
        task.overdue = task.is_overdue()
    return render(request, 'projectapp/tasks_by_tag.html', {
        'project': project,
        'tasks': tasks,
        'tag': get_object_or_404(Tag, id=tag_id),
    })
