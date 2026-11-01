from rest_framework import serializers
from .models import Category, CourseCategory


class CategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'parent_category', 'is_active', 'created_at', 'subcategories']

    def get_subcategories(self, obj):
        children = obj.subcategories.filter(is_active=True)
        return CategorySerializer(children, many=True).data


class CourseListSerializer(serializers.Serializer):
    course_id = serializers.CharField()
    title = serializers.CharField()
    category = serializers.CharField(allow_null=True)
    organization = serializers.CharField()
    is_active = serializers.BooleanField()
    start = serializers.DateTimeField(allow_null=True)
    end = serializers.DateTimeField(allow_null=True)
    enrollment_start = serializers.DateTimeField(allow_null=True)
    enrollment_end = serializers.DateTimeField(allow_null=True)
    course_image_url = serializers.CharField()


class CourseDetailSerializer(serializers.Serializer):
    course_id = serializers.CharField()
    title = serializers.CharField()
    category = serializers.CharField(allow_null=True)
    organization = serializers.CharField()
    is_active = serializers.BooleanField()
    start = serializers.DateTimeField(allow_null=True)
    end = serializers.DateTimeField(allow_null=True)
    enrollment_start = serializers.DateTimeField(allow_null=True)
    enrollment_end = serializers.DateTimeField(allow_null=True)
    course_image_url = serializers.CharField()
    short_description = serializers.CharField(allow_null=True)
    effort = serializers.CharField(allow_null=True)
    language = serializers.CharField(allow_null=True)


class CourseCreateUpdateSerializer(serializers.Serializer):
    course_id = serializers.CharField(
        help_text="Open edX course ID, e.g. 'org+course+run'"
    )
    category_id = serializers.IntegerField(
        required=False, allow_null=True,
        help_text="Category ID to assign this course to"
    )

    def validate_course_id(self, value):
        from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
        if not CourseOverview.objects.filter(id=value).exists():
            raise serializers.ValidationError(
                f"Course '{value}' does not exist in Open edX."
            )
        return value

    def validate_category_id(self, value):
        if value is not None and not Category.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError(
                f"Category with id {value} does not exist or is inactive."
            )
        return value
