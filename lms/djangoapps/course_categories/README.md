# Course Categories Management — Open edX Custom Application

A custom Django application for the Open edX platform that enables administrators to organize courses into hierarchical categories with full REST API support for filtering, searching, and CRUD operations.

---

## Table of Contents

1. [Installation & Setup](#installation--setup)
2. [Running Open edX](#running-open-edx)
3. [Running the Custom Application](#running-the-custom-application)
4. [Database Models](#database-models)
5. [REST API Documentation](#rest-api-documentation)
6. [Testing the APIs](#testing-the-apis)
7. [Database & Performance Optimization](#database--performance-optimization)
8. [Technical Questions](#technical-questions)

---

## Installation & Setup

### Prerequisites

- macOS / Linux
- Docker Desktop installed and running
- Python 3.8+
- At least 8 GB RAM allocated to Docker

### Step 1: Install Tutor

```bash
pip install "tutor[full]"
```

### Step 2: Launch Open edX

```bash
tutor local launch
```

This command will:
- Download the Open edX Docker images
- Configure MySQL, MongoDB, Redis, Caddy, and other services
- Run database migrations
- Create the required configuration files

### Step 3: Create an Admin Account

```bash
tutor local do createuser --staff --superuser admin admin@example.com
```

### Step 4: Access the Platform

| Service | URL |
|---------|-----|
| LMS | http://local.openedx.io |
| Studio | http://studio.local.openedx.io |
| Django Admin | http://local.openedx.io/admin |

### Installed Components & Services

| Service | Purpose |
|---------|---------|
| LMS | Learning Management System — student-facing |
| CMS (Studio) | Content Management — course authoring |
| MySQL | Primary relational database |
| MongoDB | Modulestore for course content |
| Redis | Caching and Celery message broker |
| Caddy | Reverse proxy and HTTPS |
| MFE | Micro-frontends (Learner Dashboard, etc.) |
| Meilisearch | Full-text search engine |
| SMTP | Email delivery (development) |

---

## Running Open edX

### Start all services

```bash
tutor local start -d
```

### Stop all services

```bash
tutor local stop
```

### View logs

```bash
docker logs tutor_local-lms-1 --tail 50 -f
```

### Check service status

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

---

## Running the Custom Application

This application follows Open edX's recommended extension pattern — **no core files are modified**. Integration is handled through:

1. **`plugin_app` in `apps.py`**: Automatically registers URL routes via Open edX's plugin system.
2. **Tutor plugin**: Adds the app to `INSTALLED_APPS` without editing `common.py`.

### Step 1: Install the Tutor Plugin

Create the plugin file at `$(tutor plugins printroot)/course_categories.py`:

```python
from tutor import hooks

hooks.Filters.ENV_PATCHES.add_item(
    ("openedx-lms-common-settings", "INSTALLED_APPS.append('lms.djangoapps.course_categories')")
)
```

Enable the plugin:

```bash
tutor plugins enable course_categories
```

### Step 2: Deploy the App into the Container

```bash
# Copy the app files
docker cp lms/djangoapps/course_categories tutor_local-lms-1:/openedx/edx-platform/lms/djangoapps/course_categories

# Fix file permissions
docker exec --user root tutor_local-lms-1 chmod -R 777 /openedx/edx-platform/lms/djangoapps/course_categories/
```

### Step 3: Run Migrations

```bash
docker exec tutor_local-lms-1 python manage.py lms makemigrations course_categories
docker exec tutor_local-lms-1 python manage.py lms migrate course_categories
```

### Step 4: Restart LMS

```bash
docker restart tutor_local-lms-1
```

### How URL Registration Works

The app's `apps.py` uses Open edX's `PluginURLs` mechanism:

```python
plugin_app = {
    PluginURLs.CONFIG: {
        ProjectType.LMS: {
            PluginURLs.NAMESPACE: 'course_categories',
            PluginURLs.REGEX: '^api/categories/',
            PluginURLs.RELATIVE_PATH: 'urls',
        }
    },
}
```

This automatically mounts all URL patterns under `/api/categories/` when the app is loaded — no changes to `lms/urls.py` required.

### After editing files

| Changed file | Commands |
|---|---|
| views.py / serializers.py | `docker cp` the file — auto-reloads |
| urls.py | `docker cp` + `docker restart tutor_local-lms-1` |
| models.py | `docker cp` + `makemigrations` + `migrate` + `restart` |
| admin.py | `docker cp` + `docker restart tutor_local-lms-1` |

---

## Database Models

### Category

| Field | Type | Description |
|-------|------|-------------|
| id | Integer (PK) | Auto-generated |
| name | CharField(255) | Unique category name |
| slug | SlugField(255) | URL-friendly unique identifier |
| description | TextField | Optional description |
| parent_category | ForeignKey(self) | Optional parent for subcategories |
| is_active | BooleanField | Default True |
| created_at | DateTimeField | Auto-set on creation |

### CourseCategory

| Field | Type | Description |
|-------|------|-------------|
| id | Integer (PK) | Auto-generated |
| course_id | CharField(255) | Open edX course identifier (unique) |
| category | ForeignKey(Category) | Assigned category |
| created_at | DateTimeField | Auto-set on creation |

### Entity Relationship

```
Category (1) ──── (N) CourseCategory (1) ──── (1) CourseOverview
    │
    └── parent_category (self-referencing FK for subcategories)
```

Example hierarchy:

```
Information Technology
├── Programming
├── Cybersecurity
└── Artificial Intelligence
Business Administration
├── Management
└── Accounting
Engineering
├── Computer Engineering
└── Electrical Engineering
```

---

## REST API Documentation

Base URL: `http://local.openedx.io/api/categories`

### 1. Categories

#### GET /api/categories/v1/
List all active categories with subcategories.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| search | string | Search by name or description |

**Response (200):**
```json
{
  "count": 3,
  "results": [
    {
      "id": 1,
      "name": "Information Technology",
      "slug": "information-technology",
      "description": "IT courses",
      "parent_category": null,
      "is_active": true,
      "created_at": "2026-10-31T20:44:49Z",
      "subcategories": [
        {
          "id": 4,
          "name": "Programming",
          "slug": "programming",
          "description": "",
          "parent_category": 1,
          "is_active": true,
          "created_at": "2026-10-31T20:45:00Z",
          "subcategories": []
        }
      ]
    }
  ]
}
```

#### POST /api/categories/v1/
Create a new category. Requires authentication.

**Request Body:**
```json
{
  "name": "Data Science",
  "slug": "data-science",
  "description": "Data Science courses",
  "parent_category": 1,
  "is_active": true
}
```

---

### 2. Courses — List & Filter

#### GET /api/categories/v1/courses/
List courses from Open edX with filtering, search, and pagination.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| category | string | Filter by category name or slug (includes subcategories) |
| organization | string | Filter by organization |
| search | string | Search in course title or course ID |
| is_active | boolean | `true` for active, `false` for ended courses |
| page | integer | Page number (default: 1) |
| page_size | integer | Results per page (default: 10, max: 100) |

**Example:**
```
GET /api/categories/v1/courses/?category=programming&organization=MOHESR&search=python&is_active=true&page=1
```

**Response (200):**
```json
{
  "count": 25,
  "next": "http://local.openedx.io/api/categories/v1/courses/?page=2",
  "previous": null,
  "results": [
    {
      "course_id": "course-v1:MOHESR+IT101+2026",
      "title": "Introduction to Python",
      "category": "Programming",
      "organization": "MOHESR",
      "is_active": true,
      "start": "2026-01-01T00:00:00Z",
      "end": null,
      "enrollment_start": "2025-12-01T00:00:00Z",
      "enrollment_end": null,
      "course_image_url": "/asset-v1:MOHESR+IT101+2026+type@asset+block@images_course_image.jpg"
    }
  ]
}
```

---

### 3. Courses — CRUD

#### GET /api/categories/v1/courses/{course_id}/
Retrieve detailed information about a specific course.

**Response (200):**
```json
{
  "course_id": "course-v1:MOHESR+IT101+2026",
  "title": "Introduction to Python",
  "category": "Programming",
  "organization": "MOHESR",
  "is_active": true,
  "start": "2026-01-01T00:00:00Z",
  "end": null,
  "enrollment_start": null,
  "enrollment_end": null,
  "course_image_url": "/asset-v1:...",
  "short_description": "Learn Python basics",
  "effort": "5 hours/week",
  "language": "en"
}
```

**Response (404):**
```json
{"error": "Course 'course-v1:X+Y+Z' not found."}
```

#### POST /api/categories/v1/courses/create/
Register an Open edX course with a category. **Requires admin authentication.**

**Request Body:**
```json
{
  "course_id": "course-v1:MOHESR+IT101+2026",
  "category_id": 4
}
```

**Response (201):** Full course detail object.

**Response (400):**
```json
{"error": "Course 'course-v1:MOHESR+IT101+2026' is already assigned to a category."}
```

**Validation errors:**
```json
{"course_id": ["Course 'X' does not exist in Open edX."]}
{"category_id": ["Category with id 99 does not exist or is inactive."]}
```

#### PUT /api/categories/v1/courses/{course_id}/
Update a course's category assignment. **Requires admin authentication.**

**Request Body:**
```json
{
  "category_id": 5
}
```

**Response (200):** Updated course detail object.

Pass `"category_id": null` to remove the category assignment.

#### DELETE /api/categories/v1/courses/{course_id}/
Remove a course from the category system. **Requires admin authentication.**

**Response (204):** No content.

**Response (404):**
```json
{"error": "Course 'course-v1:X+Y+Z' has no category assignment."}
```

---

### Authentication

- **GET** endpoints: Public (read-only, no authentication required)
- **POST/PUT/DELETE** endpoints: Require admin authentication
- Use session auth (browser) or pass credentials via HTTP Basic Auth or OAuth2 token

**Example with curl:**
```bash
# Login and get session cookie
curl -c cookies.txt -X POST http://local.openedx.io/login_ajax \
  -d '{"email":"admin@example.com","password":"yourpassword"}' \
  -H "Content-Type: application/json"

# Use session cookie for admin endpoints
curl -b cookies.txt -X POST http://local.openedx.io/api/categories/v1/courses/create/ \
  -d '{"course_id":"course-v1:org+course+run","category_id":1}' \
  -H "Content-Type: application/json"
```

---

## Testing the APIs

### Using curl

```bash
# List categories
curl http://local.openedx.io/api/categories/v1/

# List courses with filters
curl "http://local.openedx.io/api/categories/v1/courses/?category=programming&page=1"

# Search courses
curl "http://local.openedx.io/api/categories/v1/courses/?search=python&organization=MOHESR"

# Get course detail
curl "http://local.openedx.io/api/categories/v1/courses/course-v1:MOHESR+IT101+2026/"

# Combine filters
curl "http://local.openedx.io/api/categories/v1/courses/?category=programming&organization=MOHESR&search=python&is_active=true&page=1&page_size=10"
```

### Using the browser

Navigate to any GET endpoint in the browser. Django REST Framework provides a browsable HTML interface:

- http://local.openedx.io/api/categories/v1/
- http://local.openedx.io/api/categories/v1/courses/

### Using Django Admin

Access http://local.openedx.io/admin to:
- Manage categories (create, edit, delete)
- Assign courses to categories
- View all course-category relationships

---

## Database & Performance Optimization

### Query Optimization

1. **`select_related()`** is used for single-valued relationships (ForeignKey):
   - `Category.objects.select_related('parent_category')` — avoids N+1 when loading parent categories
   - `CourseCategory.objects.select_related('category')` — joins category in a single query

2. **Batch loading** in `CourseListView.list()`:
   - Instead of querying the category for each course individually (N+1 problem), all category mappings are fetched in one query using `filter(course_id__in=course_ids)` and built into a dictionary for O(1) lookups.

3. **Database indexes**:
   - `Category.name` — unique index
   - `Category.slug` — unique index
   - `CourseCategory.course_id` — unique index
   - `CourseOverview.id` — primary key index
   - `CourseOverview.org` — used for organization filtering

### Scalability for Thousands of Courses

1. **Pagination**: All list endpoints use `PageNumberPagination` (default 10, max 100 per page), so even with 100K+ courses, each request processes a bounded number of rows.

2. **Indexed filtering**: All filter fields (`org`, `display_name`, category `slug`/`name`) are indexed, so queries use index scans, not full table scans.

3. **Efficient joins**: `CourseCategory` uses a simple FK to `Category`, and `course_id` is indexed. The join between `CourseCategory` and `CourseOverview` uses `id__in` with a subquery, which MySQL optimizes well.

4. **Lazy QuerySets**: Django QuerySets are lazy — filters are chained in Python but executed as a single SQL query only when data is needed. Multiple filters in one request translate to one SQL query with multiple WHERE clauses.

5. **Minimal data transfer**: The serializers return only the fields needed for listing. The detail endpoint adds a few more fields but never loads the full course content from MongoDB.

---

## Technical Questions

### 1. Explain the difference between Open edX LMS and Studio.

**LMS (Learning Management System)** is the student-facing application. Students use it to browse courses, enroll, view content, watch videos, complete assignments, take exams, and track their progress. It serves the learner dashboard and handles all enrollment and grading logic.

**Studio (CMS)** is the instructor/author-facing application. Course teams use it to create and organize course content — adding sections, subsections, units, videos, problems, and other XBlocks. Studio provides a visual editor and handles course publishing workflows. Once content is published in Studio, it becomes available in LMS.

In short: Studio is where courses are built; LMS is where courses are taken.

### 2. What is Tutor, and what role does it play in Open edX deployment?

Tutor is the official, community-supported deployment tool for Open edX. It replaces the older native installation and Ansible-based provisioning methods. Tutor uses Docker containers to package and run all Open edX services (LMS, CMS, MySQL, MongoDB, Redis, Caddy, Celery workers, etc.) in an isolated and reproducible environment.

Key roles:
- **Simplified installation**: A single `tutor local launch` command sets up the entire platform.
- **Configuration management**: Tutor generates and manages all configuration files.
- **Plugin system**: Extends Open edX without modifying core code — plugins can add Django apps, modify settings, add Docker services, and inject custom templates.
- **Development mode**: `tutor dev` provides hot-reloading and debugging support.
- **Upgrades**: Tutor versions map to Open edX releases, making upgrades straightforward.

### 3. Explain how Open edX handles course structures and course identifiers.

Open edX uses a hierarchical course structure:
- **Course** → **Sections** (chapters) → **Subsections** (sequentials) → **Units** (verticals) → **Components** (XBlocks: videos, problems, text, etc.)

Course identifiers follow a specific format:
- **Legacy format**: `org/course/run` (e.g., `MOHESR/IT101/2026`)
- **Current format**: `course-v1:org+course+run` (e.g., `course-v1:MOHESR+IT101+2026`)

These are represented in code as `CourseKey` objects (from the `opaque-keys` library). The course content is stored in MongoDB via the **Modulestore**, while course metadata (display name, start/end dates, enrollment info) is cached in the `CourseOverview` model in MySQL for efficient querying.

### 4. What is the difference between a Django application and an Open edX XBlock?

A **Django application** is a standard Django app that can include models, views, URL routes, admin panels, REST APIs, middleware, management commands, and templates. It operates at the platform level and has full access to the Django ORM and all Open edX services. Example: the `course_categories` app in this project.

An **XBlock** is Open edX's component-based plugin architecture for course content. XBlocks are rendered inside the courseware and represent individual learning components — a video player, a multiple-choice problem, a discussion forum, a simulation, etc. Each XBlock manages its own rendering (student view, studio view), stores its own state per student, and defines its own editing interface. XBlocks are reusable across courses and can be published as standalone Python packages.

Key difference: Django apps extend the platform's functionality (APIs, admin, workflows); XBlocks extend the course content types available to authors.

### 5. How can you extend Open edX without modifying its core code?

Open edX provides several extension mechanisms:

1. **Tutor plugins**: Add Django apps, modify settings, inject templates, add Docker services, and customize configuration — all without touching core code. In this project, we use a Tutor plugin to add `course_categories` to `INSTALLED_APPS`.
2. **`plugin_app` in AppConfig**: Open edX's `PluginURLs` system allows Django apps to register their own URL routes automatically via `apps.py`, without editing `lms/urls.py`. This is how our app mounts its API at `/api/categories/`.
3. **XBlocks**: Create custom course components installable via pip.
4. **Open edX Filters and Events**: The platform emits events (via `openedx-events`) and supports pipeline filters (via `openedx-filters`) that allow external code to hook into and modify platform behavior at defined extension points.
5. **Django signals**: Listen to platform signals (enrollment, grading, user creation) and execute custom logic.
6. **Theming**: Custom themes for LMS and Studio branding without modifying templates.
7. **MFE (Micro-Frontend) customization**: Override or extend React-based frontends.

### 6. Explain how Django REST Framework can be used to build custom APIs.

Django REST Framework (DRF) provides the building blocks for REST APIs in Django:

- **Serializers**: Define how data is converted between Python objects and JSON. `ModelSerializer` auto-generates fields from Django models. Custom serializers validate input data.
- **Views**: `APIView` for full control, `GenericAPIView` with mixins, or `ViewSets` for CRUD with minimal code. Views handle HTTP methods and return `Response` objects.
- **Routers**: Automatically generate URL patterns for ViewSets.
- **Authentication**: Built-in support for session, token, JWT, and OAuth2 authentication.
- **Permissions**: Classes like `IsAuthenticated`, `IsAdminUser`, or custom permissions control access.
- **Filtering & Search**: `DjangoFilterBackend` and `SearchFilter` enable query parameter-based filtering.
- **Pagination**: `PageNumberPagination` or `CursorPagination` for handling large result sets.
- **Throttling**: Rate-limiting to protect APIs.

In this project, DRF is used for all endpoints — serializers validate course IDs and category assignments, views handle filtering logic, and pagination ensures scalable responses.

### 7. What is the purpose of Celery and Redis in Open edX?

**Celery** is a distributed task queue used for asynchronous and background processing. In Open edX, it handles tasks that are too slow for a synchronous HTTP request:
- Grading calculations and certificate generation
- Bulk email sending to enrolled students
- Course content export/import
- Search index updates
- Generating reports (grade reports, student activity)
- Course re-publishing and cache invalidation

**Redis** serves two roles:
1. **Message broker**: Passes task messages from the web application to Celery workers. When LMS queues a task (e.g., "generate certificate for student X"), Redis holds the message until a worker picks it up.
2. **Cache backend**: Stores frequently accessed data (course metadata, user sessions, configuration values) in memory for fast retrieval, reducing database load.

### 8. How would you troubleshoot an Open edX service returning HTTP 500?

Step-by-step approach:

1. **Check logs**: `docker logs tutor_local-lms-1 --tail 100` — the traceback reveals the exact error and file/line.
2. **Identify the error type**: ImportError (missing module), DatabaseError (migration issue), PermissionError, or application logic error.
3. **Check service health**: `docker ps` — ensure MySQL, Redis, MongoDB are running and not restarting.
4. **Check recent changes**: `git log` and `git diff` — did a recent change introduce the error?
5. **Reproduce locally**: Hit the same endpoint with `curl -v` to see full request/response headers.
6. **Check Django settings**: Verify `INSTALLED_APPS`, database configuration, and environment variables.
7. **Database state**: Run `python manage.py lms migrate --check` to see if migrations are pending.
8. **Resource issues**: Check disk space, memory usage (`docker stats`), and database connections.
9. **Django shell**: `docker exec tutor_local-lms-1 python manage.py lms shell` — import the failing module interactively to isolate the error.

### 9. How would you maintain compatibility with future Open edX releases?

1. **Use official extension points**: Tutor plugins, Open edX Events, Open edX Filters, and XBlocks rather than patching core code. These APIs are versioned and maintained.
2. **Avoid modifying core files**: Never edit `lms/envs/common.py`, `lms/urls.py`, or other core files directly. Use Tutor plugin hooks to inject settings and URL patterns.
3. **Pin to stable APIs**: Use `CourseOverview` and other public models rather than internal Modulestore APIs that may change.
4. **Follow deprecation warnings**: Open edX logs deprecation warnings — monitor and migrate before features are removed.
5. **Track Named Releases**: Each Open edX release (Quince, Redwood, Sumac) has release notes with breaking changes. Review them before upgrading.
6. **Write tests**: Automated tests catch regressions when upgrading. Test against the course data models and API contracts.
7. **Use semantic versioning**: If the custom app is packaged separately, follow semver and declare compatible Open edX versions.
8. **Engage with the community**: Follow Open edX forums, attend contributor meetings, and review the DEPR (deprecation) process for advance notice of changes.
