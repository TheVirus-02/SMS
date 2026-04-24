import calendar
from datetime import date
import re

from django.contrib import messages
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

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


def student_registration(request):
    context = {
        "courses": Course.objects.all(),
        "counsellors": Counsellor.objects.select_related("center").all(),
        "trainers": Trainer.objects.all(),
        "batches": Batch.objects.all(),
        "centers": Center.objects.all(),
        "status_choices": Student.STATUS_CHOICES,
    }
    if request.method == "POST":
        mobile_no = (request.POST.get("mobile_no") or "").strip()
        duplicate_error = validate_student_mobile_for_registration(mobile_no)
        if duplicate_error:
            messages.error(request, duplicate_error)
            return render(request, "student/student-registration.html", context)

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
            counsellor_id=request.POST.get("counsellor"),
            course_fee=request.POST.get("course_fee"),
            paid_fee=request.POST.get("paid_fee"),
            trainer_id=request.POST.get("trainer"),
            batch_id=request.POST.get("batch"),
            center_id=request.POST.get("center"),
            status=request.POST.get("status") or "active",
        )
        student.courses.set(request.POST.getlist("courses"))
        messages.success(request, "Student updated successfully")
        return redirect("student_detail", id=student.id)
    return render(request, "student/student-registration.html", context)


def record(request):
    students_qs = Student.objects.select_related(
        "counsellor", "trainer", "batch", "center"
    ).prefetch_related("courses")
    query = request.GET.get("q", "").strip()
    payment_filter = request.GET.get("payment_status", "").strip()
    student_status = request.GET.get("student_status", "").strip()
    trainer_id = request.GET.get("trainer", "").strip()
    center_id = request.GET.get("center", "").strip()

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

    students = list(students_qs)
    if payment_filter == "Paid":
        students = [student for student in students if student.remaining_fee == 0 and student.course_fee]
    elif payment_filter == "Pending":
        students = [student for student in students if student.total_paid == 0]
    elif payment_filter == "Partial":
        students = [
            student for student in students if 0 < student.remaining_fee < (student.course_fee or 0)
        ]

    return render(
        request,
        "student/record.html",
        {
            "students": students,
            "query": query,
            "payment_filter": payment_filter,
            "student_status": student_status,
            "trainer_id": trainer_id,
            "center_id": center_id,
            "trainers": Trainer.objects.all(),
            "centers": Center.objects.all(),
            "status_choices": Student.STATUS_CHOICES,
            "total_records": len(students),
            "paid_count": sum(1 for student in students if student.payment_status == "Paid"),
            "partial_count": sum(1 for student in students if student.payment_status == "Partial"),
            "pending_count": sum(1 for student in students if student.payment_status == "Pending"),
        },
    )


def student_detail(request, id):
    student = get_object_or_404(
        Student.objects.prefetch_related(
            Prefetch(
                "sms_logs",
                queryset=SmsLog.objects.select_related(
                    "exam_registration__student_course__course"
                ).order_by("-created_at"),
            )
        ),
        id=id,
    )
    trainers = Trainer.objects.all()
    batches = Batch.objects.all()
    centers = Center.objects.all()
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

    exam_registrations = ExamRegistration.objects.select_related(
        "student_course__course", "receipt_issued_by"
    ).prefetch_related(
        Prefetch("sms_logs", queryset=SmsLog.objects.order_by("-created_at"))
    ).filter(student_course__student=student)

    if request.method == "POST":
        student.trainer_id = request.POST.get("trainer")
        student.batch_id = request.POST.get("batch")
        student.center_id = request.POST.get("center")
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
        },
    )


def update_student(request, id):
    student = get_object_or_404(Student, id=id)
    if request.method == "POST":
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
        student.counsellor_id = request.POST.get("counsellor") or None
        student.trainer_id = request.POST.get("trainer")
        student.batch_id = request.POST.get("batch")
        student.center_id = request.POST.get("center")
        student.course_fee = request.POST.get("course_fee")
        student.paid_fee = request.POST.get("paid_fee")
        student.status = request.POST.get("status")
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
            "trainers": Trainer.objects.all(),
            "batches": Batch.objects.all(),
            "centers": Center.objects.all(),
            "courses": Course.objects.all(),
            "counsellors": Counsellor.objects.select_related("center").all(),
            "show_student_nav": True,
        },
    )


def add_installment(request, student_id):
    student = get_object_or_404(Student, id=student_id)
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
            "show_student_nav": True,
        },
    )


def trainer_batches(request, trainer_id):
    trainer = Trainer.objects.get(id=trainer_id)
    batches = Batch.objects.filter(trainerschedule__trainer=trainer).distinct().order_by("time")
    return render(request, "attendance/batch_list.html", {"trainer": trainer, "batches": batches})


def batch_students(request, batch_id):
    batch = Batch.objects.get(id=batch_id)
    students = Student.objects.filter(batch=batch)
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
