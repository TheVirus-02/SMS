from datetime import date, timedelta

from django.db.models import Sum
from django.shortcuts import redirect, render

from student.models import Attendance, Batch, Center, CommunicationLog, Course, Enquiry, Installment, Student, Trainer
from student.portal import ROLE_ADMIN, ROLE_COUNSELLOR, ROLE_TRAINER, get_portal_role, portal_login_required


@portal_login_required
def index(request):
    role = get_portal_role(request.user)
    if role == ROLE_COUNSELLOR:
        return redirect("counsellor_dashboard")
    if role == ROLE_TRAINER:
        return redirect("trainer_dashboard")

    today = date.today()
    students = Student.objects.select_related("center").prefetch_related("courses").all()
    trainers = Trainer.objects.all()
    batches = Batch.objects.all()
    centers = list(Center.objects.all())
    courses = Course.objects.order_by("name")
    enquiries = Enquiry.objects.select_related("preferred_center").all()

    name_query = request.GET.get("name", "").strip()
    course_query = request.GET.get("course", "").strip()

    search_results_qs = students
    if name_query:
        search_results_qs = search_results_qs.filter(name__icontains=name_query)
    if course_query:
        search_results_qs = search_results_qs.filter(courses__id=course_query)
    search_results = (
        search_results_qs.distinct().order_by("name")
        if name_query or course_query
        else []
    )

    total_students_count = students.count()
    active_students = students.filter(status="active").count()
    today_admissions = students.filter(joining_date=today).count()
    today_enquiries = enquiries.filter(enquiry_date=today).count()
    today_admission_collection = sum(student.paid_fee or 0 for student in students if student.joining_date == today)
    today_installment_collection = Installment.objects.filter(installment_date=today).aggregate(total=Sum("amount"))["total"] or 0
    today_collection_total = today_admission_collection + today_installment_collection
    pending_fee_students_count = sum(1 for student in students if student.remaining_fee > 0)
    today_follow_up_count = enquiries.filter(next_follow_up_date=today).exclude(status__in=["admitted", "lost"]).count()
    overdue_fee_alert_count = sum(
        1 for student in students if student.remaining_fee > 0 and student.joining_date and student.joining_date <= today - timedelta(days=30)
    )
    overdue_follow_up_alert_count = enquiries.filter(next_follow_up_date__lt=today).exclude(status__in=["admitted", "lost"]).count()
    stale_enquiry_alert_count = enquiries.exclude(status__in=["admitted", "lost"]).filter(updated_at__date__lte=today - timedelta(days=7)).count()
    recent_communication_logs = CommunicationLog.objects.select_related("student", "enquiry")[:5]

    preferred_center_order = ["Second Floor", "Ground Floor", "Royal Plaza"]
    center_order_map = {name.casefold(): index for index, name in enumerate(preferred_center_order)}
    ordered_centers = sorted(
        centers,
        key=lambda center: (center_order_map.get(center.name.casefold(), len(preferred_center_order)), center.name.casefold()),
    )

    center_summary_map = {}
    for center in ordered_centers:
        center_students = [student for student in students if student.center_id == center.id]
        center_summary_map[center.id] = {
            "center": center,
            "total_fee": sum(student.course_fee or 0 for student in center_students),
            "pending_fee": sum(student.remaining_fee for student in center_students),
            "collection_fee": sum(student.total_paid for student in center_students),
            "today_admissions": sum(1 for student in center_students if student.joining_date == today),
            "today_enquiries": enquiries.filter(preferred_center_id=center.id, enquiry_date=today).count(),
        }

    fee_summary_rows = [
        {
            "label": "Total Fee",
            "values": [center_summary_map[center.id]["total_fee"] for center in ordered_centers],
            "total": sum(center_summary_map[center.id]["total_fee"] for center in ordered_centers),
        },
        {
            "label": "Pending Fee",
            "values": [center_summary_map[center.id]["pending_fee"] for center in ordered_centers],
            "total": sum(center_summary_map[center.id]["pending_fee"] for center in ordered_centers),
        },
        {
            "label": "Collection Fee",
            "values": [center_summary_map[center.id]["collection_fee"] for center in ordered_centers],
            "total": sum(center_summary_map[center.id]["collection_fee"] for center in ordered_centers),
        },
        {
            "label": "Today's Admission",
            "values": [center_summary_map[center.id]["today_admissions"] for center in ordered_centers],
            "total": sum(center_summary_map[center.id]["today_admissions"] for center in ordered_centers),
        },
        {
            "label": "Today's Enquiry",
            "values": [center_summary_map[center.id]["today_enquiries"] for center in ordered_centers],
            "total": sum(center_summary_map[center.id]["today_enquiries"] for center in ordered_centers),
        },
    ]

    context = {
        "total_students": total_students_count,
        "active_students": active_students,
        "today_admissions": today_admissions,
        "today_enquiries": today_enquiries,
        "today_collection_total": today_collection_total,
        "pending_fee_students_count": pending_fee_students_count,
        "today_follow_up_count": today_follow_up_count,
        "overdue_fee_alert_count": overdue_fee_alert_count,
        "overdue_follow_up_alert_count": overdue_follow_up_alert_count,
        "stale_enquiry_alert_count": stale_enquiry_alert_count,
        "trainers_count": trainers.count(),
        "centers_count": len(centers),
        "batches_count": batches.count(),
        "today": today,
        "present_count": Attendance.objects.filter(date=today, status="present").count(),
        "absent_count": Attendance.objects.filter(date=today, status="absent").count(),
        "leave_count": Attendance.objects.filter(date=today, status="leave").count(),
        "recent_students": students.order_by("-joining_date")[:5],
        "courses": courses,
        "name_query": name_query,
        "course_query": course_query,
        "search_results": search_results,
        "has_search_filters": bool(name_query or course_query),
        "fee_summary_centers": ordered_centers,
        "fee_summary_rows": fee_summary_rows,
        "recent_communication_logs": recent_communication_logs,
    }
    return render(request, "index.html", context)
