from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from student.models import Batch, Center, Course, Student, Trainer, TrainerSchedule
from student.portal import ROLE_ADMIN, ROLE_TRAINER, get_portal_role, get_trainer_for_user_or_404, role_required


User = get_user_model()


@role_required(ROLE_ADMIN)
def trainer_list(request):
    query = request.GET.get("q", "").strip()
    trainers = Trainer.objects.prefetch_related("courses").select_related("user").annotate(
        student_count=Count("student", distinct=True),
        schedule_count=Count("trainerschedule", distinct=True),
    ).order_by("name")
    if query:
        trainers = trainers.filter(
            Q(name__icontains=query) |
            Q(mobile__icontains=query) |
            Q(courses__name__icontains=query) |
            Q(user__username__icontains=query)
        ).distinct()

    return render(
        request,
        "trainer/trainer_list.html",
        {
            "trainers": trainers,
            "query": query,
            "total_trainers": trainers.count(),
        },
    )


@role_required(ROLE_ADMIN, ROLE_TRAINER)
def trainer_detail(request, id):
    if get_portal_role(request.user) == ROLE_TRAINER:
        trainer = get_trainer_for_user_or_404(request.user, id, Trainer.objects.prefetch_related("courses").select_related("user"))
    else:
        trainer = get_object_or_404(Trainer.objects.prefetch_related("courses").select_related("user"), id=id)
    schedules = TrainerSchedule.objects.select_related("center", "batch").filter(trainer=trainer)
    assigned_students = Student.objects.filter(trainer=trainer).select_related("batch", "center").order_by("name")
    return render(
        request,
        "trainer/trainer_detail.html",
        {
            "trainer": trainer,
            "schedules": schedules,
            "assigned_students": assigned_students,
            "student_count": assigned_students.count(),
        },
    )


@role_required(ROLE_ADMIN)
def add_trainer(request):
    courses = Course.objects.all().order_by("name")
    if request.method == "POST":
        error = validate_trainer_form(request)
        if error:
            return render(
                request,
                "trainer/add_trainer.html",
                {
                    "courses": courses,
                    "users": available_portal_users(),
                    "error": [error],
                    "form_data": trainer_form_data_from_request(request),
                },
            )
        user = resolve_portal_user(request)
        trainer = Trainer.objects.create(
            name=request.POST.get("name"),
            age=request.POST.get("age") or None,
            dob=request.POST.get("dob") or None,
            mobile=request.POST.get("mobile"),
            joining_date=request.POST.get("joining_date") or None,
            record_scope=request.POST.get("record_scope") or Trainer.RECORD_SCOPE_ASSIGNED,
            can_access_student_registration=request.POST.get("can_access_student_registration") == "on",
            can_access_student_records=request.POST.get("can_access_student_records") == "on",
            can_edit_students=request.POST.get("can_edit_students") == "on",
            can_manage_fees=request.POST.get("can_manage_fees") == "on",
            can_access_enquiries=request.POST.get("can_access_enquiries") == "on",
            can_convert_enquiries=request.POST.get("can_convert_enquiries") == "on",
            can_manage_batches=request.POST.get("can_manage_batches") == "on",
            can_access_attendance=request.POST.get("can_access_attendance") == "on",
            can_access_logistics=request.POST.get("can_access_logistics") == "on",
            can_view_reports=request.POST.get("can_view_reports") == "on",
            can_view_exams=request.POST.get("can_view_exams") == "on",
            user=user,
        )
        trainer.courses.set(request.POST.getlist("courses"))
        messages.success(request, f"{trainer.name} added successfully.")
        return redirect("trainer_detail", id=trainer.id)
    return render(
        request,
        "trainer/add_trainer.html",
        {"courses": courses, "users": available_portal_users(), "form_data": {"selected_course_ids": []}},
    )


