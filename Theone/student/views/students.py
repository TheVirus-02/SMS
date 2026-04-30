import calendar
import csv
from datetime import date
import re

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from student.models import (
    Attendance,
    Batch,
    Center,
    Counsellor,
    Course,
    ExamRegistration,
    Enquiry,
    Installment,
    SmsLog,
    Student,
    StudentCourse,
    Trainer,
)
from student.portal import (
    ROLE_ADMIN,
    ROLE_COUNSELLOR,
    ROLE_TRAINER,
    scope_enquiries_for_user,
    get_portal_role,
    get_student_for_user_or_404,
    portal_login_required,
    role_required,
    scope_batches_for_user,
    scope_centers_for_user,
    scope_counsellors_for_user,
    scope_students_for_user,
    scope_trainers_for_user,
    user_can_manage_fees,
    user_can_view_exams,
)


def serialize_student_courses(student):
    return ", ".join(course.name for course in student.courses.all()) or "-"


def parse_report_date(raw_value):
    if not raw_value:
        return None
    try:
        return date.fromisoformat(raw_value)
    except ValueError:
        return None


def student_form_options(request):
    return {
        "courses": Course.objects.all().order_by("name"),
        "counsellors": scope_counsellors_for_user(request.user, Counsellor.objects.select_related("center")).order_by("name"),
        "trainers": scope_trainers_for_user(request.user, Trainer.objects.all()).order_by("name"),
        "batches": scope_batches_for_user(request.user, Batch.objects.all()).order_by("time"),
        "centers": scope_centers_for_user(request.user, Center.objects.all()).order_by("name"),
        "status_choices": Student.STATUS_CHOICES,
        "can_manage_fees": user_can_manage_fees(request.user),
        "can_view_exams": user_can_view_exams(request.user),
        "portal_role": get_portal_role(request.user),
    }


def apply_student_update_from_request(student, request):
    role = get_portal_role(request.user)
    can_manage_fees = user_can_manage_fees(request.user)
    student.name = request.POST.get("name")
    student.mobile_no = request.POST.get("mobile_no")
    student.alt_mobile_no = request.POST.get("alt_mobile_no")
    student.guardian_name = request.POST.get("guardian_name")
    student.guardian_mobile = request.POST.get("guardian_mobile")
    student.email = request.POST.get("email")
    student.qualification = request.POST.get("qualification")
    student.address = request.POST.get("address")
    student.reference_source = request.POST.get("reference_source")
    student.dob = request.POST.get("dob") or None
    student.joining_date = request.POST.get("joining_date") or None
    student.status = request.POST.get("status") or student.status
    student.batch_id = request.POST.get("batch") or None

    if role in {ROLE_ADMIN, ROLE_COUNSELLOR}:
        student.counsellor_id = request.POST.get("counsellor") or None
        student.trainer_id = request.POST.get("trainer") or None
        student.center_id = request.POST.get("center") or None
    elif role == ROLE_TRAINER:
        if student.trainer_id:
            student.trainer_id = student.trainer_id

    if can_manage_fees:
        student.course_fee = request.POST.get("course_fee")
        student.paid_fee = request.POST.get("paid_fee")


