from collections import OrderedDict
from datetime import date, datetime

from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from student.models import Attendance, Batch, Center, CenterLogistics, Student, Trainer


def attendance_batches(request):
    search_query = request.GET.get("q", "").strip()
    batch_data = []
    centers = list(Center.objects.all().order_by("name"))

    for batch in Batch.objects.all().order_by("time"):
        batch_label = str(batch)
        center_rows = []
        total_students = 0
        total_capacity = 0
        trainer_names_for_batch = set()

        for center in centers:
            center_students = Student.objects.select_related("trainer").filter(batch=batch, center=center)
            student_count = center_students.count()
            logistics = CenterLogistics.objects.filter(center=center).first()
            capacity = logistics.total_capacity if logistics else 0
            available = max(capacity - student_count, 0)
            trainer_names = sorted(
                {
                    student.trainer.name
                    for student in center_students
                    if student.trainer and student.trainer.name
                }
            )
            trainer_names_for_batch.update(trainer_names)

            center_rows.append(
                {
                    "id": center.id,
                    "name": center.name,
                    "students": student_count,
                    "capacity": capacity,
                    "available": available,
                    "trainer_names": trainer_names,
                }
            )
            total_students += student_count
            total_capacity += capacity

        if search_query:
            normalized_query = search_query.lower()
            batch_matches = normalized_query in batch_label.lower()
            trainer_matches = any(normalized_query in trainer_name.lower() for trainer_name in trainer_names_for_batch)
            if not batch_matches and not trainer_matches:
                continue

        batch_data.append(
            {
                "batch": batch,
                "batch_label": batch_label,
                "total_students": total_students,
                "total_capacity": total_capacity,
                "total_available": max(total_capacity - total_students, 0),
                "centers": center_rows,
                "trainer_names": sorted(trainer_names_for_batch),
            }
        )

    return render(
        request,
        "attendance/batches.html",
        {"batch_data": batch_data, "today": date.today(), "search_query": search_query},
    )


def attendance_batch_detail(request, batch_id):
    batch = get_object_or_404(Batch, id=batch_id)
    selected_date = parse_selected_date(request.GET.get("date"))
    trainer_filter = request.GET.get("trainer", "").strip()

    students_qs = Student.objects.select_related("trainer", "center", "batch").filter(batch=batch)
    if trainer_filter:
        students_qs = students_qs.filter(trainer_id=trainer_filter)
    students = list(students_qs.order_by("center__name", "trainer__name", "name"))

    attendance_map = {
        record.student_id: record
        for record in Attendance.objects.filter(student__in=students, date=selected_date)
    }

    grouped_data = OrderedDict()
    present_count = 0
    absent_count = 0
    leave_count = 0

    for student in students:
        center_name = student.center.name if student.center else "No Center"
        trainer_name = student.trainer.name if student.trainer else "No Trainer"
        center_bucket = grouped_data.setdefault(
            center_name,
            {"center_name": center_name, "trainers": OrderedDict(), "total_students": 0, "present_count": 0},
        )
        trainer_bucket = center_bucket["trainers"].setdefault(
            trainer_name,
            {
                "trainer": student.trainer,
                "trainer_name": trainer_name,
                "students": [],
                "total_students": 0,
                "present_count": 0,
            },
        )

        attendance_record = attendance_map.get(student.id)
        current_status = attendance_record.status if attendance_record else ""
        if current_status == "present":
            present_count += 1
            center_bucket["present_count"] += 1
            trainer_bucket["present_count"] += 1
        elif current_status == "absent":
            absent_count += 1
        elif current_status == "leave":
            leave_count += 1

        trainer_bucket["students"].append(
            {
                "student": student,
                "status": current_status,
                "remarks": attendance_record.remarks if attendance_record else "",
            }
        )
        trainer_bucket["total_students"] += 1
        center_bucket["total_students"] += 1

    grouped_list = []
    for center_bucket in grouped_data.values():
        center_bucket["trainers"] = list(center_bucket["trainers"].values())
        grouped_list.append(center_bucket)

    context = {
        "batch": batch,
        "selected_date": selected_date,
        "grouped_data": grouped_list,
        "total_students": len(students),
        "present_count": present_count,
        "absent_count": absent_count,
        "leave_count": leave_count,
        "unmarked_count": max(len(students) - present_count - absent_count - leave_count, 0),
        "trainer_filter": trainer_filter,
        "trainers": Trainer.objects.filter(student__batch=batch).distinct().order_by("name"),
    }
    return render(request, "attendance/batch_detail.html", context)


