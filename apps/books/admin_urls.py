from rest_framework.routers import DefaultRouter

from .admin_views import AdminBookViewSet, AdminSubjectViewSet

router = DefaultRouter()
router.register("books", AdminBookViewSet, basename="admin-book")
router.register("subjects", AdminSubjectViewSet, basename="admin-subject")

urlpatterns = router.urls
