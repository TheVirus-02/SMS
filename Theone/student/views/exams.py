from datetime import date, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Prefetch, Q, Sum
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render

from student.models import ExamRegistration, SmsLog, Student, StudentCourse, Trainer
from student.portal import ROLE_ADMIN, ROLE_COUNSELLOR, ROLE_TRAINER, capability_required, user_can_view_exams
from student.sms import send_exam_registration_sms
from student.views.helpers import build_sms_status_context


@capability_required(user_can_view_exams, ROLE_ADMIN, ROLE_COUNSELLOR, ROLE_TRAINER)
def register_exam(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    completed_courses = StudentCourse.objects.select_related("course").filter(
        student=student,
        is_completed=True,
        exam_registration__isnull=True,
    )
    existing_registrations = ExamRegistration.objects.select_related(
        "student_course__course", "receipt_issued_by"
    ).prefetch_related(
        Prefetch("sms_logs", queryset=SmsLog.objects.order_by("-created_at"))
    ).filter(student_course__student=student)

    if request.method == "POST":
        student_course = get_object_or_404(
            StudentCourse.objects.select_related("course"),
            id=request.POST.get("student_course"),
            student=student,
            is_completed=True,
        )
        if hasattr(student_course, "exam_registration"):
            messages.error(request, f"{student_course.course.name} exam is already registered.")
            return redirect("register_exam", student_id=student.id)

        registration = ExamRegistration(
            student_course=student_course,
            exam_date=request.POST.get("exam_date") or None,
            receipt_no=request.POST.get("receipt_no", "").strip(),
            receipt_issued_by_id=request.POST.get("receipt_issued_by") or None,
            receipt_issued_date=request.POST.get("receipt_issued_date") or None,
            receipt_amount=request.POST.get("receipt_amount") or 0,
            payment_method=request.POST.get("payment_method") or "cash",
            payment_amount=request.POST.get("payment_amount") or 0,
            payment_reference=request.POST.get("payment_reference", "").strip() or None,
            remarks=request.POST.get("remarks", "").strip() or None,
        )

        try:
            registration.full_clean()
            registration.save()
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            sms_result = send_exam_registration_sms(student, registration)
            if sms_result.sent:
                messages.success(
                    request,
                    f"Exam registered for {student_course.course.name}. SMS sent to {student.mobile_no}.",
                )
            else:
                messages.success(request, f"Exam registered for {student_course.course.name}.")
                if sms_result.skipped:
                    messages.info(request, f"Student SMS status: {sms_result.detail}")
                else:
                    messages.warning(request, f"SMS was not sent. {sms_result.detail}")
            return redirect("student_detail", id=student.id)

    return render(
        request,
        "exams/register_exam.html",
        {
            "student": student,
            "completed_courses": completed_courses,
            "trainers": Trainer.objects.all().order_by("name"),
            "payment_mode_choices": ExamRegistration.PAYMENT_MODE_CHOICES,
            "existing_registrations": existing_registrations,
            "sms_status": build_sms_status_context(student),
            "show_student_nav": True,
        },
    )


@capability_required(user_can_view_exams, ROLE_ADMIN, ROLE_COUNSELLOR, ROLE_TRAINER)
def exam_dashboard(request):
    registrations = ExamRegistration.objects.select_related(
        "student_course__student",
        "student_course__course",
        "receipt_issued_by",
    ).prefetch_related(
        Prefetch("sms_logs", queryset=SmsLog.objects.order_by("-created_at"))
    )
    today = date.today()
    days_until_sunday = (6 - today.weekday()) % 7 or 7
    next_sunday = today + timedelta(days=days_until_sunday)

    next_sunday_registrations = ExamRegistration.objects.select_related(
        "student_course__student",
        "student_course__course",
        "receipt_issued_by",
    ).prefetch_related(
        Prefetch("sms_logs", queryset=SmsLog.objects.order_by("-created_at"))
    ).filter(exam_date=next_sunday).order_by(
        "receipt_issued_by__name",
        "student_course__student__name",
    )

    trainer_exam_fee_summary = [
        {
            "trainer_name": row["receipt_issued_by__name"] or "Not Assigned",
            "registration_count": row["registration_count"],
            "total_amount": row["total_amount"] or 0,
        }
        for row in next_sunday_registrations.values(
            "receipt_issued_by_id",
            "receipt_issued_by__name",
        ).annotate(
            registration_count=Count("id"),
            total_amount=Sum("payment_amount"),
        ).order_by("-total_amount", "receipt_issued_by__name")
    ]

    selected_date = request.GET.get("exam_date", "").strip()
    search_query = request.GET.get("q", "").strip()
    if selected_date:
        registrations = registrations.filter(exam_date=selected_date)
    if search_query:
        registrations = registrations.filter(
            Q(student_course__student__name__icontains=search_query)
            | Q(receipt_no__icontains=search_query)
            | Q(student_course__course__name__icontains=search_query)
        )

    return render(
        request,
        "exams/exam_dashboard.html",
        {
            "registrations": registrations,
            "selected_date": selected_date,
            "search_query": search_query,
            "available_dates": ExamRegistration.objects.order_by("exam_date")
            .values_list("exam_date", flat=True)
            .distinct(),
            "next_sunday": next_sunday,
            "next_sunday_registration_count": next_sunday_registrations.count(),
            "next_sunday_exam_fee_total": next_sunday_registrations.aggregate(
                total=Sum("payment_amount")
            )["total"]
            or 0,
            "trainer_exam_fee_summary": trainer_exam_fee_summary,
            "payment_mode_summary": next_sunday_registrations.values("payment_method")
            .annotate(registration_count=Count("id"), total_amount=Sum("payment_amount"))
            .order_by("-total_amount", "payment_method"),
            "next_sunday_registrations": next_sunday_registrations[:8],
        },
    )


@capability_required(user_can_view_exams, ROLE_ADMIN, ROLE_COUNSELLOR, ROLE_TRAINER)
def enter_marks(request, reg_id):
    reg = get_object_or_404(
        ExamRegistration.objects.select_related(
            "student_course__student",
            "student_course__course",
            "receipt_issued_by",
        ),
        id=reg_id,
    )
    if request.method == "POST":
        reg.exam_marks = request.POST.get("exam_marks") or None
        reg.practical_marks = request.POST.get("practical_marks") or None
        try:
            reg.full_clean()
            reg.save()
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, f"Marks saved for {reg.student_name} - {reg.course_name}.")
            return redirect(f"{redirect('exam_dashboard').url}?exam_date={reg.exam_date}")

    return render(request, "exams/update_marks.html", {"reg": reg, "show_student_nav": False})


