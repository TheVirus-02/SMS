from datetime import date

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from student.models import Center, Counsellor, Enquiry, Student
from student.portal import ROLE_ADMIN, ROLE_COUNSELLOR, get_counsellor_for_user_or_404, get_portal_role, role_required


User = get_user_model()


@role_required(ROLE_ADMIN)
def counsellor_list(request):
    query = request.GET.get("q", "").strip()
    centre_id = request.GET.get("center", "").strip()
    today = date.today()

    counsellors = Counsellor.objects.select_related("center", "user").annotate(
        student_count=Count("student", distinct=True),
        active_student_count=Count("student", filter=Q(student__status="active"), distinct=True),
        completed_student_count=Count("student", filter=Q(student__status="completed"), distinct=True),
        joined_this_month_count=Count(
            "student",
            filter=Q(student__joining_date__year=today.year, student__joining_date__month=today.month),
            distinct=True,
        ),
        enquiry_count=Count("enquiry", distinct=True),
        open_enquiry_count=Count("enquiry", filter=~Q(enquiry__status="admitted"), distinct=True),
        today_follow_up_enquiry_count=Count("enquiry", filter=Q(enquiry__next_follow_up_date=today), distinct=True),
    ).order_by("name")

    if query:
        counsellors = counsellors.filter(
            Q(name__icontains=query)
            | Q(mobile__icontains=query)
            | Q(center__name__icontains=query)
            | Q(user__username__icontains=query)
        )
    if centre_id:
        counsellors = counsellors.filter(center_id=centre_id)

    return render(
        request,
        "counsellor/counsellor_list.html",
        {
            "counsellors": counsellors,
            "query": query,
            "selected_center_id": centre_id,
            "centers": Center.objects.all().order_by("name"),
            "total_counsellors": counsellors.count(),
            "total_students": sum(counsellor.student_count for counsellor in counsellors),
            "total_active_students": sum(counsellor.active_student_count for counsellor in counsellors),
            "total_joined_this_month": sum(counsellor.joined_this_month_count for counsellor in counsellors),
            "total_enquiries": sum(counsellor.enquiry_count for counsellor in counsellors),
            "total_today_follow_ups": sum(counsellor.today_follow_up_enquiry_count for counsellor in counsellors),
        },
    )


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR)
def counsellor_detail(request, id):
    if get_portal_role(request.user) == ROLE_COUNSELLOR:
        counsellor = get_counsellor_for_user_or_404(request.user, id, Counsellor.objects.select_related("center", "user"))
    else:
        counsellor = get_object_or_404(Counsellor.objects.select_related("center", "user"), id=id)
    students = Student.objects.select_related("trainer", "batch", "center").filter(
        counsellor=counsellor
    ).order_by("name")
    today = date.today()
    active_students = [student for student in students if student.status == "active"]
    completed_students = [student for student in students if student.status == "completed"]
    joined_this_month = [
        student
        for student in students
        if student.joining_date and student.joining_date.year == today.year and student.joining_date.month == today.month
    ]
    enquiries = list(
        Enquiry.objects.select_related("interested_course", "preferred_center").filter(
            assigned_counsellor=counsellor
        ).order_by("-updated_at", "-enquiry_date")[:10]
    )
    return render(
        request,
        "counsellor/counsellor_detail.html",
        {
            "counsellor": counsellor,
            "students": students,
            "student_count": students.count(),
            "active_student_count": len(active_students),
            "completed_student_count": len(completed_students),
            "joined_this_month_count": len(joined_this_month),
            "enquiries": enquiries,
            "enquiry_count": Enquiry.objects.filter(assigned_counsellor=counsellor).count(),
            "open_enquiry_count": Enquiry.objects.filter(assigned_counsellor=counsellor).exclude(status="admitted").count(),
            "today_follow_up_enquiry_count": Enquiry.objects.filter(assigned_counsellor=counsellor, next_follow_up_date=today).count(),
        },
    )


@role_required(ROLE_ADMIN)
def add_counsellor(request):
    centers = Center.objects.all().order_by("name")
    if request.method == "POST":
        form_data = build_counsellor_form_data(request)
        error = validate_counsellor_form(form_data)
        if error:
            return render(
                request,
                "counsellor/counsellor_form.html",
                {"centers": centers, "error": [error], "form_data": normalize_counsellor_form_data(form_data), "users": available_portal_users()},
            )

        user = resolve_portal_user(form_data, role_label="counsellor")
        counsellor = Counsellor.objects.create(**build_counsellor_model_payload(form_data, user))
        messages.success(request, f"{counsellor.name} added successfully.")
        return redirect("counsellor_detail", id=counsellor.id)

    return render(
        request,
        "counsellor/counsellor_form.html",
        {"centers": centers, "error": [], "form_data": empty_counsellor_form_data(), "users": available_portal_users()},
    )


