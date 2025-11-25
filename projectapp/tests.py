from django.test import TestCase
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from django.db import IntegrityError

from .models import Project, Task, Milestone, Tag

class ProjectModelTests(TestCase):

    def test_progress_no_tasks(self):
        p = Project.objects.create(title="Empty")
        self.assertEqual(p.progress, 0.0)

    def test_progress_no_milestones_simple_tasks(self):
        p = Project.objects.create(title="Simple")
        Task.objects.create(project=p, title="A", due_date=date.today(), status="done")
        Task.objects.create(project=p, title="B", due_date=date.today(), status="todo")
        Task.objects.create(project=p, title="C", due_date=date.today(), status="todo")

        # 1/3 done = 33.33
        self.assertAlmostEqual(p.progress, 33.33, places=2)

    def test_progress_with_milestones_all_tasks_done(self):
        p = Project.objects.create(title="Proj")
        m = Milestone.objects.create(project=p, name="MS1", due_date=date.today())

        Task.objects.create(project=p, milestone=m, title="A", status="done", due_date=date.today())
        Task.objects.create(project=p, milestone=m, title="B", status="done", due_date=date.today())

        self.assertEqual(p.progress, 100.0)

    def test_progress_with_milestones_none_complete_strict(self):
        """
        Milestones exist → 90% weighting.
        Milestone incomplete → milestone contribution = 0%
        Stray tasks exist → 10% weighting.
        If stray tasks also incomplete → total = 0%.
        """
        p = Project.objects.create(title="Proj")
        m = Milestone.objects.create(project=p, name="MS1", due_date=date.today())

        Task.objects.create(project=p, milestone=m, title="A", due_date=date.today(), status='done')
        Task.objects.create(project=p, milestone=m, title="B", due_date=date.today(), status='todo')

        # Stray incomplete task
        Task.objects.create(project=p, title="C", due_date=date.today(), status='todo')

        self.assertEqual(p.progress, 0.0)

    def test_progress_with_milestones_complete_and_stray_half(self):
        p = Project.objects.create(title="Proj")
        m = Milestone.objects.create(project=p, name="MS1", due_date=date.today())

        Task.objects.create(project=p, milestone=m, title="A", due_date=date.today(), status="done")
        Task.objects.create(project=p, milestone=m, title="B", due_date=date.today(), status="done")

        Task.objects.create(project=p, title="C", due_date=date.today(), status="done")
        Task.objects.create(project=p, title="D", due_date=date.today(), status="todo")

        # milestone = complete → contributes 90%
        # stray = 1/2 = 50% → contributes 5%
        # total = 95%
        self.assertEqual(p.progress, 95.0)


class MilestoneTests(TestCase):

    def setUp(self):
        self.p = Project.objects.create(title="P")
        self.m = Milestone.objects.create(project=self.p, name="MS", due_date=date.today())

    def test_milestone_complete_property(self):
        Task.objects.create(project=self.p, milestone=self.m,
                            title="A", due_date=date.today(), status="todo")
        self.assertFalse(self.m.is_complete)

        # now complete
        t = Task.objects.get(title="A")
        t.status = "done"
        t.save()
        self.m.refresh_from_db()
        self.assertTrue(self.m.is_complete)

    def test_milestone_latest_due_date(self):
        d1 = date.today() + timedelta(days=3)
        d2 = date.today() + timedelta(days=7)

        Task.objects.create(project=self.p, milestone=self.m, title="A", due_date=d1)
        Task.objects.create(project=self.p, milestone=self.m, title="B", due_date=d2)

        self.assertEqual(self.m.latest_due_date(), d2)

    def test_milestone_recalculates_due_date(self):
        d1 = date.today() + timedelta(days=5)
        d2 = date.today() + timedelta(days=12)

        t1 = Task.objects.create(project=self.p, milestone=self.m, title="A", due_date=d1)
        t2 = Task.objects.create(project=self.p, milestone=self.m, title="B", due_date=d2)

        self.m.recalculate_and_save_date()
        self.m.refresh_from_db()
        self.assertEqual(self.m.due_date, d2)

    def test_milestone_due_date_updates_when_task_deleted(self):
        d1 = date.today() + timedelta(days=5)
        d2 = date.today() + timedelta(days=12)

        t1 = Task.objects.create(project=self.p, milestone=self.m, title="A", due_date=d1)
        t2 = Task.objects.create(project=self.p, milestone=self.m, title="B", due_date=d2)

        self.m.recalculate_and_save_date()
        self.assertEqual(self.m.due_date, d2)

        t2.delete()
        self.m.recalculate_and_save_date()
        self.m.refresh_from_db()

        self.assertEqual(self.m.due_date, d1)


