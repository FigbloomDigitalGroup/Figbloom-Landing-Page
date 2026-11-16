from rest_framework.routers import SimpleRouter

from .views import ProjectAdminViewSet

# SimpleRouter for the same reason as in the activities app: careers.urls
# already mounts a DefaultRouter at /api/ and it owns the API root view.
router = SimpleRouter()
router.register('admin/projects', ProjectAdminViewSet, basename='admin-projects')

urlpatterns = router.urls