def build_student_record_context(request):
    students_qs = scope_students_for_user(
        request.user,
        Student.objects.select_related(
        "counsellor", "trainer", "batch", "center"
        ).prefetch_related("courses"),
    )
    query = request.GET.get("q", "").strip()
    payment_filter = request.GET.get("payment_status", "").strip()
    student_status = request.GET.get("student_status", "").strip()
    trainer_id = request.GET.get("trainer", "").strip()
    center_id = request.GET.get("center", "").strip()
    counsellor_id = request.GET.get("counsellor", "").strip()
    batch_id = request.GET.get("batch", "").strip()
    sort_by = request.GET.get("sort", "").strip() or "newest"

    if query:
        students_qs = students_qs.filter(
            Q(student_id__icontains=query)
            | Q(name__icontains=query)
            | Q(mobile_no__icontains=query)
            | Q(guardian_mobile__icontains=query)
            | Q(counsellor__name__icontains=query)
            | Q(trainer__name__icontains=query)
            | Q(center__name__icontains=query)
            | Q(courses__name__icontains=query)
        ).distinct()
    if student_status:
        students_qs = students_qs.filter(status=student_status)
    if trainer_id:
        students_qs = students_qs.filter(trainer_id=trainer_id)
    if center_id:
        students_qs = students_qs.filter(center_id=center_id)
    if counsellor_id:
        students_qs = students_qs.filter(counsellor_id=counsellor_id)
    if batch_id:
        students_qs = students_qs.filter(batch_id=batch_id)

    students = list(students_qs)
    if payment_filter == "Paid":
        students = [student for student in students if student.remaining_fee == 0 and student.course_fee]
    elif payment_filter == "Pending":
        students = [student for student in students if student.total_paid == 0]
    elif payment_filter == "Partial":
        students = [
            student for student in students if 0 < student.remaining_fee < (student.course_fee or 0)
        ]

    if sort_by == "name":
        students.sort(key=lambda student: (student.name or "").lower())
    elif sort_by == "pending_fee":
        students.sort(key=lambda student: (student.remaining_fee, (student.name or "").lower()), reverse=True)
    elif sort_by == "total_paid":
        students.sort(key=lambda student: (student.total_paid, (student.name or "").lower()), reverse=True)
    else:
        students.sort(key=lambda student: (student.joining_date or date.min, student.name or ""), reverse=True)

    return {
        "students": students,
        "query": query,
        "payment_filter": payment_filter,
        "student_status": student_status,
        "trainer_id": trainer_id,
        "center_id": center_id,
        "counsellor_id": counsellor_id,
        "batch_id": batch_id,
        "sort_by": sort_by,
        "trainers": scope_trainers_for_user(request.user, Trainer.objects.all()).order_by("name"),
        "centers": scope_centers_for_user(request.user, Center.objects.all()).order_by("name"),
        "counsellors": scope_counsellors_for_user(request.user, Counsellor.objects.select_related("center")).order_by("name"),
        "batches": scope_batches_for_user(request.user, Batch.objects.all()).order_by("time"),
        "status_choices": Student.STATUS_CHOICES,
        "total_records": len(students),
        "paid_count": sum(1 for student in students if student.payment_status == "Paid"),
        "partial_count": sum(1 for student in students if student.payment_status == "Partial"),
        "pending_count": sum(1 for student in students if student.payment_status == "Pending"),
        "pending_fee_total": sum(student.remaining_fee for student in students),
        "can_manage_fees": user_can_manage_fees(request.user),
    }


def build_pending_fee_context(request):
    query = request.GET.get("q", "").strip()
    center_id = request.GET.get("center", "").strip()
    trainer_id = request.GET.get("trainer", "").strip()
    counsellor_id = request.GET.get("counsellor", "").strip()
    pending_type = request.GET.get("pending_type", "").strip()

    students_qs = scope_students_for_user(
        request.user,
        Student.objects.select_related(
        "center", "trainer", "counsellor", "batch"
        ).prefetch_related("courses"),
    )

    if query:
        students_qs = students_qs.filter(
            Q(student_id__icontains=query)
            | Q(name__icontains=query)
            | Q(mobile_no__icontains=query)
            | Q(courses__name__icontains=query)
            | Q(center__name__icontains=query)
        ).distinct()
    if center_id:
        students_qs = students_qs.filter(center_id=center_id)
    if trainer_id:
        students_qs = students_qs.filter(trainer_id=trainer_id)
    if counsellor_id:
        students_qs = students_qs.filter(counsellor_id=counsellor_id)

    students = [student for student in students_qs if student.remaining_fee > 0]
    if pending_type == "no_payment":
        students = [student for student in students if student.total_paid == 0]
    elif pending_type == "partial":
        students = [student for student in students if student.total_paid > 0]

    students.sort(key=lambda student: (student.remaining_fee, (student.name or "").lower()), reverse=True)

    return {
        "students": students,
        "query": query,
        "center_id": center_id,
        "trainer_id": trainer_id,
        "counsellor_id": counsellor_id,
        "pending_type": pending_type,
        "centers": scope_centers_for_user(request.user, Center.objects.all()).order_by("name"),
        "trainers": scope_trainers_for_user(request.user, Trainer.objects.all()).order_by("name"),
        "counsellors": scope_counsellors_for_user(request.user, Counsellor.objects.select_related("center")).order_by("name"),
        "total_students": len(students),
        "pending_fee_total": sum(student.remaining_fee for student in students),
        "full_pending_count": sum(1 for student in students if student.total_paid == 0),
        "partial_pending_count": sum(1 for student in students if student.total_paid > 0),
        "can_manage_fees": user_can_manage_fees(request.user),
    }


