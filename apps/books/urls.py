from rest_framework.routers import DefaultRouter

from .views import BookViewSet, SubjectViewSet

router = DefaultRouter()
router.register("books", BookViewSet, basename="book")
router.register("subjects", SubjectViewSet, basename="subject")

urlpatterns = router.urls