@role_required(ROLE_ADMIN)
def update_trainer(request, id):
    trainer = get_object_or_404(Trainer, id=id)
    courses = Course.objects.all().order_by("name")
    if request.method == "POST":
        error = validate_trainer_form(request, current_user=trainer.user)
        if error:
            return render(
                request,
                "trainer/update_trainer.html",
                {
                    "trainer": trainer,
                    "courses": courses,
                    "users": available_portal_users(trainer.user_id),
                    "error": [error],
                    "form_data": trainer_form_data_from_request(request),
                },
            )
        trainer.name = request.POST.get("name")
        trainer.age = request.POST.get("age") or None
        trainer.dob = request.POST.get("dob") or None
        trainer.mobile = request.POST.get("mobile")
        trainer.joining_date = request.POST.get("joining_date") or None
        trainer.record_scope = request.POST.get("record_scope") or Trainer.RECORD_SCOPE_ASSIGNED
        trainer.can_access_student_registration = request.POST.get("can_access_student_registration") == "on"
        trainer.can_access_student_records = request.POST.get("can_access_student_records") == "on"
        trainer.can_edit_students = request.POST.get("can_edit_students") == "on"
        trainer.can_manage_fees = request.POST.get("can_manage_fees") == "on"
        trainer.can_access_enquiries = request.POST.get("can_access_enquiries") == "on"
        trainer.can_convert_enquiries = request.POST.get("can_convert_enquiries") == "on"
        trainer.can_manage_batches = request.POST.get("can_manage_batches") == "on"
        trainer.can_access_attendance = request.POST.get("can_access_attendance") == "on"
        trainer.can_access_logistics = request.POST.get("can_access_logistics") == "on"
        trainer.can_view_reports = request.POST.get("can_view_reports") == "on"
        trainer.can_view_exams = request.POST.get("can_view_exams") == "on"
        trainer.user = resolve_portal_user(request, current_user=trainer.user)
        trainer.save()
        trainer.courses.set(request.POST.getlist("courses"))
        messages.success(request, f"{trainer.name} updated successfully.")
        return redirect("trainer_detail", id=trainer.id)
    return render(
        request,
        "trainer/update_trainer.html",
        {
            "trainer": trainer,
            "courses": courses,
            "users": available_portal_users(trainer.user_id),
            "form_data": {
                "login_username": trainer.user.username if trainer.user_id else "",
                "login_password": "",
                "record_scope": trainer.record_scope,
                "can_access_student_registration": trainer.can_access_student_registration,
                "can_access_student_records": trainer.can_access_student_records,
                "can_edit_students": trainer.can_edit_students,
                "can_manage_fees": trainer.can_manage_fees,
                "can_access_enquiries": trainer.can_access_enquiries,
                "can_convert_enquiries": trainer.can_convert_enquiries,
                "can_manage_batches": trainer.can_manage_batches,
                "can_access_attendance": trainer.can_access_attendance,
                "can_access_logistics": trainer.can_access_logistics,
                "can_view_reports": trainer.can_view_reports,
                "can_view_exams": trainer.can_view_exams,
                "selected_course_ids": [str(course_id) for course_id in trainer.courses.values_list("id", flat=True)],
            },
        },
    )


@role_required(ROLE_ADMIN)
@require_POST
def delete_trainer(request, id):
    trainer = get_object_or_404(Trainer, id=id)
    trainer_name = trainer.name
    trainer.delete()
    messages.success(request, f"{trainer_name} deleted successfully.")
    return redirect("trainer_list")


@role_required(ROLE_ADMIN)
def trainer_schedule_page(request):
    trainer_id = request.GET.get("trainer", "").strip()
    schedules = TrainerSchedule.objects.select_related("trainer", "center", "batch").order_by(
        "batch__time", "trainer__name", "center__name"
    )
    if trainer_id:
        schedules = schedules.filter(trainer_id=trainer_id)

    all_batches = list(Batch.objects.all().order_by("time"))
    all_centers = list(Center.objects.all().order_by("name"))
    assigned_pairs = set(TrainerSchedule.objects.values_list("batch_id", "center_id"))
    uncovered_slots = []
    for batch in all_batches:
        missing_centers = [center for center in all_centers if (batch.id, center.id) not in assigned_pairs]
        if missing_centers:
            uncovered_slots.append(
                {
                    "batch": batch,
                    "missing_centers": missing_centers,
                    "missing_count": len(missing_centers),
                }
            )

    return render(
        request,
        "trainer/schedule_list.html",
        {
            "schedules": schedules,
            "trainers": Trainer.objects.all().order_by("name"),
            "centers": Center.objects.all().order_by("name"),
            "batches": Batch.objects.all().order_by("time"),
            "selected_trainer_id": trainer_id,
            "uncovered_slots": uncovered_slots,
        },
    )


