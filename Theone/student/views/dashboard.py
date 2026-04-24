from datetime import date

from django.shortcuts import render

from student.models import Attendance, Batch, Center, Student, Trainer


def index(request):
    students = Student.objects.all()
    trainers = Trainer.objects.all()
    batches = Batch.objects.all()
    centers = Center.objects.all()

    total_students_count = students.count()
    active_students = students.filter(status="active").count()
    pending_fees = sum(student.remaining_fee for student in students if student.remaining_fee > 0)

    today = date.today()
    context = {
        "total_students": total_students_count,
        "active_students": active_students,
        "pending_fees": pending_fees,
        "trainers_count": trainers.count(),
        "centers_count": centers.count(),
        "batches_count": batches.count(),
        "today": today,
        "present_count": Attendance.objects.filter(date=today, status="present").count(),
        "absent_count": Attendance.objects.filter(date=today, status="absent").count(),
        "leave_count": Attendance.objects.filter(date=today, status="leave").count(),
        "recent_students": students.order_by("-joining_date")[:5],
    }
    return render(request, "index.html", context)