class TaskTests(TestCase):

    def setUp(self):
        self.p = Project.objects.create(title="P")
        self.m1 = Milestone.objects.create(project=self.p, name="M1", due_date=date.today())
        self.m2 = Milestone.objects.create(project=self.p, name="M2", due_date=date.today())

    def test_task_overdue(self):
        overdue = Task.objects.create(project=self.p, title="A",
                                      due_date=date.today() - timedelta(days=1),
                                      status="todo")
        self.assertTrue(overdue.is_overdue())

        not_overdue = Task.objects.create(project=self.p, title="B",
                                          due_date=date.today() + timedelta(days=1),
                                          status="in_progress")
        self.assertFalse(not_overdue.is_overdue())

        done_past = Task.objects.create(project=self.p, title="C",
                                        due_date=date.today() - timedelta(days=10),
                                        status="done")
        self.assertFalse(done_past.is_overdue())

    def test_moving_task_updates_both_milestones(self):
        # Task initially belongs to m1
        t = Task.objects.create(
            title="Moveable",
            due_date=date(2025, 12, 5),
            milestone=self.m1,
            project=self.p
        )

        # Initial milestone due
        old_m1_due = self.m1.due_date

        # Move task to m2
        t.milestone = self.m2
        t.save()

        # Refresh both milestones
        self.m1.refresh_from_db()
        self.m2.refresh_from_db()

        # m1 should update because task removed
        self.assertNotEqual(old_m1_due, self.m1.due_date)

        # m2 should update because task added
        self.assertEqual(self.m2.due_date, t.due_date)

        # task due date must remain unchanged (never recalculated)
        self.assertEqual(t.due_date, date(2025, 12, 5))

    def test_circular_dependency_self(self):
        t = Task.objects.create(
            project=self.p, title="A",
            due_date=date.today()
        )
        with self.assertRaises(ValidationError):
            t.prerequisite_tasks.set([t])

    def test_circular_dependency_chain(self):
        a = Task.objects.create(project=self.p, title="A", due_date=date.today())
        b = Task.objects.create(project=self.p, title="B", due_date=date.today())
        c = Task.objects.create(project=self.p, title="C", due_date=date.today())

        b.prerequisite_tasks.add(a)
        c.prerequisite_tasks.add(b)

        # This should create a cycle
        with self.assertRaises(ValidationError):
            a.prerequisite_tasks.add(c)


class TagTests(TestCase):

    def setUp(self):
        self.p = Project.objects.create(title="P")

    def test_unique_tag_per_project(self):
        Tag.objects.create(project=self.p, name="Feature")
        with self.assertRaises(IntegrityError):
            Tag.objects.create(project=self.p, name="Feature")

    def test_same_tag_name_in_different_projects(self):
        Tag.objects.create(project=self.p, name="Feature")
        p2 = Project.objects.create(title="Other")
        tag = Tag.objects.create(project=p2, name="Feature")
        self.assertIsNotNone(tag.pk)

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
        self.task_1 = Task.objects.create(project=self.project_a, title="Done Task", status='done', due_date=date.today())
        self.task_2 = Task.objects.create(project=self.project_a, title="In Progress Task", status='in_progress', due_date=date.today())
        self.task_3 = Task.objects.create(project=self.project_a, title="To Do Task", status='todo', due_date=date.today())

    def test_progress_calculation(self):
        """Tests Project.progress logic."""
        # Project A: 1 done / 3 total tasks = 33%
        self.assertAlmostEqual(self.project_a.progress, 33.333, places=2)
        
        # Test 100% completion
        self.task_2.status = 'done'
        self.task_2.save()
        self.task_3.status = 'done'
        self.task_3.save()
        self.assertEqual(self.project_a.progress, 100.00)

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
        self.list_url = reverse('project_list')
        
    def test_login_not_required(self):
        """Anonymous users should be able to access the project list."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projectapp/project_list_new.html')

    def test_permissions_in_context_for_anonymous(self):
        """Anonymous users should not have any project/task permissions."""
        response = self.client.get(self.list_url)
        self.assertFalse(response.context['can_add_project'])
        self.assertFalse(response.context['can_change_project'])
        self.assertFalse(response.context['can_delete_project'])
        self.assertFalse(response.context['can_add_task'])
        self.assertFalse(response.context['can_change_task'])
        self.assertFalse(response.context['can_delete_task']) 
    
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
        response = self.client.post(self.create_url)
        
        # Should be redirected to home_page (as defined in PermissionMixin)
        self.assertRedirects(response, reverse('project_list')) 

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
        self.task = Task.objects.create(project=self.project, title="Move Me", status='todo', due_date=date.today())
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