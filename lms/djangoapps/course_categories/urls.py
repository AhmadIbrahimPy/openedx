from django.urls import path
from .views import CategoryListView, CourseListView, CourseDetailView, CourseCreateView

app_name = 'course_categories'

urlpatterns = [
    path('v1/', CategoryListView.as_view(), name='category-list'),
    path('v1/courses/', CourseListView.as_view(), name='course-list'),
    path('v1/courses/create/', CourseCreateView.as_view(), name='course-create'),
    path('v1/courses/<str:course_id>/', CourseDetailView.as_view(), name='course-detail'),
]
