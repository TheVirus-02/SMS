# AGENTS.md - AI Coding Assistant Guidelines

## Project Overview
This is a Django 6.0.3-based Student Management System for tracking students, trainers, batches, attendance, payments, and center logistics. The system manages educational center operations with features for student enrollment, fee tracking via installments, daily attendance marking, trainer scheduling, and PC inventory per center.

## Architecture
- **Framework**: Django 6.0.3 with single app `student`
- **Database**: SQLite for development (via `db.sqlite3`), PostgreSQL for production (configured via `DATABASE_URL`)
- **Deployment**: Render with gunicorn, static files served via whitenoise
- **Templates**: Located in `BASE_DIR/templates/`, extends `base.html`
- **Static Files**: `static/` for development, `staticfiles/` for production
- **Environment**: Configured via `.env` or `sms.env` files loaded in `settings.py`

## Key Models & Relationships
- **Student**: Core entity with auto-generated `student_id` ("MTX-" + 6 hex chars), tracks fees, payments, status
- **Trainer**: Assigned to students, has schedules and courses
- **Batch**: Time-based groups (displayed as "1 PM" format)
- **Center**: Physical locations with logistics (PC counts)
- **Course**: Many-to-many with students via `StudentCourse` (tracks completion)
- **Attendance**: Daily status per student (present/absent/leave)
- **Installment**: Payment tracking with modes (cash/upi/card/bank_transfer)
- **TrainerSchedule**: Links trainer-center-batch with time slots

## Critical Patterns
- **Student ID Generation**: `uuid.uuid4().hex[:6].upper()` prefixed with "MTX-"
- **Payment Calculation**: Properties like `total_paid` (paid_fee + installment sum), `remaining_fee`, `payment_status` ("Paid"/"Pending"/"Partial")
- **Attendance Uniqueness**: One record per student per date
- **Installment Auto-numbering**: Increments per student
- **Logistics Validation**: `repair_pc` cannot exceed `total_pc`
- **Course Completion**: Auto-sets `completion_date` when marked complete
- **Batch Time Display**: `time.strftime("%I %p").lstrip("0")` (e.g., "1 PM")

## Development Workflow
- **Run Server**: `python manage.py runserver` (loads env from `sms.env`)
- **Migrations**: `python manage.py makemigrations && python manage.py migrate`
- **Collect Static**: `python manage.py collectstatic --no-input` (for production)
- **Database Setup**: Defaults to SQLite, override with `DATABASE_URL` for PostgreSQL
- **Debug Mode**: Controlled by `DEBUG` env var (False in production)

## Common Tasks
- **Add Student**: Use `student_registration` view, sets courses via many-to-many
- **Mark Attendance**: Per trainer/batch via `mark_attendance`, updates or creates daily records
- **Track Payments**: Add installments via `add_installment`, auto-increments numbers
- **Manage Trainers**: CRUD operations with course assignments
- **Update Logistics**: AJAX endpoints for PC counts (`update_total_pc`, `update_repair_pc`)
- **Filter Records**: Complex queries in `record` view with payment status calculations

## Code Conventions
- **Imports**: Standard Django + custom `templatetags.dict_extras`
- **Queries**: Use `select_related`/`prefetch_related` for optimization (e.g., `Student.objects.select_related('trainer', 'batch', 'center')`)
- **Validation**: Model-level `save()` methods for auto-fields and constraints
- **Templates**: Inline styles in `base.html`, block structure for content
- **URLs**: RESTful patterns like `student/<int:id>/`, `trainer/<int:id>/`
- **AJAX**: JSON responses for logistics updates
- **Calendar**: Monthly attendance view using `calendar` module

## Deployment Notes
- **Render Config**: `render.yaml` sets up web service + PostgreSQL database
- **Environment Vars**: `SECRET_KEY` generated, `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` set for domain
- **Build**: `pip install -r requirements.txt && python manage.py collectstatic --no-input`
- **Start**: `python manage.py migrate --noinput && gunicorn Theone.wsgi:application --bind 0.0.0.0:$PORT`</content>
<parameter name="filePath">C:\Users\Administrator\PycharmProjects\TheLastProject\AGENTS.md
