from django.test import TestCase, Client
from django.urls import reverse
from projectapp.models import Project, Task, Tag
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from datetime import date, timedelta
import json

def get_permission(model_class, action):
    """Utility to get a specific permission object."""
    ctype = ContentType.objects.get_for_model(model_class)
    return Permission.objects.get(content_type=ctype, codename=f'{action}_{model_class._meta.model_name}')


class ProjectModelTest(TestCase):
    def setUp(self):
        self.project_a = Project.objects.create(title="Project Alpha")
        self.task_1 = Task.objects.create(project=self.project_a, title="Done Task", status='done')
        self.task_2 = Task.objects.create(project=self.project_a, title="In Progress Task", status='in_progress')
        self.task_3 = Task.objects.create(project=self.project_a, title="To Do Task", status='todo')

    def test_progress_calculation(self):
        """Tests Project.calculate_progress() logic."""
        # Project A: 1 done / 3 total tasks = 33%
        self.assertAlmostEqual(self.project_a.calculate_progress(), 33.333, places=3)
        
        # Test 100% completion
        self.task_2.status = 'done'
        self.task_2.save()
        self.task_3.status = 'done'
        self.task_3.save()
        self.assertEqual(self.project_a.calculate_progress(), 100.00)

    def test_is_overdue(self):
        """Tests Task.is_overdue() logic."""
        # Not overdue (due date in the future)
        future_task = Task.objects.create(project=self.project_a, title="Future", due_date=date.today() + timedelta(days=5))
        self.assertFalse(future_task.is_overdue())

        # Overdue (due date in the past and not 'done')
        past_task = Task.objects.create(project=self.project_a, title="Past", due_date=date.today() - timedelta(days=5), status='todo')
        self.assertTrue(past_task.is_overdue())
        
        # Completed task is never overdue
        completed_past_task = Task.objects.create(project=self.project_a, title="Completed Past", due_date=date.today() - timedelta(days=5), status='done')
        self.assertFalse(completed_past_task.is_overdue())

class ProjectListViewTest(TestCase):
    def setUp(self):
        # Setup: Create a test user and a client
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='password')
        self.list_url = reverse('project_list_name') # Replace with your actual URL name

    def test_login_required(self):
        # Test 1: Check LoginRequiredMixin
        response = self.client.get(self.list_url)
        # Should redirect to the login page
        self.assertRedirects(response, f'/accounts/login/?next={self.list_url}')

    def test_view_uses_correct_template_and_context(self):
        # Login the user
        self.client.login(username='tester', password='password')
        response = self.client.get(self.list_url)
        
        # Test 2: Check template and context name
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projectapp/project_list_new.html')
        self.assertIn('project_results', response.context)
        
    def test_queryset_sorting(self):
        # Test 3: Check sorting by title
        self.client.login(username='tester', password='password')
        response = self.client.get(self.list_url + '?sort=title')
        # ... logic to check order of projects ...
        pass

class ProjectViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='password')
        self.project_c = Project.objects.create(title="Zeta Project")
        self.project_a = Project.objects.create(title="Alpha Project")
        self.list_url = reverse('project_list') # Assuming URL name is 'project_list'
        self.detail_url = reverse('project_detail', args=[self.project_a.id])

        # Tasks for sorting test
        Task.objects.create(project=self.project_a, title="Task Low Priority", priority=1, due_date=date.today() + timedelta(days=10))
        Task.objects.create(project=self.project_a, title="Task High Priority", priority=3, due_date=date.today() + timedelta(days=5))
        
    def test_list_sorting_by_title(self):
        """Test ProjectListView default sorting."""
        self.client.login(username='tester', password='password')
        response = self.client.get(self.list_url + '?sort=title')
        
        # Assert 'Alpha Project' comes before 'Zeta Project'
        self.assertEqual(response.context['project_results'][0].title, "Alpha Project")

    def test_detail_task_sorting_by_priority(self):
        """Test ProjectDetailView task sorting."""
        self.client.login(username='tester', password='password')
        response = self.client.get(self.detail_url + '?sort=priority')
        tasks = response.context['tasks']
        
        # Priority 3 (High) should come first due to order_by('-priority')
        self.assertEqual(tasks[0].title, "Task High Priority")

    def test_detail_task_overdue_flag(self):
        """Test that tasks in detail view have the 'overdue' flag attached."""
        self.client.login(username='tester', password='password')
        
        # Create an overdue task
        Task.objects.create(
            project=self.project_a, 
            title="Old Task", 
            due_date=date.today() - timedelta(days=1), 
            status='todo'
        )
        
        response = self.client.get(self.detail_url)
        # Check that at least one task has the 'overdue' attribute attached
        self.assertTrue(any(t.overdue for t in response.context['tasks']))
        
class ProjectCrudTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_no_perm = User.objects.create_user(username='no_perm', password='password')
        self.user_with_perm = User.objects.create_user(username='can_add', password='password')
        
        # Grant the user permission to ADD projects
        add_perm = get_permission(Project, 'add')
        self.user_with_perm.user_permissions.add(add_perm)
        
        self.create_url = reverse('project_create') # Assuming URL name
        
    def test_create_permission_denied(self):
        """Test ProjectCreateView redirects unauthorized user via PermissionMixin."""
        self.client.login(username='no_perm', password='password')
        response = self.client.get(self.create_url)
        
        # Should be redirected to home_page (as defined in PermissionMixin)
        self.assertRedirects(response, reverse('home_page')) 

    def test_create_success(self):
        """Test ProjectCreateView with correct permission."""
        self.client.login(username='can_add', password='password')
        response = self.client.post(self.create_url, {
            'title': 'New Test Project',
            'description': 'A new project.',
            'status': 'todo' # Assuming ProjectForm handles status/fields
        })
        
        # Should redirect to project_list on success (200 OK after redirect)
        self.assertRedirects(response, reverse('project_list'))
        # Assert object was created
        self.assertTrue(Project.objects.filter(title='New Test Project').exists())

class TaskApiTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_no_perm = User.objects.create_user(username='no_perm', password='password')
        self.user_with_perm = User.objects.create_user(username='can_change', password='password')
        
        # Grant user permission to CHANGE tasks
        change_perm = get_permission(Task, 'change')
        self.user_with_perm.user_permissions.add(change_perm)
        
        self.project = Project.objects.create(title="Test Project")
        self.task = Task.objects.create(project=self.project, title="Move Me", status='todo')
        self.move_url = reverse('task_move') # Assuming URL name

    def test_task_move_unauthorized(self):
        """CRITICAL: Test that a logged-in user without perm is blocked (403)."""
        self.client.login(username='no_perm', password='password')
        
        response = self.client.post(self.move_url, 
            json.dumps({'task_id': self.task.id, 'status': 'done'}), 
            content_type='application/json'
        )
        
        # Assert 403 Forbidden status
        self.assertEqual(response.status_code, 403) 
        # Assert the status did NOT change
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, 'todo')

    def test_task_move_authorized(self):
        """Test authorized task status change."""
        self.client.login(username='can_change', password='password')
        
        response = self.client.post(self.move_url, 
            json.dumps({'task_id': self.task.id, 'status': 'in_progress'}), 
            content_type='application/json'
        )
        
        # Assert success
        self.assertEqual(response.status_code, 200)
        # Assert the status DID change
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, 'in_progress')