def write_csv_response(filename, headers, rows):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return response


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR)
def student_registration(request):
    context = student_form_options(request)
    if request.method == "POST":
        mobile_no = (request.POST.get("mobile_no") or "").strip()
        duplicate_error = validate_student_mobile_for_registration(mobile_no)
        if duplicate_error:
            messages.error(request, duplicate_error)
            return render(request, "student/student-registration.html", context)

        role = get_portal_role(request.user)
        counsellor_id = request.POST.get("counsellor") or None
        center_id = request.POST.get("center") or None
        if role == ROLE_COUNSELLOR and hasattr(request.user, "counsellor_profile"):
            counsellor_id = request.user.counsellor_profile.id
            center_id = request.user.counsellor_profile.center_id

        student = Student.objects.create(
            name=request.POST.get("name"),
            mobile_no=mobile_no,
            alt_mobile_no=request.POST.get("alt_mobile_no"),
            guardian_name=request.POST.get("guardian_name"),
            guardian_mobile=request.POST.get("guardian_mobile"),
            email=request.POST.get("email"),
            qualification=request.POST.get("qualification"),
            address=request.POST.get("address"),
            reference_source=request.POST.get("reference_source"),
            dob=request.POST.get("dob"),
            joining_date=request.POST.get("joining_date"),
            counsellor_id=counsellor_id,
            course_fee=request.POST.get("course_fee") if user_can_manage_fees(request.user) else None,
            paid_fee=request.POST.get("paid_fee") if user_can_manage_fees(request.user) else None,
            trainer_id=request.POST.get("trainer"),
            batch_id=request.POST.get("batch"),
            center_id=center_id,
            status=request.POST.get("status") or "active",
        )
        student.courses.set(request.POST.getlist("courses"))
        messages.success(request, "Student updated successfully")
        return redirect("student_detail", id=student.id)
    return render(request, "student/student-registration.html", context)


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR, ROLE_TRAINER)
def record(request):
    return render(request, "student/record.html", build_student_record_context(request))


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR, ROLE_TRAINER)
def student_detail(request, id):
    student = get_student_for_user_or_404(
        request.user,
        id,
        Student.objects.prefetch_related(
            Prefetch(
                "sms_logs",
                queryset=SmsLog.objects.select_related(
                    "exam_registration__student_course__course"
                ).order_by("-created_at"),
            )
        ),
    )
    trainers = scope_trainers_for_user(request.user, Trainer.objects.all()).order_by("name")
    batches = scope_batches_for_user(request.user, Batch.objects.all()).order_by("time")
    centers = scope_centers_for_user(request.user, Center.objects.all()).order_by("name")
    today = date.today()

    attendance_dict = {item.student_id: item.status for item in Attendance.objects.filter(date=today)}
    attendance = Attendance.objects.filter(student=student).order_by("-date")
    attendance_map = {
        record.date: record.status
        for record in Attendance.objects.filter(student=student, date__year=today.year, date__month=today.month)
    }
    attendance_calendar = []
    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(today.year, today.month):
        attendance_calendar.append(
            [
                {
                    "day": day,
                    "in_month": day.month == today.month,
                    "status": attendance_map.get(day),
                }
                for day in week
            ]
        )

    exam_registrations = []
    if user_can_view_exams(request.user):
        exam_registrations = ExamRegistration.objects.select_related(
            "student_course__course", "receipt_issued_by"
        ).prefetch_related(
            Prefetch("sms_logs", queryset=SmsLog.objects.order_by("-created_at"))
        ).filter(student_course__student=student)

    if request.method == "POST":
        role = get_portal_role(request.user)
        if role in {ROLE_ADMIN, ROLE_COUNSELLOR}:
            student.trainer_id = request.POST.get("trainer") or None
            student.batch_id = request.POST.get("batch") or None
            student.center_id = request.POST.get("center") or None
        elif role == ROLE_TRAINER:
            student.batch_id = request.POST.get("batch") or None
        else:
            raise PermissionDenied("You cannot update this student.")
        student.save()
        return JsonResponse({"status": "success"})

    return render(
        request,
        "student/student_detail.html",
        {
            "student": student,
            "trainers": trainers,
            "batches": batches,
            "centers": centers,
            "attendance_dict": attendance_dict,
            "attendance": attendance,
            "attendance_calendar": attendance_calendar,
            "calendar_month_label": today.strftime("%B %Y"),
            "exam_registrations": exam_registrations,
            "show_student_nav": True,
            "can_manage_fees": user_can_manage_fees(request.user),
            "can_view_exams": user_can_view_exams(request.user),
            "can_edit_student": True,
        },
    )


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR, ROLE_TRAINER)
def update_student(request, id):
    student = get_student_for_user_or_404(request.user, id)
    if request.method == "POST":
        apply_student_update_from_request(student, request)
        student.save()

        selected_courses = list(set(request.POST.getlist("courses")))
        StudentCourse.objects.filter(student=student).exclude(course_id__in=selected_courses).delete()
        for course_id in selected_courses:
            is_completed = request.POST.get(f"completed_{course_id}") == "on"
            completion_date = request.POST.get(f"date_{course_id}") or None
            if is_completed and not completion_date:
                completion_date = date.today()
            StudentCourse.objects.update_or_create(
                student=student,
                course_id=course_id,
                defaults={"is_completed": is_completed, "completion_date": completion_date},
            )
        return redirect("student_detail", id=student.id)

    return render(
        request,
        "student/student_update.html",
        {
            "student": student,
            **student_form_options(request),
            "show_student_nav": True,
        },
    )


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR)
def add_installment(request, student_id):
    student = get_student_for_user_or_404(request.user, student_id)
    last_installment = Installment.objects.filter(student=student).order_by("-installment_no").first()
    next_installment_no = 1 if last_installment is None else last_installment.installment_no + 1

    if request.method == "POST":
        Installment.objects.create(
            student=student,
            installment_no=next_installment_no,
            installment_date=request.POST.get("installment_date"),
            amount=request.POST.get("amount"),
            payment_mode=request.POST.get("payment_mode") or "cash",
            transaction_id=request.POST.get("transaction_id"),
            remarks=request.POST.get("remarks"),
        )
        return redirect("student_detail", id=student.id)

    return render(
        request,
        "installment/installment_add.html",
        {
            "student": student,
            "next_installment_no": next_installment_no,
            "payment_mode_choices": Installment.PAYMENT_MODE_CHOICES,
            "installment": None,
            "form_mode": "add",
            "show_student_nav": True,
        },
    )


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR)
def edit_installment(request, installment_id):
    installment = get_object_or_404(Installment, id=installment_id)
    student = installment.student
    get_student_for_user_or_404(request.user, student.id)

    if request.method == "POST":
        installment.installment_date = request.POST.get("installment_date")
        installment.amount = request.POST.get("amount")
        installment.payment_mode = request.POST.get("payment_mode") or "cash"
        installment.transaction_id = request.POST.get("transaction_id")
        installment.remarks = request.POST.get("remarks")
        installment.save()
        messages.success(request, "Installment updated successfully.")
        return redirect("student_detail", id=student.id)

    return render(
        request,
        "installment/installment_add.html",
        {
            "student": student,
            "next_installment_no": installment.installment_no,
            "payment_mode_choices": Installment.PAYMENT_MODE_CHOICES,
            "installment": installment,
            "form_mode": "edit",
            "show_student_nav": True,
        },
    )


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR)
@require_POST
def delete_installment(request, installment_id):
    installment = get_object_or_404(Installment, id=installment_id)
    student_id = installment.student_id
    get_student_for_user_or_404(request.user, student_id)
    installment.delete()
    messages.success(request, "Installment deleted successfully.")
    return redirect("student_detail", id=student_id)


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR)
def today_collection_dashboard(request):
    today = date.today()
    center_id = request.GET.get("center", "").strip()

    admission_students_qs = scope_students_for_user(
        request.user,
        Student.objects.select_related("center").prefetch_related("courses").filter(
            joining_date=today,
            paid_fee__gt=0,
        ),
    )
    installments_qs = Installment.objects.select_related("student__center").prefetch_related("student__courses").filter(
        installment_date=today
    )
    allowed_student_ids = scope_students_for_user(request.user, Student.objects.all()).values_list("id", flat=True)
    installments_qs = installments_qs.filter(student_id__in=allowed_student_ids)

    if center_id:
        admission_students_qs = admission_students_qs.filter(center_id=center_id)
        installments_qs = installments_qs.filter(student__center_id=center_id)

    collection_rows = []
    for student in admission_students_qs.order_by("name"):
        collection_rows.append(
            {
                "kind": "Admission",
                "student": student,
                "receipt_kind": "admission",
                "center_name": student.center.name if student.center else "-",
                "courses": ", ".join(course.name for course in student.courses.all()) or "-",
                "amount": student.paid_fee or 0,
                "payment_mode": "Admission",
                "reference": "-",
                "remarks": "Admission paid fee",
            }
        )

    for installment in installments_qs.order_by("-installment_no", "student__name"):
        collection_rows.append(
            {
                "kind": f"Installment {installment.installment_no}",
                "student": installment.student,
                "receipt_kind": "installment",
                "installment_id": installment.id,
                "center_name": installment.student.center.name if installment.student.center else "-",
                "courses": ", ".join(course.name for course in installment.student.courses.all()) or "-",
                "amount": installment.amount or 0,
                "payment_mode": installment.get_payment_mode_display(),
                "reference": installment.transaction_id or "-",
                "remarks": installment.remarks or "-",
            }
        )

    collection_rows.sort(key=lambda row: ((row["student"].name or "").lower(), row["kind"]))

    center_totals = {}
    for row in collection_rows:
        center_totals[row["center_name"]] = center_totals.get(row["center_name"], 0) + row["amount"]

    return render(
        request,
        "student/today_collection_dashboard.html",
        {
            "today": today,
            "collection_rows": collection_rows,
            "total_collection": sum(row["amount"] for row in collection_rows),
            "admission_collection_total": sum(student.paid_fee or 0 for student in admission_students_qs),
            "installment_collection_total": installments_qs.aggregate(total=Sum("amount"))["total"] or 0,
            "collection_count": len(collection_rows),
            "center_totals": sorted(center_totals.items()),
            "center_id": center_id,
            "centers": scope_centers_for_user(request.user, Center.objects.all()).order_by("name"),
        },
    )


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR, ROLE_TRAINER)
def pending_fee_list(request):
    return render(request, "student/pending_fee_list.html", build_pending_fee_context(request))


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR)
def daily_admissions_report(request):
    today = date.today()
    center_id = request.GET.get("center", "").strip()
    counsellor_id = request.GET.get("counsellor", "").strip()

    students_qs = scope_students_for_user(
        request.user,
        Student.objects.select_related(
        "center", "trainer", "counsellor", "batch"
        ).prefetch_related("courses").filter(joining_date=today),
    )

    if center_id:
        students_qs = students_qs.filter(center_id=center_id)
    if counsellor_id:
        students_qs = students_qs.filter(counsellor_id=counsellor_id)

    students = list(students_qs.order_by("name"))

    return render(
        request,
        "student/daily_admissions_report.html",
        {
            "today": today,
            "students": students,
            "center_id": center_id,
            "counsellor_id": counsellor_id,
            "centers": scope_centers_for_user(request.user, Center.objects.all()).order_by("name"),
            "counsellors": scope_counsellors_for_user(request.user, Counsellor.objects.select_related("center")).order_by("name"),
            "total_students": len(students),
            "admission_collection_total": sum(student.paid_fee or 0 for student in students),
        },
    )


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR)
def reporting_dashboard(request):
    today = date.today()
    date_from_value = request.GET.get("date_from", "").strip()
    date_to_value = request.GET.get("date_to", "").strip()
    center_id = request.GET.get("center", "").strip()
    course_id = request.GET.get("course", "").strip()
    counsellor_id = request.GET.get("counsellor", "").strip()
    trainer_id = request.GET.get("trainer", "").strip()

    date_from = parse_report_date(date_from_value) or today.replace(day=1)
    date_to = parse_report_date(date_to_value) or today
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    students_qs = scope_students_for_user(
        request.user,
        Student.objects.select_related(
        "center", "trainer", "counsellor", "batch"
        ).prefetch_related("courses").filter(joining_date__range=(date_from, date_to)),
    )
    enquiries_qs = scope_enquiries_for_user(
        request.user,
        Enquiry.objects.select_related(
        "preferred_center", "interested_course", "assigned_counsellor"
        ).filter(enquiry_date__range=(date_from, date_to)),
    )
    converted_enquiries_qs = scope_enquiries_for_user(
        request.user,
        Enquiry.objects.select_related(
        "preferred_center", "interested_course", "assigned_counsellor"
        ).filter(converted_at__range=(date_from, date_to)),
    )
    installments_qs = Installment.objects.select_related(
        "student__center", "student__trainer", "student__counsellor"
    ).prefetch_related("student__courses").filter(installment_date__range=(date_from, date_to))
    installments_qs = installments_qs.filter(student_id__in=students_qs.values_list("id", flat=True))

    if center_id:
        students_qs = students_qs.filter(center_id=center_id)
        enquiries_qs = enquiries_qs.filter(preferred_center_id=center_id)
        converted_enquiries_qs = converted_enquiries_qs.filter(preferred_center_id=center_id)
        installments_qs = installments_qs.filter(student__center_id=center_id)
    if course_id:
        students_qs = students_qs.filter(courses__id=course_id).distinct()
        enquiries_qs = enquiries_qs.filter(interested_course_id=course_id)
        converted_enquiries_qs = converted_enquiries_qs.filter(interested_course_id=course_id)
        installments_qs = installments_qs.filter(student__courses__id=course_id).distinct()
    if counsellor_id:
        students_qs = students_qs.filter(counsellor_id=counsellor_id)
        enquiries_qs = enquiries_qs.filter(assigned_counsellor_id=counsellor_id)
        converted_enquiries_qs = converted_enquiries_qs.filter(assigned_counsellor_id=counsellor_id)
        installments_qs = installments_qs.filter(student__counsellor_id=counsellor_id)
    if trainer_id:
        students_qs = students_qs.filter(trainer_id=trainer_id)
        installments_qs = installments_qs.filter(student__trainer_id=trainer_id)

    students = list(students_qs)
    enquiries = list(enquiries_qs)
    converted_enquiries = list(converted_enquiries_qs)
    installments = list(installments_qs)

    student_ids = {student.id for student in students}
    center_rows = []
    for center in Center.objects.order_by("name"):
        center_students = [student for student in students if student.center_id == center.id]
        center_enquiries = [enquiry for enquiry in enquiries if enquiry.preferred_center_id == center.id]
        center_conversions = [enquiry for enquiry in converted_enquiries if enquiry.preferred_center_id == center.id]
        center_installments = [installment for installment in installments if installment.student.center_id == center.id]
        admission_collection = sum(student.paid_fee or 0 for student in center_students)
        installment_collection = sum(installment.amount or 0 for installment in center_installments)
        if center_students or center_enquiries or center_installments or center_conversions:
            center_rows.append(
                {
                    "name": center.name,
                    "admissions": len(center_students),
                    "enquiries": len(center_enquiries),
                    "conversions": len(center_conversions),
                    "collection": admission_collection + installment_collection,
                    "pending_fee": sum(student.remaining_fee for student in center_students),
                }
            )

    course_rows = []
    for course in Course.objects.order_by("name"):
        course_students = [student for student in students if any(student_course.id == course.id for student_course in student.courses.all())]
        course_student_ids = {student.id for student in course_students}
        course_enquiries = [enquiry for enquiry in enquiries if enquiry.interested_course_id == course.id]
        course_conversions = [enquiry for enquiry in converted_enquiries if enquiry.interested_course_id == course.id]
        course_installments = [installment for installment in installments if installment.student_id in course_student_ids]
        if course_students or course_enquiries or course_installments or course_conversions:
            course_rows.append(
                {
                    "name": course.name,
                    "students": len(course_students),
                    "enquiries": len(course_enquiries),
                    "conversions": len(course_conversions),
                    "collection": sum(student.paid_fee or 0 for student in course_students) + sum(installment.amount or 0 for installment in course_installments),
                    "pending_fee": sum(student.remaining_fee for student in course_students),
                }
            )

    trainer_rows = []
    for trainer in Trainer.objects.order_by("name"):
        trainer_students = [student for student in students if student.trainer_id == trainer.id]
        trainer_installments = [installment for installment in installments if installment.student.trainer_id == trainer.id]
        if trainer_students or trainer_installments:
            trainer_rows.append(
                {
                    "name": trainer.name,
                    "students": len(trainer_students),
                    "active_students": sum(1 for student in trainer_students if student.status == "active"),
                    "collection": sum(student.paid_fee or 0 for student in trainer_students) + sum(installment.amount or 0 for installment in trainer_installments),
                    "pending_fee": sum(student.remaining_fee for student in trainer_students),
                }
            )

    counsellor_rows = []
    for counsellor in Counsellor.objects.select_related("center").all():
        counsellor_students = [student for student in students if student.counsellor_id == counsellor.id]
        counsellor_enquiries = [enquiry for enquiry in enquiries if enquiry.assigned_counsellor_id == counsellor.id]
        counsellor_conversions = [enquiry for enquiry in converted_enquiries if enquiry.assigned_counsellor_id == counsellor.id]
        if counsellor_students or counsellor_enquiries or counsellor_conversions:
            counsellor_rows.append(
                {
                    "name": counsellor.name,
                    "center_name": counsellor.center.name if counsellor.center else "-",
                    "enquiries": len(counsellor_enquiries),
                    "admissions": len(counsellor_students),
                    "conversions": len(counsellor_conversions),
                    "collection": sum(student.paid_fee or 0 for student in counsellor_students),
                }
            )

    context = {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "center_id": center_id,
        "course_id": course_id,
        "counsellor_id": counsellor_id,
        "trainer_id": trainer_id,
        "centers": scope_centers_for_user(request.user, Center.objects.all()).order_by("name"),
        "courses": Course.objects.order_by("name"),
        "counsellors": scope_counsellors_for_user(request.user, Counsellor.objects.select_related("center")).order_by("name"),
        "trainers": scope_trainers_for_user(request.user, Trainer.objects.all()).order_by("name"),
        "total_admissions": len(students),
        "total_enquiries": len(enquiries),
        "total_conversions": len(converted_enquiries),
        "admission_collection_total": sum(student.paid_fee or 0 for student in students),
        "installment_collection_total": sum(installment.amount or 0 for installment in installments),
        "pending_fee_total": sum(student.remaining_fee for student in students),
        "center_rows": center_rows,
        "course_rows": course_rows,
        "trainer_rows": trainer_rows,
        "counsellor_rows": counsellor_rows,
    }
    context["total_collection"] = context["admission_collection_total"] + context["installment_collection_total"]
    context["conversion_rate"] = round((context["total_conversions"] / context["total_enquiries"]) * 100, 2) if context["total_enquiries"] else 0
    return render(request, "student/reporting_dashboard.html", context)


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR)
def export_student_records_csv(request):
    context = build_student_record_context(request)
    return write_csv_response(
        "student-records.csv",
        ["Student ID", "Student Name", "Mobile", "Center", "Trainer", "Counsellor", "Batch", "Courses", "Status", "Total Fee", "Total Paid", "Pending Fee", "Payment Status", "Joining Date"],
        [
            [
                student.student_id,
                student.name,
                student.mobile_no,
                student.center.name if student.center else "-",
                student.trainer.name if student.trainer else "-",
                student.counsellor.name if student.counsellor else "-",
                str(student.batch) if student.batch else "-",
                serialize_student_courses(student),
                student.get_status_display(),
                student.course_fee or 0,
                student.total_paid,
                student.remaining_fee,
                student.payment_status,
                student.joining_date or "-",
            ]
            for student in context["students"]
        ],
    )


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR)
def export_pending_fees_csv(request):
    context = build_pending_fee_context(request)
    return write_csv_response(
        "pending-fee-list.csv",
        ["Student ID", "Student Name", "Mobile", "Center", "Trainer", "Counsellor", "Courses", "Total Fee", "Paid", "Pending Fee", "Payment Status"],
        [
            [
                student.student_id,
                student.name,
                student.mobile_no,
                student.center.name if student.center else "-",
                student.trainer.name if student.trainer else "-",
                student.counsellor.name if student.counsellor else "-",
                serialize_student_courses(student),
                student.course_fee or 0,
                student.total_paid,
                student.remaining_fee,
                student.payment_status,
            ]
            for student in context["students"]
        ],
    )


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR)
def export_today_collection_csv(request):
    today = date.today()
    center_id = request.GET.get("center", "").strip()

    admission_students_qs = Student.objects.select_related("center").prefetch_related("courses").filter(
        joining_date=today,
        paid_fee__gt=0,
    )
    installments_qs = Installment.objects.select_related("student__center").prefetch_related("student__courses").filter(
        installment_date=today
    )
    if center_id:
        admission_students_qs = admission_students_qs.filter(center_id=center_id)
        installments_qs = installments_qs.filter(student__center_id=center_id)

    rows = []
    for student in admission_students_qs.order_by("name"):
        rows.append(
            [
                "Admission",
                student.student_id,
                student.name,
                student.center.name if student.center else "-",
                serialize_student_courses(student),
                student.paid_fee or 0,
                "Admission",
                "-",
                "Admission paid fee",
            ]
        )
    for installment in installments_qs.order_by("-installment_no", "student__name"):
        rows.append(
            [
                f"Installment {installment.installment_no}",
                installment.student.student_id,
                installment.student.name,
                installment.student.center.name if installment.student.center else "-",
                serialize_student_courses(installment.student),
                installment.amount or 0,
                installment.get_payment_mode_display(),
                installment.transaction_id or "-",
                installment.remarks or "-",
            ]
        )
    return write_csv_response(
        "today-collection-report.csv",
        ["Type", "Student ID", "Student Name", "Center", "Courses", "Amount", "Payment Mode", "Reference", "Remarks"],
        rows,
    )


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR)
def export_daily_admissions_csv(request):
    today = date.today()
    center_id = request.GET.get("center", "").strip()
    counsellor_id = request.GET.get("counsellor", "").strip()

    students_qs = Student.objects.select_related(
        "center", "trainer", "counsellor", "batch"
    ).prefetch_related("courses").filter(joining_date=today)
    if center_id:
        students_qs = students_qs.filter(center_id=center_id)
    if counsellor_id:
        students_qs = students_qs.filter(counsellor_id=counsellor_id)

    students = list(students_qs.order_by("name"))
    return write_csv_response(
        "daily-admissions-report.csv",
        ["Student ID", "Student Name", "Mobile", "Center", "Trainer", "Counsellor", "Batch", "Courses", "Admission Fee", "Total Fee", "Joining Date"],
        [
            [
                student.student_id,
                student.name,
                student.mobile_no,
                student.center.name if student.center else "-",
                student.trainer.name if student.trainer else "-",
                student.counsellor.name if student.counsellor else "-",
                str(student.batch) if student.batch else "-",
                serialize_student_courses(student),
                student.paid_fee or 0,
                student.course_fee or 0,
                student.joining_date or "-",
            ]
            for student in students
        ],
    )


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR)
def admission_receipt(request, student_id):
    student = get_student_for_user_or_404(
        request.user,
        student_id,
        Student.objects.select_related("center", "trainer", "counsellor", "batch").prefetch_related("courses"),
    )
    return render(
        request,
        "student/admission_receipt.html",
        {
            "student": student,
            "receipt_date": student.joining_date or date.today(),
            "receipt_amount": student.paid_fee or 0,
            "show_student_nav": True,
        },
    )


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR)
def installment_receipt(request, installment_id):
    installment = get_object_or_404(
        Installment.objects.select_related("student__center", "student__trainer", "student__counsellor", "student__batch").prefetch_related("student__courses"),
        id=installment_id,
    )
    get_student_for_user_or_404(request.user, installment.student_id)
    return render(
        request,
        "installment/installment_receipt.html",
        {
            "installment": installment,
            "student": installment.student,
            "receipt_date": installment.installment_date,
            "receipt_amount": installment.amount,
            "show_student_nav": True,
        },
    )


