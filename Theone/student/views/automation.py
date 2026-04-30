from functools import wraps
from datetime import date, timedelta

from django.contrib import messages
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from student.models import Attendance, Center, CommunicationLog, Counsellor, Enquiry, Installment, Student, Trainer
from student.portal import (
    ROLE_ADMIN,
    get_enquiry_for_user_or_404,
    get_portal_role,
    get_student_for_user_or_404,
    portal_login_required,
    portal_redirect_name,
    role_required,
    scope_centers_for_user,
    scope_counsellors_for_user,
    scope_enquiries_for_user,
    scope_students_for_user,
    user_can_access_reminder_center,
    user_can_send_fee_reminders,
    user_can_send_follow_up_reminders,
)
from student.sms import (
    build_enquiry_follow_up_message,
    build_fee_reminder_message,
    send_general_sms,
)
from student.views.helpers import build_sms_status_context


def reminder_capability_required(capability_check):
    def decorator(view_func):
        @portal_login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not capability_check(request.user):
                messages.error(request, "You do not have access to that page.")
                return redirect(portal_redirect_name(request.user))
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


def get_fee_students(user):
    return list(
        scope_students_for_user(
            user,
            Student.objects.select_related("center", "trainer", "counsellor", "batch")
            .prefetch_related("courses")
            .filter(course_fee__gt=0),
        )
        .order_by("joining_date", "name")
    )


def get_pending_fee_students(user):
    return [student for student in get_fee_students(user) if student.remaining_fee > 0]


def get_follow_up_enquiries(user):
    return list(
        scope_enquiries_for_user(
            user,
            Enquiry.objects.select_related(
                "interested_course", "preferred_center", "preferred_batch", "assigned_counsellor"
            ),
        )
        .exclude(status__in=["admitted", "lost"])
        .order_by("next_follow_up_date", "name")
    )


def build_recent_communication_logs(user):
    role = get_portal_role(user)
    logs_qs = CommunicationLog.objects.select_related("student", "enquiry")
    if role == ROLE_ADMIN:
        return list(logs_qs[:20])

    student_ids = list(scope_students_for_user(user, Student.objects.all()).values_list("id", flat=True))
    enquiry_ids = list(scope_enquiries_for_user(user, Enquiry.objects.all()).values_list("id", flat=True))
    if not student_ids and not enquiry_ids:
        return []
    return list(logs_qs.filter(Q(student_id__in=student_ids) | Q(enquiry_id__in=enquiry_ids))[:20])


def build_reminder_context(request):
    today = date.today()
    due_cutoff = today - timedelta(days=30)
    can_send_fee = user_can_send_fee_reminders(request.user)
    can_send_follow_up = user_can_send_follow_up_reminders(request.user)

    fee_students = get_pending_fee_students(request.user) if can_send_fee else []
    overdue_students = [student for student in fee_students if student.joining_date and student.joining_date <= due_cutoff]
    no_payment_students = [student for student in fee_students if student.total_paid == 0]

    follow_up_enquiries = get_follow_up_enquiries(request.user) if can_send_follow_up else []
    today_follow_ups = [enquiry for enquiry in follow_up_enquiries if enquiry.next_follow_up_date == today]
    overdue_follow_ups = [
        enquiry for enquiry in follow_up_enquiries if enquiry.next_follow_up_date and enquiry.next_follow_up_date < today
    ]
    stale_enquiries = [
        enquiry
        for enquiry in follow_up_enquiries
        if enquiry.updated_at.date() <= today - timedelta(days=7)
    ]

    return {
        "today": today,
        "fee_students": fee_students[:30],
        "overdue_students": overdue_students[:20],
        "no_payment_students": no_payment_students[:20],
        "today_follow_ups": today_follow_ups[:20],
        "overdue_follow_ups": overdue_follow_ups[:20],
        "stale_enquiries": stale_enquiries[:20],
        "recent_logs": build_recent_communication_logs(request.user),
        "sms_status": build_sms_status_context(),
        "pending_fee_alert_count": len(fee_students),
        "overdue_fee_alert_count": len(overdue_students),
        "today_follow_up_alert_count": len(today_follow_ups),
        "overdue_follow_up_alert_count": len(overdue_follow_ups),
        "centers": scope_centers_for_user(request.user, Center.objects.order_by("name")),
        "counsellors": scope_counsellors_for_user(request.user, Counsellor.objects.select_related("center").order_by("name")),
        "can_send_fee_reminders": can_send_fee,
        "can_send_follow_up_reminders": can_send_follow_up,
        "is_admin_automation_user": get_portal_role(request.user) == ROLE_ADMIN,
    }


