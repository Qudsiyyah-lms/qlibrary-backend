from rest_framework.routers import DefaultRouter

from .admin_views import AdminInviteViewSet, AdminManagementViewSet

router = DefaultRouter()
router.register("admins/invites", AdminInviteViewSet, basename="admin-invite")
router.register("admins", AdminManagementViewSet, basename="admin-user")

urlpatterns = router.urls
