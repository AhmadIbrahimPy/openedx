from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, filters, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAdminUser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

from .models import Category, CourseCategory
from .serializers import (
    CategorySerializer, CourseListSerializer,
    CourseDetailSerializer, CourseCreateUpdateSerializer,
)


class StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class CategoryListView(generics.ListCreateAPIView):
    queryset = Category.objects.select_related('parent_category').filter(is_active=True)
    serializer_class = CategorySerializer
    authentication_classes = [OAuth2Authentication, SessionAuthentication]
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']


def _build_course_data(course, category_name=None):
    now = timezone.now()
    return {
        'course_id': str(course.id),
        'title': course.display_name,
        'category': category_name,
        'organization': course.org,
        'is_active': course.end is None or course.end > now,
        'start': course.start,
        'end': course.end,
        'enrollment_start': course.enrollment_start,
        'enrollment_end': course.enrollment_end,
        'course_image_url': course.course_image_url,
    }


def _build_course_detail(course, category_name=None):
    data = _build_course_data(course, category_name)
    data['short_description'] = getattr(course, 'short_description', None)
    data['effort'] = getattr(course, 'effort', None)
    data['language'] = getattr(course, 'language', None)
    return data


class CourseListView(generics.ListAPIView):
    """
    GET /api/categories/v1/courses/?category=programming&organization=MOHESR&search=python&is_active=true&page=1
    """
    serializer_class = CourseListSerializer
    authentication_classes = [OAuth2Authentication, SessionAuthentication]
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = StandardPagination

    def get_queryset(self):
        now = timezone.now()
        queryset = CourseOverview.objects.all()

        category_param = self.request.query_params.get('category')
        if category_param:
            matching_course_ids = CourseCategory.objects.filter(
                Q(category__slug__iexact=category_param) |
                Q(category__name__iexact=category_param) |
                Q(category__parent_category__slug__iexact=category_param) |
                Q(category__parent_category__name__iexact=category_param)
            ).values_list('course_id', flat=True)
            queryset = queryset.filter(id__in=matching_course_ids)

        organization = self.request.query_params.get('organization')
        if organization:
            queryset = queryset.filter(org__iexact=organization)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(display_name__icontains=search) | Q(id__icontains=search)
            )

        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            if is_active.lower() in ('true', '1'):
                queryset = queryset.filter(Q(end__isnull=True) | Q(end__gt=now))
            elif is_active.lower() in ('false', '0'):
                queryset = queryset.filter(end__lte=now)

        return queryset.order_by('-created')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        courses = page or queryset

        course_ids = [str(c.id) for c in courses]
        category_map = {}
        for cc in CourseCategory.objects.filter(course_id__in=course_ids).select_related('category'):
            category_map[cc.course_id] = cc.category.name

        results = [_build_course_data(c, category_map.get(str(c.id))) for c in courses]
        serializer = self.get_serializer(results, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class CourseDetailView(APIView):
    """
    GET    /api/categories/v1/courses/{course_id}/  — Retrieve course details
    PUT    /api/categories/v1/courses/{course_id}/  — Update course category assignment
    DELETE /api/categories/v1/courses/{course_id}/  — Remove course from category system
    """
    authentication_classes = [OAuth2Authentication, SessionAuthentication]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticatedOrReadOnly()]
        return [IsAdminUser()]

    def get(self, request, course_id):
        try:
            course = CourseOverview.objects.get(id=course_id)
        except CourseOverview.DoesNotExist:
            return Response(
                {'error': f"Course '{course_id}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        cc = CourseCategory.objects.filter(course_id=course_id).select_related('category').first()
        category_name = cc.category.name if cc else None
        data = _build_course_detail(course, category_name)
        serializer = CourseDetailSerializer(data)
        return Response(serializer.data)

    def put(self, request, course_id):
        serializer = CourseCreateUpdateSerializer(data={
            'course_id': course_id,
            'category_id': request.data.get('category_id'),
        })
        serializer.is_valid(raise_exception=True)

        category_id = serializer.validated_data.get('category_id')
        if category_id:
            CourseCategory.objects.update_or_create(
                course_id=course_id,
                defaults={'category_id': category_id},
            )
        else:
            CourseCategory.objects.filter(course_id=course_id).delete()

        course = CourseOverview.objects.get(id=course_id)
        cc = CourseCategory.objects.filter(course_id=course_id).select_related('category').first()
        category_name = cc.category.name if cc else None
        data = _build_course_detail(course, category_name)
        return Response(CourseDetailSerializer(data).data)

    def delete(self, request, course_id):
        deleted, _ = CourseCategory.objects.filter(course_id=course_id).delete()
        if not deleted:
            return Response(
                {'error': f"Course '{course_id}' has no category assignment."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class CourseCreateView(APIView):
    """
    POST /api/categories/v1/courses/  — Register a course with a category
    """
    authentication_classes = [OAuth2Authentication, SessionAuthentication]
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = CourseCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        course_id = serializer.validated_data['course_id']
        category_id = serializer.validated_data.get('category_id')

        if CourseCategory.objects.filter(course_id=course_id).exists():
            return Response(
                {'error': f"Course '{course_id}' is already assigned to a category."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if category_id:
            CourseCategory.objects.create(course_id=course_id, category_id=category_id)

        course = CourseOverview.objects.get(id=course_id)
        cc = CourseCategory.objects.filter(course_id=course_id).select_related('category').first()
        category_name = cc.category.name if cc else None
        data = _build_course_detail(course, category_name)
        return Response(CourseDetailSerializer(data).data, status=status.HTTP_201_CREATED)