def mark_attendance(request, trainer_id, batch_id):
    base_url = reverse("attendance_batch_detail", args=[batch_id])
    return redirect(f"{base_url}?trainer={trainer_id}")


@require_POST
def save_attendance_record(request, student_id):
    student = get_object_or_404(Student.objects.select_related("batch"), id=student_id)
    selected_date = parse_selected_date(request.POST.get("date"))
    status = (request.POST.get("status") or "").strip().lower()
    remarks = (request.POST.get("remarks") or "").strip()

    valid_statuses = {choice[0] for choice in Attendance.STATUS_CHOICES}
    if status not in valid_statuses:
        return JsonResponse({"status": "error", "message": "Invalid attendance status."}, status=400)

    attendance, _ = Attendance.objects.update_or_create(
        student=student,
        date=selected_date,
        defaults={"status": status, "remarks": remarks or None},
    )
    return JsonResponse(
        {
            "status": "success",
            "student_id": student.id,
            "attendance_status": attendance.status,
            "remarks": attendance.remarks or "",
            "date": selected_date.isoformat(),
        }
    )


def parse_selected_date(raw_date):
    if raw_date:
        try:
            return datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            pass
    return date.today()


def daily_absentees(request):
    selected_date = parse_selected_date(request.GET.get("date"))
    center_id = request.GET.get("center", "").strip()
    batch_id = request.GET.get("batch", "").strip()

    records_qs = Attendance.objects.select_related(
        "student__center", "student__batch", "student__trainer"
    ).filter(date=selected_date, status="absent")
    if center_id:
        records_qs = records_qs.filter(student__center_id=center_id)
    if batch_id:
        records_qs = records_qs.filter(student__batch_id=batch_id)

    records = list(records_qs.order_by("student__center__name", "student__batch__time", "student__name"))
    return render(
        request,
        "attendance/daily_absentees.html",
        {
            "selected_date": selected_date,
            "records": records,
            "center_id": center_id,
            "batch_id": batch_id,
            "centers": Center.objects.all().order_by("name"),
            "batches": Batch.objects.all().order_by("time"),
            "total_absentees": len(records),
        },
    )


def attendance_monthly_summary(request):
    today = date.today()
    month_value = request.GET.get("month", "").strip()
    center_id = request.GET.get("center", "").strip()
    batch_id = request.GET.get("batch", "").strip()

    try:
        selected_month = datetime.strptime(month_value, "%Y-%m").date() if month_value else today.replace(day=1)
    except ValueError:
        selected_month = today.replace(day=1)

    students_qs = Student.objects.select_related("center", "batch", "trainer").all()
    if center_id:
        students_qs = students_qs.filter(center_id=center_id)
    if batch_id:
        students_qs = students_qs.filter(batch_id=batch_id)
    students = list(students_qs.order_by("center__name", "batch__time", "name"))

    attendance_records = Attendance.objects.filter(
        student__in=students,
        date__year=selected_month.year,
        date__month=selected_month.month,
    )
    attendance_map = {}
    for record in attendance_records:
        bucket = attendance_map.setdefault(record.student_id, {"present": 0, "absent": 0, "leave": 0})
        bucket[record.status] = bucket.get(record.status, 0) + 1

    summary_rows = []
    for student in students:
        counts = attendance_map.get(student.id, {"present": 0, "absent": 0, "leave": 0})
        total_marked = counts["present"] + counts["absent"] + counts["leave"]
        attendance_percentage = round((counts["present"] / total_marked) * 100, 2) if total_marked else 0
        summary_rows.append(
            {
                "student": student,
                "present": counts["present"],
                "absent": counts["absent"],
                "leave": counts["leave"],
                "total_marked": total_marked,
                "attendance_percentage": attendance_percentage,
            }
        )

    return render(
        request,
        "attendance/monthly_summary.html",
        {
            "selected_month": selected_month,
            "month_value": selected_month.strftime("%Y-%m"),
            "summary_rows": summary_rows,
            "center_id": center_id,
            "batch_id": batch_id,
            "centers": Center.objects.all().order_by("name"),
            "batches": Batch.objects.all().order_by("time"),
            "total_students": len(summary_rows),
        },
    )
