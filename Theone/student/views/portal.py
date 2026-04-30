from datetime import date

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Count, Sum
from django.shortcuts import redirect, render

from student.models import Attendance, CenterLogistics, Enquiry, Installment, Student
from student.portal import (
    ROLE_ADMIN,
    ROLE_COUNSELLOR,
    ROLE_TRAINER,
    get_counsellor_for_user,
    get_portal_role,
    get_trainer_for_user,
    portal_redirect_name,
    require_portal_account,
    role_required,
    scope_centers_for_user,
    scope_enquiries_for_user,
    scope_students_for_user,
)


def portal_login(request):
    if request.user.is_authenticated:
        try:
            require_portal_account(request.user)
        except Exception:
            logout(request)
        else:
            return redirect(portal_redirect_name(request.user))

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        role = get_portal_role(user)
        if not role:
            form.add_error(None, "This user is not linked to an admin, counsellor, or trainer portal.")
        else:
            login(request, user)
            return redirect(portal_redirect_name(user))

    return render(request, "portal/login.html", {"form": form, "portal_hide_navigation": True})


def portal_logout(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("portal_login")


@role_required(ROLE_COUNSELLOR)
def counsellor_dashboard(request):
    counsellor = get_counsellor_for_user(request.user)
    if not counsellor:
        messages.error(request, "This login is not linked to a counsellor profile.")
        return redirect("portal_login")

    today = date.today()
    students = list(
        scope_students_for_user(request.user, Student.objects.select_related("trainer", "batch", "center").prefetch_related("courses")).order_by("-joining_date", "name")
    )
    enquiries = list(
        scope_enquiries_for_user(
            request.user,
            Enquiry.objects.select_related("interested_course", "preferred_center", "preferred_batch", "assigned_counsellor"),
        ).order_by("-updated_at", "-enquiry_date")
    )

    context = {
        "counsellor": counsellor,
        "students": students[:8],
        "recent_enquiries": enquiries[:8],
        "today_follow_ups": [enquiry for enquiry in enquiries if enquiry.next_follow_up_date == today][:8],
        "pending_fee_students": [student for student in students if student.remaining_fee > 0][:8],
        "student_count": len(students),
        "active_students": sum(1 for student in students if student.status == "active"),
        "pending_fee_total": sum(student.remaining_fee for student in students),
        "today_admissions": sum(1 for student in students if student.joining_date == today),
        "today_follow_up_count": sum(1 for enquiry in enquiries if enquiry.next_follow_up_date == today),
        "open_enquiry_count": sum(1 for enquiry in enquiries if enquiry.status not in {"admitted", "lost"}),
        "center_name": counsellor.center.name if counsellor.center else "No Center Assigned",
    }
    return render(request, "portal/counsellor_dashboard.html", context)


@role_required(ROLE_TRAINER)
def trainer_dashboard(request):
    trainer = get_trainer_for_user(request.user)
    if not trainer:
        messages.error(request, "This login is not linked to a trainer profile.")
        return redirect("portal_login")

    today = date.today()
    students = list(
        scope_students_for_user(request.user, Student.objects.select_related("batch", "center", "counsellor").prefetch_related("courses")).order_by("name")
    )
    centers = list(scope_centers_for_user(request.user))
    todays_attendance = Attendance.objects.filter(student__trainer=trainer, date=today)

    context = {
        "trainer": trainer,
        "students": students[:10],
        "student_count": len(students),
        "active_students": sum(1 for student in students if student.status == "active"),
        "pending_fee_total": sum(student.remaining_fee for student in students),
        "present_count": todays_attendance.filter(status="present").count(),
        "absent_count": todays_attendance.filter(status="absent").count(),
        "leave_count": todays_attendance.filter(status="leave").count(),
        "batches": trainer.trainerschedule_set.select_related("batch", "center").order_by("batch__time", "center__name"),
        "logistics_rows": [
            {
                "center": center,
                "log": CenterLogistics.objects.get_or_create(center=center)[0],
                "student_count": len([student for student in students if student.center_id == center.id]),
            }
            for center in centers
        ],
    }
    return render(request, "portal/trainer_dashboard.html", context)
