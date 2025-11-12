from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.main, name='home_page'), ###
    path('projects/new/', views.project_create, name='project_create'),
    path('project_list/', views.project_list, name='project_list'),
    path('search/', views.search, name='search'),
    path('projects/<int:id>/board/', views.project_board, name='project_board'),
    path('project/<int:id>/', views.project_detail, name='project_detail'),    


    
    path('project/<int:id>/edit/', views.project_edit, name='project_edit'),
    path('project/<int:id>/delete/', views.project_delete, name='project_delete'),
       
    
    path('task/move/', views.task_move, name='task_move'),    
    path('projects/<int:project_id>/tasks/new/', views.task_create, name='task_create'), #####
    path('task/<int:id>/', views.task_detail, name='task_detail'),
    path('task/<int:task_id>/edit/', views.task_edit, name='task_edit'),
    path('task/<int:id>/delete/', views.task_delete, name='task_delete'),

    path('register/', views.register, name='register'), 
    path('login/', auth_views.LoginView.as_view(template_name='projectapp/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('hint/', views.hint, name='hint'),

    path('project/<int:id>/tasks-by-tag/<int:tag_id>/', views.tasks_by_tag, name='tasks_by_tag'),
]
