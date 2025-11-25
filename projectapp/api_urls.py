from rest_framework.routers import DefaultRouter
from .api_views import ProjectViewSet, TaskViewSet, TagViewSet, MilestoneViewSet

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='api-projects')
router.register(r'tasks', TaskViewSet, basename='api-tasks')
router.register(r'tags', TagViewSet, basename='api-tags')
router.register(r'milestones', MilestoneViewSet, basename='api-milestones')

urlpatterns = router.urls