@reminder_capability_required(user_can_access_reminder_center)
def reminder_center(request):
    return render(request, "automation/reminder_center.html", build_reminder_context(request))


@reminder_capability_required(user_can_send_fee_reminders)
@require_POST
def send_fee_reminder(request, student_id):
    student = get_student_for_user_or_404(
        request.user,
        student_id,
        Student.objects.prefetch_related("courses"),
    )
    message_body = build_fee_reminder_message(student)
    result = send_general_sms(
        student=student,
        message_body=message_body,
        category=CommunicationLog.CATEGORY_FEE_REMINDER,
    )
    if result.sent:
        messages.success(request, f"Fee reminder sent to {student.name}.")
    elif result.skipped:
        messages.info(request, f"Fee reminder not sent for {student.name}. {result.detail}")
    else:
        messages.warning(request, f"Fee reminder failed for {student.name}. {result.detail}")
    return redirect("reminder_center")


@reminder_capability_required(user_can_send_follow_up_reminders)
@require_POST
def send_enquiry_follow_up_reminder(request, enquiry_id):
    enquiry = get_enquiry_for_user_or_404(
        request.user,
        enquiry_id,
        Enquiry.objects.select_related("interested_course", "preferred_center", "assigned_counsellor"),
    )
    message_body = build_enquiry_follow_up_message(enquiry)
    result = send_general_sms(
        enquiry=enquiry,
        message_body=message_body,
        category=CommunicationLog.CATEGORY_ENQUIRY_FOLLOW_UP,
    )
    if result.sent:
        messages.success(request, f"Follow-up reminder sent to {enquiry.name}.")
    elif result.skipped:
        messages.info(request, f"Follow-up reminder not sent for {enquiry.name}. {result.detail}")
    else:
        messages.warning(request, f"Follow-up reminder failed for {enquiry.name}. {result.detail}")
    return redirect("reminder_center")


@reminder_capability_required(user_can_send_fee_reminders)
@require_POST
def send_bulk_fee_reminders(request):
    today = date.today()
    center_id = (request.POST.get("center") or "").strip()
    reminder_scope = (request.POST.get("scope") or "overdue").strip()

    students = get_pending_fee_students(request.user)
    if center_id:
        students = [student for student in students if str(student.center_id or "") == center_id]
    if reminder_scope == "overdue":
        students = [student for student in students if student.joining_date and student.joining_date <= today - timedelta(days=30)]
    elif reminder_scope == "no_payment":
        students = [student for student in students if student.total_paid == 0]

    sent_count = 0
    skipped_count = 0
    failed_count = 0
    for student in students:
        result = send_general_sms(
            student=student,
            message_body=build_fee_reminder_message(student),
            category=CommunicationLog.CATEGORY_FEE_REMINDER,
        )
        if result.sent:
            sent_count += 1
        elif result.skipped:
            skipped_count += 1
        else:
            failed_count += 1

    messages.success(
        request,
        f"Bulk fee reminders processed: {len(students)} total, {sent_count} sent, {skipped_count} skipped, {failed_count} failed.",
    )
    return redirect("reminder_center")


@reminder_capability_required(user_can_send_follow_up_reminders)
@require_POST
def send_bulk_follow_up_reminders(request):
    today = date.today()
    counsellor_id = (request.POST.get("counsellor") or "").strip()
    reminder_scope = (request.POST.get("scope") or "overdue").strip()

    enquiries = get_follow_up_enquiries(request.user)
    if counsellor_id:
        enquiries = [enquiry for enquiry in enquiries if str(enquiry.assigned_counsellor_id or "") == counsellor_id]
    if reminder_scope == "today":
        enquiries = [enquiry for enquiry in enquiries if enquiry.next_follow_up_date == today]
    elif reminder_scope == "overdue":
        enquiries = [enquiry for enquiry in enquiries if enquiry.next_follow_up_date and enquiry.next_follow_up_date < today]
    elif reminder_scope == "stale":
        enquiries = [enquiry for enquiry in enquiries if enquiry.updated_at.date() <= today - timedelta(days=7)]

    sent_count = 0
    skipped_count = 0
    failed_count = 0
    for enquiry in enquiries:
        result = send_general_sms(
            enquiry=enquiry,
            message_body=build_enquiry_follow_up_message(enquiry),
            category=CommunicationLog.CATEGORY_ENQUIRY_FOLLOW_UP,
        )
        if result.sent:
            sent_count += 1
        elif result.skipped:
            skipped_count += 1
        else:
            failed_count += 1

    messages.success(
        request,
        f"Bulk follow-up reminders processed: {len(enquiries)} total, {sent_count} sent, {skipped_count} skipped, {failed_count} failed.",
    )
    return redirect("reminder_center")


