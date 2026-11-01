from django.apps import AppConfig

class CourseCategoriesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lms.djangoapps.course_categories'
    label = 'course_categories'

    def ready(self):
        from django.urls import include, path, get_resolver
        resolver = get_resolver()
        already = any('categories' in str(p.pattern) for p in resolver.url_patterns)
        if not already:
            resolver.url_patterns.append(
                path('api/categories/', include('lms.djangoapps.course_categories.urls'))
            )