@capability_required(user_can_view_exams, ROLE_ADMIN, ROLE_COUNSELLOR, ROLE_TRAINER)
def certificate_dashboard(request):
    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()

    registrations = ExamRegistration.objects.select_related(
        "student_course__student",
        "student_course__course",
    ).order_by("-exam_date", "student_course__student__name")

    if search_query:
        registrations = registrations.filter(
            Q(student_course__student__name__icontains=search_query)
            | Q(student_course__course__name__icontains=search_query)
        )

    registrations = list(registrations)
    if status_filter:
        registrations = [
            reg
            for reg in registrations
            if certificate_status_key(reg) == status_filter
        ]

    return render(
        request,
        "certificates/certificate_dashboard.html",
        {
            "registrations": registrations,
            "search_query": search_query,
            "status_filter": status_filter,
            "total_records": len(registrations),
            "created_count": sum(1 for reg in registrations if reg.is_certificate_created),
            "given_count": sum(1 for reg in registrations if reg.is_certificate_given),
            "pending_count": sum(1 for reg in registrations if reg.has_uploaded_marks and not reg.is_certificate_created),
        },
    )


@capability_required(user_can_view_exams, ROLE_ADMIN, ROLE_COUNSELLOR, ROLE_TRAINER)
def toggle_certificate_status(request, reg_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request method.")

    reg = get_object_or_404(ExamRegistration, id=reg_id)
    action = (request.POST.get("action") or "").strip()

    if action not in {"created", "given"}:
        return HttpResponseBadRequest("Invalid certificate action.")

    if action == "created":
        if reg.is_certificate_created:
            reg.certificate_created_date = None
            reg.certificate_given_date = None
            reg.save(update_fields=["certificate_created_date", "certificate_given_date", "updated_at"])
            messages.success(request, f"Certificate creation reset for {reg.student_name} - {reg.course_name}.")
        else:
            if not reg.has_uploaded_marks:
                messages.warning(request, f"Marks are not uploaded yet for {reg.student_name} - {reg.course_name}.")
            else:
                reg.certificate_created_date = date.today()
                reg.save(update_fields=["certificate_created_date", "updated_at"])
                messages.success(request, f"Certificate created for {reg.student_name} - {reg.course_name}.")

    if action == "given":
        if reg.is_certificate_given:
            reg.certificate_given_date = None
            reg.save(update_fields=["certificate_given_date", "updated_at"])
            messages.success(request, f"Certificate given status reset for {reg.student_name} - {reg.course_name}.")
        else:
            if not reg.has_uploaded_marks:
                messages.warning(request, f"Marks are not uploaded yet for {reg.student_name} - {reg.course_name}.")
            else:
                if not reg.is_certificate_created:
                    reg.certificate_created_date = date.today()
                reg.certificate_given_date = date.today()
                reg.save(update_fields=["certificate_created_date", "certificate_given_date", "updated_at"])
                messages.success(request, f"Certificate given marked for {reg.student_name} - {reg.course_name}.")

    redirect_url = redirect("certificate_dashboard").url
    query_params = {}
    if request.GET.get("q"):
        query_params["q"] = request.GET["q"]
    if request.GET.get("status"):
        query_params["status"] = request.GET["status"]
    if query_params:
        redirect_url = f"{redirect_url}?{urlencode(query_params)}"
    return redirect(redirect_url)


def certificate_status_key(reg):
    if not reg.has_uploaded_marks:
        return "not_given"
    if not reg.is_certificate_created:
        return "pending"
    if reg.is_certificate_given:
        return "given"
    return "created"
