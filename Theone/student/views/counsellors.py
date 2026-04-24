from datetime import date

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from student.models import Center, Counsellor, Enquiry, Student


def counsellor_list(request):
    query = request.GET.get("q", "").strip()
    centre_id = request.GET.get("center", "").strip()
    today = date.today()

    counsellors = Counsellor.objects.select_related("center").annotate(
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


def counsellor_detail(request, id):
    counsellor = get_object_or_404(Counsellor.objects.select_related("center"), id=id)
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


def add_counsellor(request):
    centers = Center.objects.all().order_by("name")
    if request.method == "POST":
        form_data = build_counsellor_form_data(request)
        error = validate_counsellor_form(form_data)
        if error:
            return render(
                request,
                "counsellor/counsellor_form.html",
                {"centers": centers, "error": [error], "form_data": form_data},
            )

        counsellor = Counsellor.objects.create(**form_data)
        messages.success(request, f"{counsellor.name} added successfully.")
        return redirect("counsellor_detail", id=counsellor.id)

    return render(
        request,
        "counsellor/counsellor_form.html",
        {"centers": centers, "error": [], "form_data": empty_counsellor_form_data()},
    )


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
                {"counsellor": counsellor, "centers": centers, "error": [error], "form_data": form_data},
            )

        for field, value in form_data.items():
            setattr(counsellor, field, value)
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
            "form_data": {
                "name": counsellor.name,
                "mobile": counsellor.mobile or "",
                "center_id": str(counsellor.center_id) if counsellor.center_id else "",
                "address": counsellor.address or "",
                "age": counsellor.age or "",
                "dob": counsellor.dob.isoformat() if counsellor.dob else "",
                "joining_date": counsellor.joining_date.isoformat() if counsellor.joining_date else "",
            },
        },
    )


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
        "address": (request.POST.get("address") or "").strip() or None,
        "age": request.POST.get("age") or None,
        "dob": request.POST.get("dob") or None,
        "joining_date": request.POST.get("joining_date") or None,
    }


def validate_counsellor_form(form_data):
    if not form_data["name"]:
        return "Counsellor name is required."
    return None


def empty_counsellor_form_data():
    return {
        "name": "",
        "mobile": "",
        "center_id": "",
        "address": "",
        "age": "",
        "dob": "",
        "joining_date": "",
    }
