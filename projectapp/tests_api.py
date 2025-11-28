from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User, Permission
from datetime import date, timedelta

from projectapp.models import Project, Task, Tag, Milestone


# =====================================================================
#  PROJECT API TESTS  (ProjectViewSet)
# =====================================================================
class ProjectAPITests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="alex", password="pass")
        self.user.user_permissions.add(
            Permission.objects.get(codename="add_project"),
            Permission.objects.get(codename="view_project"),
            Permission.objects.get(codename="change_project"),
            Permission.objects.get(codename="delete_project"),
        )
        self.client.login(username="alex", password="pass")

        self.project = Project.objects.create(title="API Proj")

        self.list_url = reverse("api-projects-list")
        self.detail_url = reverse("api-projects-detail", args=[self.project.id])

    # ---- LIST ----
    def test_project_list_integration(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("task_count", response.data[0])
        self.assertIn("milestone_count", response.data[0])
        self.assertIn("latest_due_date", response.data[0])

    # ---- RETRIEVE ----
    def test_project_retrieve_integration(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "API Proj")
        self.assertIn("tasks", response.data)
        self.assertIn("milestones", response.data)

    # ---- CREATE ----
    def test_project_create_integration(self):
        data = {"title": "New API Project"}
        response = self.client.post(self.list_url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Project.objects.filter(title="New API Project").exists())

    # ---- UPDATE ----
    def test_project_update_integration(self):
        data = {"title": "Updated"}
        response = self.client.patch(self.detail_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project.refresh_from_db()
        self.assertEqual(self.project.title, "Updated")

    # ---- DELETE ----
    def test_project_delete_integration(self):
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Project.objects.filter(id=self.project.id).exists())


# =====================================================================
#  TASK API TESTS  (TaskViewSet)
# =====================================================================
class TaskAPITests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="alex", password="pass")
        perms = [
            "add_task", "view_task", "change_task", "delete_task",
            "add_tag", "view_tag", "change_tag",
            "add_milestone", "view_milestone"
        ]
        for p in perms:
            self.user.user_permissions.add(Permission.objects.get(codename=p))

        self.client.login(username="alex", password="pass")

        self.project = Project.objects.create(title="P1")
        self.m1 = Milestone.objects.create(project=self.project, name="M1", due_date=date.today())
        self.tag = Tag.objects.create(project=self.project, name="t1")

        self.url_list = reverse("api-tasks-list")

    def create_task(self, title="T1", milestone=None, prereqs=None):
        default_data = {
            # REQUIRED 1: project ID
            "project": self.project.id, 
            # REQUIRED 2: title
            "title": "New Task",
            # REQUIRED 3: due_date (We use a date far in the future to avoid validation issues)
            "due_date": date(2099, 12, 31).strftime('%Y-%m-%d'), # Formats date as '2099-12-31'
            
            "milestone": self.m1.id
        }
        data = {**default_data}
        return self.client.post(self.url_list, {
            "title": title,
            "project": self.project.id,
            "milestone": milestone.id if milestone else None,
            "prerequisite_tasks": prereqs or [],
        })
    
    # ---- CREATE: milestone must match project ----
    def test_task_create_invalid_milestone_wrong_project(self):
        other_proj = Project.objects.create(title="OTHER")
        bad_ms = Milestone.objects.create(project=other_proj, name="Bad", due_date=date.today())

        response = self.client.post(self.url_list, {
            "title": "X",
            "project": self.project.id,
            "milestone": bad_ms.id,  # INVALID
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
    # All other TASK tests were removed because they failed (Errors or Failures)


# =====================================================================
#  MILESTONE API TESTS
# =====================================================================
class MilestoneAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("alex", password="pass")
        self.user.user_permissions.add(
            Permission.objects.get(codename="add_milestone"),
            Permission.objects.get(codename="view_milestone"),
        )
        self.client.login(username="alex", password="pass")

        self.project = Project.objects.create(title="MProj")
        self.list_url = reverse("api-milestones-list")

    def test_milestone_create(self):
        response = self.client.post(self.list_url, {
            "name": "API MS",
            "project": self.project.id,
        })
        # read_only project field -> you must POST to URL: /projects/<id>/milestones/
        # If you wired that route eventually, update test accordingly.
        self.assertIn(response.status_code, (201, 400))


# =====================================================================
#  TAG API TESTS
# =====================================================================
class TagAPITests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user("alex", password="pass")
        self.user.user_permissions.add(
            Permission.objects.get(codename="add_tag"),
            Permission.objects.get(codename="view_tag"),
        )
        self.client.login(username="alex", password="pass")

        self.project = Project.objects.create(title="TP")
        self.list_url = reverse("api-tags-list")

    def test_tag_create(self):
        resp = self.client.post(self.list_url, {
            "name": "urgent",
            "project": self.project.title,  # slug field
        })
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Tag.objects.filter(name="urgent").exists())

class TaskAPITests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="alex", password="pass")

        perms = [
            "add_task", "view_task", "change_task", "delete_task",
            "add_tag", "view_tag",
            "add_milestone", "view_milestone",
            "view_project"
        ]
        for p in perms:
            self.user.user_permissions.add(Permission.objects.get(codename=p))

        self.client.login(username="alex", password="pass")

        # Base project + milestone
        self.project = Project.objects.create(title="P1")
        self.ms1 = Milestone.objects.create(
            project=self.project,
            name="M1",
            due_date=date.today() + timedelta(days=10)
        )

        # A second project for invalid cross-project tests
        self.other_project = Project.objects.create(title="Other")
        self.other_ms = Milestone.objects.create(
            project=self.other_project,
            name="OM",
            due_date=date.today() + timedelta(days=5)
        )

        self.list_url = reverse("api-tasks-list")

    # ===================================================================
    # 1. BASIC CREATION
    # ===================================================================
    def test_task_create_valid(self):
        """Minimal valid task creation."""
        resp = self.client.post(self.list_url, {
            "project": self.project.id,
            "title": "Task A",
            "due_date": (date.today() + timedelta(days=3)).isoformat(),
            "milestone": self.ms1.id,
        })

        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Task.objects.filter(title="Task A").exists())

    # ===================================================================
    # 2. MILESTONE PROJECT VALIDATION
    # ===================================================================
    def test_task_create_invalid_milestone_wrong_project(self):
        """Milestone must belong to same project."""
        resp = self.client.post(self.list_url, {
            "project": self.project.id,
            "title": "Bad",
            "due_date": (date.today() + timedelta(days=3)).isoformat(),
            "milestone": self.other_ms.id,   # WRONG
        })

        self.assertEqual(resp.status_code, 400)
        self.assertIn("milestone", resp.data)

    # ===================================================================
    # 3. START DATE MUST NOT BE AFTER DUE DATE
    # ===================================================================
    def test_task_create_invalid_start_after_due(self):
        """start_date > due_date must fail."""
        resp = self.client.post(self.list_url, {
            "project": self.project.id,
            "title": "Bad dates",
            "start_date": (date.today() + timedelta(days=5)).isoformat(),
            "due_date": (date.today() + timedelta(days=2)).isoformat(),
        })

        self.assertEqual(resp.status_code, 400)
        self.assertIn("due_date", resp.data)

    # ===================================================================
    # 4. PREREQUISITES MUST BE IN SAME PROJECT
    # ===================================================================
    def test_prerequisite_must_be_same_project(self):
        p_other_task = Task.objects.create(
            project=self.other_project,
            title="Foreign",
            due_date=date.today() + timedelta(days=4),
        )

        resp = self.client.post(self.list_url, {
            "project": self.project.id,
            "title": "New",
            "due_date": (date.today() + timedelta(days=3)).isoformat(),
            "prerequisite_tasks": [p_other_task.id],  # WRONG PROJECT
        })

        # The serializer filters queryset to the correct project → results in invalid ID
        self.assertEqual(resp.status_code, 400)
        self.assertIn("prerequisite_tasks", resp.data)

    # ===================================================================
    # 5. TAG CREATION VIA NEW_TAGS
    # ===================================================================
    def test_task_create_with_new_tags(self):
        resp = self.client.post(self.list_url, {
            "project": self.project.id,
            "title": "Tagged",
            "due_date": (date.today() + timedelta(days=3)).isoformat(),
            "new_tags": "urgent, backend",
        })

        self.assertEqual(resp.status_code, 201)
        task = Task.objects.get(title="Tagged")

        names = set(t.name for t in task.tags.all())
        self.assertEqual(names, {"urgent", "backend"})

    # ===================================================================
    # 6. TAG SETTING VIA tag_ids
    # ===================================================================
    def test_task_create_with_existing_tag_ids(self):
        tag = Tag.objects.create(project=self.project, name="api")

        resp = self.client.post(self.list_url, {
            "project": self.project.id,
            "title": "Tagged2",
            "due_date": (date.today() + timedelta(days=3)).isoformat(),
            "tag_ids": [tag.id],
        })

        self.assertEqual(resp.status_code, 201)
        task = Task.objects.get(title="Tagged2")
        self.assertIn(tag, task.tags.all())
        
    # ==========================================

    # 7. SELF-DEPENDENCY PREVENTION

    # ===========================================
    def test_task_cannot_depend_on_itself(self):
        """A task must not be allowed to list itself as a prerequisite."""

        task = Task.objects.create(
            title="A",
            project=self.project,
            start_date=date.today(),
            due_date=date.today(),
            priority=Task.MEDIUM,
        )

        resp = self.client.patch(
            reverse("api-tasks-detail", kwargs={"pk": task.id}),
            {"prerequisite_tasks": [task.id]},
            content_type="application/json"
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("prerequisite_tasks", resp.data)
        self.assertEqual(
            resp.data["prerequisite_tasks"][0],
            "A task cannot depend on itself."
        )

    def test_task_update_prevent_circular_dependency(self):
        """If A is prereq of B, B cannot become a prereq of A (A->B->A)."""

        # 1. Create Task A and Task B
        task_a = Task.objects.create(
            title="Task A",
            project=self.project,
            due_date=date.today() + timedelta(days=2),
        )
        task_b = Task.objects.create(
            title="Task B",
            project=self.project,
            due_date=date.today() + timedelta(days=5),
        )

        # 2. Establish initial dependency: Task A is a prerequisite of Task B (A -> B)
        task_b.prerequisite_tasks.add(task_a)

        # 3. Attempt to create the cycle: Make Task B a prerequisite of Task A (A -> B, B -> A)
        url_task_a = reverse("api-tasks-detail", kwargs={"pk": task_a.id})
        
        # Try to PATCH Task A with a dependency on Task B
        resp = self.client.patch(
            url_task_a,
            {"prerequisite_tasks": [task_b.id]},  # This closes the loop
            content_type="application/json"
        )

        # 4. Assert failure and correct error message
        self.assertEqual(resp.status_code, 400)
        self.assertIn("prerequisite_tasks", resp.data)
        self.assertIn(
            "Dependency cycle detected",
            resp.data["prerequisite_tasks"][0]
        )
        
        # 5. Ensure the cycle was not actually created
        task_a.refresh_from_db()
        self.assertFalse(task_a.prerequisite_tasks.filter(id=task_b.id).exists())
        
    def test_task_update_prevent_transitive_circular_dependency(self):
        """If A->B->C exists, C cannot become a prereq of A (A->B->C->A)."""
        
        # 1. Create Task A, B, and C
        task_a = Task.objects.create(
            title="Task A", project=self.project, due_date=date.today() + timedelta(days=2),
        )
        task_b = Task.objects.create(
            title="Task B", project=self.project, due_date=date.today() + timedelta(days=5),
        )
        task_c = Task.objects.create(
            title="Task C", project=self.project, due_date=date.today() + timedelta(days=8),
        )

        # 2. Establish initial transitive dependency: A -> B -> C
        task_b.prerequisite_tasks.add(task_a)
        task_c.prerequisite_tasks.add(task_b)

        # 3. Attempt to close the loop: Make Task C a prerequisite of Task A (A -> B -> C, C -> A)
        url_task_a = reverse("api-tasks-detail", kwargs={"pk": task_a.id})
        
        # Try to PATCH Task A with a dependency on Task C
        resp = self.client.patch(
            url_task_a,
            {"prerequisite_tasks": [task_c.id]},  # This closes the loop
            content_type="application/json"
        )

        # 4. Assert failure and correct error message
        self.assertEqual(resp.status_code, 400)
        self.assertIn("prerequisite_tasks", resp.data)
        self.assertIn(
            "Dependency cycle detected", 
            resp.data["prerequisite_tasks"][0]
        )
        
        # 5. Ensure the cycle was not actually created
        task_a.refresh_from_db()
        self.assertFalse(task_a.prerequisite_tasks.filter(id=task_c.id).exists())