@role_required(ROLE_ADMIN)
def communication_log_list(request):
    category = request.GET.get("category", "").strip()
    status = request.GET.get("status", "").strip()
    logs_qs = CommunicationLog.objects.select_related("student", "enquiry")
    if category:
        logs_qs = logs_qs.filter(category=category)
    if status:
        logs_qs = logs_qs.filter(status=status)
    return render(
        request,
        "automation/communication_logs.html",
        {
            "logs": logs_qs[:200],
            "category": category,
            "status": status,
            "category_choices": CommunicationLog.CATEGORY_CHOICES,
            "status_choices": CommunicationLog.STATUS_CHOICES,
        },
    )


@role_required(ROLE_ADMIN)
def daily_summary(request):
    selected_date = request.GET.get("date", "").strip()
    try:
        summary_date = date.fromisoformat(selected_date) if selected_date else date.today()
    except ValueError:
        summary_date = date.today()

    admissions = Student.objects.select_related("center", "trainer").filter(joining_date=summary_date)
    enquiries = Enquiry.objects.select_related("preferred_center", "assigned_counsellor").filter(enquiry_date=summary_date)
    follow_ups = Enquiry.objects.select_related("preferred_center", "assigned_counsellor").filter(next_follow_up_date=summary_date).exclude(status__in=["admitted", "lost"])
    installments = Installment.objects.select_related("student__center").filter(installment_date=summary_date)
    absentees = Attendance.objects.select_related("student__center", "student__batch").filter(date=summary_date, status="absent")

    center_rows = []
    center_names = {center.name for center in [student.center for student in admissions if student.center]}
    center_names.update(center.name for center in [enquiry.preferred_center for enquiry in enquiries if enquiry.preferred_center])
    center_names.update(record.student.center.name for record in absentees if record.student.center)
    for center_name in sorted(center_names):
        center_rows.append(
            {
                "name": center_name,
                "admissions": sum(1 for student in admissions if student.center and student.center.name == center_name),
                "enquiries": sum(1 for enquiry in enquiries if enquiry.preferred_center and enquiry.preferred_center.name == center_name),
                "collections": sum((student.paid_fee or 0) for student in admissions if student.center and student.center.name == center_name)
                + sum((installment.amount or 0) for installment in installments if installment.student.center and installment.student.center.name == center_name),
                "absentees": sum(1 for record in absentees if record.student.center and record.student.center.name == center_name),
            }
        )

    return render(
        request,
        "automation/daily_summary.html",
        {
            "summary_date": summary_date,
            "admissions": admissions[:25],
            "enquiries": enquiries[:25],
            "follow_ups": follow_ups[:25],
            "absentees": absentees[:25],
            "today_collection_total": sum(student.paid_fee or 0 for student in admissions)
            + (installments.aggregate(total=Sum("amount"))["total"] or 0),
            "admissions_count": admissions.count(),
            "enquiries_count": enquiries.count(),
            "follow_up_count": follow_ups.count(),
            "absentee_count": absentees.count(),
            "center_rows": center_rows,
        },
    )