@role_required(ROLE_ADMIN)
def update_counsellor(request, id):
    counsellor = get_object_or_404(Counsellor, id=id)
    centers = Center.objects.all().order_by("name")
    if request.method == "POST":
        form_data = build_counsellor_form_data(request)
        error = validate_counsellor_form(form_data)
        if error:
            return render(
                request,
                "counsellor/counsellor_form.html",
                {
                    "counsellor": counsellor,
                    "centers": centers,
                    "error": [error],
                    "form_data": normalize_counsellor_form_data(form_data),
                    "users": available_portal_users(counsellor.user_id),
                },
            )

        for field, value in form_data.items():
            if field in {"user_id", "login_username", "login_password"}:
                continue
            setattr(counsellor, field, value)
        user = resolve_portal_user(form_data, current_user=counsellor.user, role_label="counsellor")
        counsellor.user = user
        counsellor.save()
        messages.success(request, f"{counsellor.name} updated successfully.")
        return redirect("counsellor_detail", id=counsellor.id)

    return render(
        request,
        "counsellor/counsellor_form.html",
        {
            "counsellor": counsellor,
            "centers": centers,
            "error": [],
            "users": available_portal_users(counsellor.user_id),
            "form_data": {
                "name": counsellor.name,
                "mobile": counsellor.mobile or "",
                "center_id": str(counsellor.center_id) if counsellor.center_id else "",
                "can_send_fee_reminders": counsellor.can_send_fee_reminders,
                "can_send_follow_up_reminders": counsellor.can_send_follow_up_reminders,
                "address": counsellor.address or "",
                "age": counsellor.age or "",
                "dob": counsellor.dob.isoformat() if counsellor.dob else "",
                "joining_date": counsellor.joining_date.isoformat() if counsellor.joining_date else "",
                "user_id": str(counsellor.user_id) if counsellor.user_id else "",
                "login_username": counsellor.user.username if counsellor.user_id else "",
                "login_password": "",
            },
        },
    )


@role_required(ROLE_ADMIN)
def delete_counsellor(request, id):
    counsellor = get_object_or_404(Counsellor, id=id)
    counsellor_name = counsellor.name
    counsellor.delete()
    messages.success(request, f"{counsellor_name} deleted successfully.")
    return redirect("counsellor_list")


def build_counsellor_form_data(request):
    return {
        "name": (request.POST.get("name") or "").strip(),
        "mobile": (request.POST.get("mobile") or "").strip() or None,
        "center_id": request.POST.get("center") or None,
        "can_send_fee_reminders": request.POST.get("can_send_fee_reminders") == "on",
        "can_send_follow_up_reminders": request.POST.get("can_send_follow_up_reminders") == "on",
        "address": (request.POST.get("address") or "").strip() or None,
        "age": request.POST.get("age") or None,
        "dob": request.POST.get("dob") or None,
        "joining_date": request.POST.get("joining_date") or None,
        "user_id": request.POST.get("user") or None,
        "login_username": (request.POST.get("login_username") or "").strip(),
        "login_password": request.POST.get("login_password") or "",
    }


def validate_counsellor_form(form_data):
    if not form_data["name"]:
        return "Counsellor name is required."
    if form_data["login_password"] and not form_data["login_username"] and not form_data["user_id"]:
        return "Enter a username when setting a login password."
    if form_data["login_username"]:
        queryset = User.objects.filter(username__iexact=form_data["login_username"])
        if form_data["user_id"]:
            queryset = queryset.exclude(id=form_data["user_id"])
        if queryset.exists():
            return "That login username already exists."
    return None


def empty_counsellor_form_data():
    return {
        "name": "",
        "mobile": "",
        "center_id": "",
        "can_send_fee_reminders": False,
        "can_send_follow_up_reminders": False,
        "address": "",
        "age": "",
        "dob": "",
        "joining_date": "",
        "user_id": "",
        "login_username": "",
        "login_password": "",
    }


def normalize_counsellor_form_data(form_data):
    return {
        "name": form_data["name"],
        "mobile": form_data["mobile"] or "",
        "center_id": str(form_data["center_id"]) if form_data["center_id"] else "",
        "can_send_fee_reminders": bool(form_data["can_send_fee_reminders"]),
        "can_send_follow_up_reminders": bool(form_data["can_send_follow_up_reminders"]),
        "address": form_data["address"] or "",
        "age": form_data["age"] or "",
        "dob": form_data["dob"] or "",
        "joining_date": form_data["joining_date"] or "",
        "user_id": str(form_data["user_id"]) if form_data["user_id"] else "",
        "login_username": form_data["login_username"],
        "login_password": "",
    }


def available_portal_users(current_user_id=None):
    queryset = User.objects.filter(is_active=True)
    queryset = queryset.exclude(trainer_profile__isnull=False).exclude(counsellor_profile__isnull=False)
    if current_user_id:
        queryset = queryset | User.objects.filter(id=current_user_id)
    return queryset.order_by("username").distinct()


def resolve_portal_user(form_data, current_user=None, role_label="user"):
    if form_data["user_id"]:
        user = User.objects.get(id=form_data["user_id"])
        should_save = False
        if form_data["login_password"]:
            user.set_password(form_data["login_password"])
            should_save = True
        if form_data["login_username"] and user.username != form_data["login_username"]:
            user.username = form_data["login_username"]
            should_save = True
        if user.first_name != form_data["name"]:
            user.first_name = form_data["name"]
            should_save = True
        if should_save:
            user.save()
        return user
    username = form_data["login_username"]
    password = form_data["login_password"]
    if current_user:
        should_save = False
        if username and current_user.username != username:
            current_user.username = username
            should_save = True
        if password:
            current_user.set_password(password)
            should_save = True
        if current_user.first_name != form_data["name"]:
            current_user.first_name = form_data["name"]
            should_save = True
        if should_save:
            current_user.save()
        return current_user
    if username:
        user = User.objects.create_user(username=username, password=password or User.objects.make_random_password())
        user.first_name = form_data["name"]
        user.save()
        return user
    return current_user


def build_counsellor_model_payload(form_data, user):
    return {
        "name": form_data["name"],
        "mobile": form_data["mobile"],
        "center_id": form_data["center_id"],
        "can_send_fee_reminders": form_data["can_send_fee_reminders"],
        "can_send_follow_up_reminders": form_data["can_send_follow_up_reminders"],
        "address": form_data["address"],
        "age": form_data["age"],
        "dob": form_data["dob"],
        "joining_date": form_data["joining_date"],
        "user": user,
    }