@role_required(ROLE_ADMIN, ROLE_TRAINER)
def trainer_batches(request, trainer_id):
    trainer = get_object_or_404(scope_trainers_for_user(request.user, Trainer.objects.all()), id=trainer_id)
    batches = Batch.objects.filter(trainerschedule__trainer=trainer).distinct().order_by("time")
    return render(request, "attendance/batch_list.html", {"trainer": trainer, "batches": batches})


@role_required(ROLE_ADMIN, ROLE_TRAINER)
def batch_students(request, batch_id):
    batch = get_object_or_404(scope_batches_for_user(request.user, Batch.objects.all()), id=batch_id)
    students = scope_students_for_user(request.user, Student.objects.filter(batch=batch))
    today = date.today()
    attendance_map = {item.student_id: item.status for item in Attendance.objects.filter(date=today)}

    if request.method == "POST":
        for student in students:
            status = request.POST.get(f"status_{student.id}")
            if status:
                Attendance.objects.update_or_create(
                    student=student,
                    date=today,
                    defaults={"status": status},
                )
        return redirect(request.path)

    return render(
        request,
        "attendance/batch_students.html",
        {"batch": batch, "students": students, "attendance_map": attendance_map, "today": today},
    )


def validate_student_mobile_for_registration(mobile_no):
    normalized_target = normalize_mobile_number(mobile_no)
    if not normalized_target:
        return None

    for student in Student.objects.all():
        if normalize_mobile_number(student.mobile_no) == normalized_target:
            return f"A student already exists with this mobile number: {student.name} ({student.student_id})."

    for enquiry in Enquiry.objects.filter(converted_student__isnull=True):
        if normalize_mobile_number(enquiry.mobile_no) == normalized_target:
            return f"An active enquiry already exists with this mobile number: {enquiry.name}. Convert that enquiry instead of creating a duplicate student."
    return None


def normalize_mobile_number(value):
    digits = re.sub(r"\D", "", value or "")
    if len(digits) >= 10:
        return digits[-10:]
    return digits
