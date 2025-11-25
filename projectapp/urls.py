from django.urls import path, include
from django.contrib.auth import views as auth_views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    # Static / Functional Views
    path('', views.main, name='home_page'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='projectapp/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('hint/', views.hint, name='hint'),

    # --- Project Views (CBVs) ---
    path('project_list/', views.ProjectListView.as_view(), name='project_list'),
    path('projects/new/', views.ProjectCreateView.as_view(), name='project_create'),
    path('project/<int:pk>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('project/<int:pk>/edit/', views.ProjectUpdateView.as_view(), name='project_edit'),
    path('project/<int:pk>/delete/', views.ProjectDeleteView.as_view(), name='project_delete'),

    # --- Task Views (CBVs + Functional) ---
    path('projects/<int:project_id>/tasks/new/', views.TaskCreateView.as_view(), name='task_create'),
    path('task/<int:pk>/', views.TaskDetailView.as_view(), name='task_detail'),
    path('task/<int:pk>/edit/', views.TaskUpdateView.as_view(), name='task_edit'),
    path('task/<int:pk>/delete/', views.TaskDeleteView.as_view(), name='task_delete'),
    
    # --- Milestone Views (CBVs) ---
    # Create: Requires project_id to know where to attach the new milestone
    path('projects/<int:project_id>/milestones/new/', views.MilestoneCreateView.as_view(), name='milestone_create'),
    # Edit/Update: Requires pk (milestone ID)
    path('milestone/<int:pk>/edit/', views.MilestoneUpdateView.as_view(), name='milestone_edit'),
    # Delete: Requires pk (milestone ID)
    path('milestone/<int:pk>/delete/', views.MilestoneDeleteView.as_view(), name='milestone_delete'),
    path('milestone/<int:pk>/', views.MilestoneDetailView.as_view(), name='milestone_detail'),

    # --- Other Functional Views ---
    path('search/', views.search, name='search'),
    path('projects/<int:pk>/board/', views.project_board, name='project_board'),
    path('task/move/', views.task_move, name='task_move'),
    path('project/<int:id>/tasks-by-tag/<int:tag_id>/', views.tasks_by_tag, name='tasks_by_tag'),
    
    path('api/', include('projectapp.api_urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