@role_required(ROLE_ADMIN)
def staff_center_analytics(request):
    today = date.today()
    date_from_value = (request.GET.get("date_from") or "").strip()
    date_to_value = (request.GET.get("date_to") or "").strip()
    try:
        date_from = date.fromisoformat(date_from_value) if date_from_value else today.replace(day=1)
    except ValueError:
        date_from = today.replace(day=1)
    try:
        date_to = date.fromisoformat(date_to_value) if date_to_value else today
    except ValueError:
        date_to = today
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    students = list(
        Student.objects.select_related("center", "trainer", "counsellor")
        .prefetch_related("courses")
        .filter(joining_date__range=(date_from, date_to))
    )
    enquiries = list(
        Enquiry.objects.select_related("preferred_center", "assigned_counsellor", "interested_course")
        .filter(enquiry_date__range=(date_from, date_to))
    )
    conversions = list(
        Enquiry.objects.select_related("preferred_center", "assigned_counsellor")
        .filter(converted_at__range=(date_from, date_to))
    )
    installments = list(
        Installment.objects.select_related("student__center", "student__trainer", "student__counsellor")
        .filter(installment_date__range=(date_from, date_to))
    )
    pending_students = get_pending_fee_students(request.user)
    overdue_follow_ups = [
        enquiry
        for enquiry in get_follow_up_enquiries(request.user)
        if enquiry.next_follow_up_date and enquiry.next_follow_up_date < today
    ]

    center_rows = []
    for center in Center.objects.order_by("name"):
        center_students = [student for student in students if student.center_id == center.id]
        center_enquiries = [enquiry for enquiry in enquiries if enquiry.preferred_center_id == center.id]
        center_conversions = [enquiry for enquiry in conversions if enquiry.preferred_center_id == center.id]
        center_pending = [student for student in pending_students if student.center_id == center.id]
        center_installments = [installment for installment in installments if installment.student.center_id == center.id]
        if center_students or center_enquiries or center_pending or center_conversions:
            enquiry_count = len(center_enquiries)
            conversion_count = len(center_conversions)
            center_rows.append(
                {
                    "name": center.name,
                    "enquiries": enquiry_count,
                    "admissions": len(center_students),
                    "conversions": conversion_count,
                    "conversion_rate": round((conversion_count / enquiry_count) * 100, 2) if enquiry_count else 0,
                    "collection": sum(student.paid_fee or 0 for student in center_students) + sum(installment.amount or 0 for installment in center_installments),
                    "pending_fee": sum(student.remaining_fee for student in center_pending),
                    "pending_students": len(center_pending),
                }
            )

    counsellor_rows = []
    for counsellor in Counsellor.objects.select_related("center").order_by("name"):
        counsellor_students = [student for student in students if student.counsellor_id == counsellor.id]
        counsellor_enquiries = [enquiry for enquiry in enquiries if enquiry.assigned_counsellor_id == counsellor.id]
        counsellor_conversions = [enquiry for enquiry in conversions if enquiry.assigned_counsellor_id == counsellor.id]
        counsellor_pending = [student for student in pending_students if student.counsellor_id == counsellor.id]
        counsellor_overdue = [enquiry for enquiry in overdue_follow_ups if enquiry.assigned_counsellor_id == counsellor.id]
        if counsellor_students or counsellor_enquiries or counsellor_pending or counsellor_conversions or counsellor_overdue:
            enquiry_count = len(counsellor_enquiries)
            conversion_count = len(counsellor_conversions)
            counsellor_rows.append(
                {
                    "name": counsellor.name,
                    "center_name": counsellor.center.name if counsellor.center else "-",
                    "enquiries": enquiry_count,
                    "admissions": len(counsellor_students),
                    "conversions": conversion_count,
                    "conversion_rate": round((conversion_count / enquiry_count) * 100, 2) if enquiry_count else 0,
                    "pending_fee": sum(student.remaining_fee for student in counsellor_pending),
                    "pending_students": len(counsellor_pending),
                    "overdue_follow_ups": len(counsellor_overdue),
                }
            )

    trainer_rows = []
    for trainer in Trainer.objects.order_by("name"):
        trainer_students = [student for student in students if student.trainer_id == trainer.id]
        trainer_pending = [student for student in pending_students if student.trainer_id == trainer.id]
        trainer_installments = [installment for installment in installments if installment.student.trainer_id == trainer.id]
        if trainer_students or trainer_pending or trainer_installments:
            trainer_rows.append(
                {
                    "name": trainer.name,
                    "students": len(trainer_students),
                    "active_students": sum(1 for student in trainer_students if student.status == "active"),
                    "pending_students": len(trainer_pending),
                    "pending_fee": sum(student.remaining_fee for student in trainer_pending),
                    "collection": sum(student.paid_fee or 0 for student in trainer_students) + sum(installment.amount or 0 for installment in trainer_installments),
                }
            )

    return render(
        request,
        "automation/staff_center_analytics.html",
        {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "center_rows": center_rows,
            "counsellor_rows": counsellor_rows,
            "trainer_rows": trainer_rows,
            "total_centers": len(center_rows),
            "total_counsellors": len(counsellor_rows),
            "total_trainers": len(trainer_rows),
        },
    )
