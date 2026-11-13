from rest_framework.routers import SimpleRouter

from .views import ActivityAdminViewSet

# SimpleRouter, not DefaultRouter: careers.urls already mounts a DefaultRouter
# at the same /api/ prefix, and two of them would both claim the API root view.
router = SimpleRouter()
router.register('admin/activities', ActivityAdminViewSet, basename='admin-activities')

urlpatterns = router.urls