@role_required(ROLE_ADMIN)
def add_schedule(request, trainer_id=None):
    initial_trainer = get_object_or_404(Trainer, id=trainer_id) if trainer_id else None
    trainers = Trainer.objects.all().order_by("name")
    centers = Center.objects.all().order_by("name")
    batches = Batch.objects.all().order_by("time")

    if request.method == "POST":
        selected_trainer = get_object_or_404(Trainer, id=request.POST.get("trainer"))
        start_batch_id = request.POST.get("start_batch")
        end_batch_id = request.POST.get("end_batch")
        center_id = request.POST.get("center") or None

        try:
            created_count = create_bulk_trainer_schedule(
                trainer=selected_trainer,
                start_batch_id=start_batch_id,
                end_batch_id=end_batch_id,
                center_id=center_id,
            )
        except ValidationError as exc:
            return render(
                request,
                "trainer/add_schedule.html",
                {
                    "trainer": initial_trainer,
                    "selected_trainer_id": request.POST.get("trainer", ""),
                    "selected_center_id": center_id or "",
                    "selected_start_batch_id": start_batch_id or "",
                    "selected_end_batch_id": end_batch_id or "",
                    "trainers": trainers,
                    "centers": centers,
                    "batches": batches,
                    "error": exc.messages,
                },
            )

        messages.success(request, f"{created_count} schedule slot(s) added successfully.")
        return redirect("trainer_schedule_page")

    return render(
        request,
        "trainer/add_schedule.html",
        {
            "trainer": initial_trainer,
            "selected_trainer_id": str(initial_trainer.id) if initial_trainer else "",
            "selected_center_id": "",
            "selected_start_batch_id": "",
            "selected_end_batch_id": "",
            "trainers": trainers,
            "centers": centers,
            "batches": batches,
        },
    )


@role_required(ROLE_ADMIN)
def update_schedule(request, id):
    schedule = get_object_or_404(TrainerSchedule.objects.select_related("trainer", "center", "batch"), id=id)
    trainers = Trainer.objects.all().order_by("name")
    centers = Center.objects.all().order_by("name")
    batches = Batch.objects.all().order_by("time")

    if request.method == "POST":
        schedule.trainer_id = request.POST.get("trainer")
        schedule.center_id = request.POST.get("center")
        schedule.batch_id = request.POST.get("batch")
        try:
            schedule.save()
        except ValidationError as exc:
            return render(
                request,
                "trainer/update_schedule.html",
                {
                    "schedule": schedule,
                    "trainers": trainers,
                    "centers": centers,
                    "batches": batches,
                    "error": exc.messages,
                },
            )
        messages.success(request, "Schedule updated successfully.")
        return redirect("trainer_schedule_page")

    return render(
        request,
        "trainer/update_schedule.html",
        {"schedule": schedule, "trainers": trainers, "centers": centers, "batches": batches},
    )


@role_required(ROLE_ADMIN)
@require_POST
def delete_schedule(request, id):
    schedule = get_object_or_404(TrainerSchedule.objects.select_related("trainer"), id=id)
    messages.success(request, "Schedule deleted successfully.")
    schedule.delete()
    return redirect("trainer_schedule_page")


def create_bulk_trainer_schedule(trainer, start_batch_id, end_batch_id, center_id=None):
    if not start_batch_id or not end_batch_id:
        raise ValidationError("Select both start batch and end batch.")

    batch_map = {batch.id: batch for batch in Batch.objects.all().order_by("time")}
    try:
        start_batch_id = int(start_batch_id)
        end_batch_id = int(end_batch_id)
    except (TypeError, ValueError):
        raise ValidationError("Invalid batch range selected.")

    start_batch = batch_map.get(start_batch_id)
    end_batch = batch_map.get(end_batch_id)
    if not start_batch or not end_batch:
        raise ValidationError("Selected batch range is not available.")

    ordered_batches = list(batch_map.values())
    start_index = next((index for index, batch in enumerate(ordered_batches) if batch.id == start_batch.id), None)
    end_index = next((index for index, batch in enumerate(ordered_batches) if batch.id == end_batch.id), None)
    if start_index is None or end_index is None or start_index > end_index:
        raise ValidationError("End batch must be after start batch.")

    created_count = 0
    for batch in ordered_batches[start_index:end_index + 1]:
        schedule = TrainerSchedule(trainer=trainer, batch=batch, center_id=center_id)
        try:
            schedule.save()
        except ValidationError as exc:
            if "already assigned for the selected batch time" in " ".join(exc.messages):
                continue
            raise
        created_count += 1

    if created_count == 0:
        raise ValidationError("No new schedule slot was created. Selected range may already exist.")
    return created_count


def available_portal_users(current_user_id=None):
    queryset = User.objects.filter(is_active=True)
    queryset = queryset.exclude(trainer_profile__isnull=False).exclude(counsellor_profile__isnull=False)
    if current_user_id:
        queryset = queryset | User.objects.filter(id=current_user_id)
    return queryset.order_by("username").distinct()


def trainer_form_data_from_request(request):
    return {
        "name": (request.POST.get("name") or "").strip(),
        "mobile": (request.POST.get("mobile") or "").strip(),
        "age": request.POST.get("age") or "",
        "dob": request.POST.get("dob") or "",
        "joining_date": request.POST.get("joining_date") or "",
        "record_scope": request.POST.get("record_scope") or Trainer.RECORD_SCOPE_ASSIGNED,
        "can_access_student_registration": request.POST.get("can_access_student_registration") == "on",
        "can_access_student_records": request.POST.get("can_access_student_records") == "on",
        "can_edit_students": request.POST.get("can_edit_students") == "on",
        "can_manage_fees": request.POST.get("can_manage_fees") == "on",
        "can_access_enquiries": request.POST.get("can_access_enquiries") == "on",
        "can_convert_enquiries": request.POST.get("can_convert_enquiries") == "on",
        "can_manage_batches": request.POST.get("can_manage_batches") == "on",
        "can_access_attendance": request.POST.get("can_access_attendance") == "on",
        "can_access_logistics": request.POST.get("can_access_logistics") == "on",
        "can_view_reports": request.POST.get("can_view_reports") == "on",
        "can_view_exams": request.POST.get("can_view_exams") == "on",
        "selected_course_ids": request.POST.getlist("courses"),
        "login_username": (request.POST.get("login_username") or "").strip(),
        "login_password": request.POST.get("login_password") or "",
        "user_id": request.POST.get("user") or "",
    }


def validate_trainer_form(request, current_user=None):
    user_id = request.POST.get("user") or None
    login_username = (request.POST.get("login_username") or "").strip()
    login_password = request.POST.get("login_password") or ""
    if not user_id and not current_user:
        if not login_username:
            return "New trainer login username is required."
        if not login_password:
            return "New trainer password is required."
    if login_password and not login_username and not user_id and not current_user:
        return "Enter a username when setting a login password."
    if login_username and not login_password and not user_id and not current_user:
        return "Enter a password for the new trainer login."
    if login_username:
        queryset = User.objects.filter(username__iexact=login_username)
        if current_user:
            queryset = queryset.exclude(id=current_user.id)
        elif user_id:
            queryset = queryset.exclude(id=user_id)
        if queryset.exists():
            return "That login username already exists."
    return None


def resolve_portal_user(request, current_user=None):
    user_id = request.POST.get("user") or None
    login_username = (request.POST.get("login_username") or "").strip()
    login_password = request.POST.get("login_password") or ""
    if user_id:
        user = User.objects.get(id=user_id)
        should_save = False
        if login_username and user.username != login_username:
            user.username = login_username
            should_save = True
        if login_password:
            user.set_password(login_password)
            should_save = True
        if user.first_name != (request.POST.get("name") or ""):
            user.first_name = request.POST.get("name") or ""
            should_save = True
        if should_save:
            user.save()
        return user
    if current_user:
        should_save = False
        if login_username and current_user.username != login_username:
            current_user.username = login_username
            should_save = True
        if login_password:
            current_user.set_password(login_password)
            should_save = True
        if current_user.first_name != (request.POST.get("name") or ""):
            current_user.first_name = request.POST.get("name") or ""
            should_save = True
        if should_save:
            current_user.save()
        return current_user
    if login_username:
        user = User.objects.create_user(username=login_username, password=login_password)
        user.first_name = request.POST.get("name") or ""
        user.is_staff = False
        user.is_superuser = False
        user.save()
        return user
    return current_user
