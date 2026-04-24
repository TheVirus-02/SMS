from datetime import date
import re

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from student.models import Batch, Center, Counsellor, Course, Enquiry, Student, Trainer


def enquiry_list(request):
    query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    counsellor_filter = request.GET.get("counsellor", "").strip()

    enquiries = Enquiry.objects.select_related(
        "interested_course",
        "preferred_batch",
        "preferred_center",
        "assigned_counsellor",
        "converted_student",
    ).order_by("-updated_at", "-enquiry_date")

    if query:
        enquiries = enquiries.filter(
            Q(name__icontains=query)
            | Q(mobile_no__icontains=query)
            | Q(interested_course__name__icontains=query)
            | Q(source__icontains=query)
        )
    if status_filter:
        enquiries = enquiries.filter(status=status_filter)
    if counsellor_filter:
        enquiries = enquiries.filter(assigned_counsellor_id=counsellor_filter)

    enquiries = list(enquiries)
    today = date.today()

    return render(
        request,
        "enquiry/enquiry_list.html",
        {
            "enquiries": enquiries,
            "query": query,
            "status_filter": status_filter,
            "counsellor_filter": counsellor_filter,
            "status_choices": Enquiry.STATUS_CHOICES,
            "counsellors": Counsellor.objects.all().order_by("name"),
            "total_enquiries": len(enquiries),
            "new_count": sum(1 for enquiry in enquiries if enquiry.status == "new"),
            "follow_up_count": sum(1 for enquiry in enquiries if enquiry.status in {"contacted", "follow_up", "demo_scheduled", "demo_attended", "interested", "ready"}),
            "admitted_count": sum(1 for enquiry in enquiries if enquiry.status == "admitted"),
            "today_follow_up_count": sum(1 for enquiry in enquiries if enquiry.next_follow_up_date == today),
        },
    )


def today_follow_up(request):
    today = date.today()
    enquiries = list(
        Enquiry.objects.select_related(
            "interested_course",
            "preferred_batch",
            "preferred_center",
            "assigned_counsellor",
            "converted_student",
        ).filter(next_follow_up_date=today).order_by("assigned_counsellor__name", "name")
    )
    return render(
        request,
        "enquiry/today_follow_up.html",
        {
            "enquiries": enquiries,
            "today": today,
            "total_enquiries": len(enquiries),
        },
    )


def enquiry_detail(request, id):
    enquiry = get_object_or_404(
        Enquiry.objects.select_related(
            "interested_course",
            "preferred_batch",
            "preferred_center",
            "assigned_counsellor",
            "converted_student",
        ),
        id=id,
    )
    return render(request, "enquiry/enquiry_detail.html", {"enquiry": enquiry})


def add_enquiry(request):
    context = build_enquiry_form_context()
    if request.method == "POST":
        return save_enquiry_form(request, context)
    return render(request, "enquiry/enquiry_form.html", context)


def update_enquiry(request, id):
    enquiry = get_object_or_404(Enquiry, id=id)
    context = build_enquiry_form_context(enquiry=enquiry)
    if request.method == "POST":
        return save_enquiry_form(request, context, enquiry=enquiry)
    return render(request, "enquiry/enquiry_form.html", context)


def delete_enquiry(request, id):
    enquiry = get_object_or_404(Enquiry, id=id)
    if enquiry.converted_student_id:
        messages.error(request, "Converted enquiry cannot be deleted because it is linked to a student record.")
        return redirect("enquiry_detail", id=enquiry.id)

    enquiry_name = enquiry.name
    enquiry.delete()
    messages.success(request, f"{enquiry_name} enquiry deleted successfully.")
    return redirect("enquiry_list")


def convert_enquiry(request, id):
    enquiry = get_object_or_404(
        Enquiry.objects.select_related(
            "interested_course",
            "preferred_batch",
            "preferred_center",
            "assigned_counsellor",
            "converted_student",
        ),
        id=id,
    )
    if enquiry.converted_student_id:
        messages.info(request, "This enquiry is already converted to admission.")
        return redirect("student_detail", id=enquiry.converted_student_id)

    context = build_conversion_context(enquiry)
    if request.method == "POST":
        return save_enquiry_conversion(request, enquiry, context)
    return render(request, "enquiry/convert_enquiry.html", context)


def build_enquiry_form_context(enquiry=None, error=None, form_data=None):
    form_data = form_data or {}
    return {
        "enquiry": enquiry,
        "error": error or [],
        "courses": Course.objects.all().order_by("name"),
        "batches": Batch.objects.all().order_by("time"),
        "centers": Center.objects.all().order_by("name"),
        "counsellors": Counsellor.objects.select_related("center").all(),
        "status_choices": Enquiry.STATUS_CHOICES,
        "probability_choices": Enquiry.PROBABILITY_CHOICES,
        "form_data": {
            "name": form_data.get("name", enquiry.name if enquiry else ""),
            "mobile_no": form_data.get("mobile_no", enquiry.mobile_no if enquiry else ""),
            "alt_mobile_no": form_data.get("alt_mobile_no", enquiry.alt_mobile_no if enquiry and enquiry.alt_mobile_no else ""),
            "guardian_name": form_data.get("guardian_name", enquiry.guardian_name if enquiry and enquiry.guardian_name else ""),
            "guardian_mobile": form_data.get("guardian_mobile", enquiry.guardian_mobile if enquiry and enquiry.guardian_mobile else ""),
            "age": form_data.get("age", enquiry.age if enquiry and enquiry.age is not None else ""),
            "qualification": form_data.get("qualification", enquiry.qualification if enquiry and enquiry.qualification else ""),
            "address": form_data.get("address", enquiry.address if enquiry and enquiry.address else ""),
            "enquiry_date": form_data.get("enquiry_date", enquiry.enquiry_date.isoformat() if enquiry and enquiry.enquiry_date else ""),
            "interested_course": form_data.get("interested_course", str(enquiry.interested_course_id) if enquiry and enquiry.interested_course_id else ""),
            "preferred_batch": form_data.get("preferred_batch", str(enquiry.preferred_batch_id) if enquiry and enquiry.preferred_batch_id else ""),
            "preferred_center": form_data.get("preferred_center", str(enquiry.preferred_center_id) if enquiry and enquiry.preferred_center_id else ""),
            "fee_discussed": form_data.get("fee_discussed", enquiry.fee_discussed if enquiry and enquiry.fee_discussed is not None else ""),
            "expected_joining_date": form_data.get("expected_joining_date", enquiry.expected_joining_date.isoformat() if enquiry and enquiry.expected_joining_date else ""),
            "source": form_data.get("source", enquiry.source if enquiry and enquiry.source else ""),
            "assigned_counsellor": form_data.get("assigned_counsellor", str(enquiry.assigned_counsellor_id) if enquiry and enquiry.assigned_counsellor_id else ""),
            "status": form_data.get("status", enquiry.status if enquiry else "new"),
            "next_follow_up_date": form_data.get("next_follow_up_date", enquiry.next_follow_up_date.isoformat() if enquiry and enquiry.next_follow_up_date else ""),
            "last_follow_up_date": form_data.get("last_follow_up_date", enquiry.last_follow_up_date.isoformat() if enquiry and enquiry.last_follow_up_date else ""),
            "follow_up_remarks": form_data.get("follow_up_remarks", enquiry.follow_up_remarks if enquiry and enquiry.follow_up_remarks else ""),
            "demo_date": form_data.get("demo_date", enquiry.demo_date.isoformat() if enquiry and enquiry.demo_date else ""),
            "demo_result": form_data.get("demo_result", enquiry.demo_result if enquiry and enquiry.demo_result else ""),
            "admission_probability": form_data.get("admission_probability", enquiry.admission_probability if enquiry else "warm"),
            "lost_reason": form_data.get("lost_reason", enquiry.lost_reason if enquiry and enquiry.lost_reason else ""),
        },
    }


def save_enquiry_form(request, context, enquiry=None):
    form_data = {
        "name": (request.POST.get("name") or "").strip(),
        "mobile_no": (request.POST.get("mobile_no") or "").strip(),
        "alt_mobile_no": (request.POST.get("alt_mobile_no") or "").strip(),
        "guardian_name": (request.POST.get("guardian_name") or "").strip(),
        "guardian_mobile": (request.POST.get("guardian_mobile") or "").strip(),
        "age": request.POST.get("age") or None,
        "qualification": (request.POST.get("qualification") or "").strip(),
        "address": (request.POST.get("address") or "").strip(),
        "enquiry_date": request.POST.get("enquiry_date") or None,
        "interested_course_id": request.POST.get("interested_course") or None,
        "preferred_batch_id": request.POST.get("preferred_batch") or None,
        "preferred_center_id": request.POST.get("preferred_center") or None,
        "fee_discussed": request.POST.get("fee_discussed") or None,
        "expected_joining_date": request.POST.get("expected_joining_date") or None,
        "source": (request.POST.get("source") or "").strip(),
        "assigned_counsellor_id": request.POST.get("assigned_counsellor") or None,
        "status": request.POST.get("status") or "new",
        "next_follow_up_date": request.POST.get("next_follow_up_date") or None,
        "last_follow_up_date": request.POST.get("last_follow_up_date") or None,
        "follow_up_remarks": (request.POST.get("follow_up_remarks") or "").strip(),
        "demo_date": request.POST.get("demo_date") or None,
        "demo_result": (request.POST.get("demo_result") or "").strip(),
        "admission_probability": request.POST.get("admission_probability") or "warm",
        "lost_reason": (request.POST.get("lost_reason") or "").strip(),
    }

    error = validate_enquiry_form(form_data, enquiry=enquiry)
    if error:
        context.update(build_enquiry_form_context(enquiry=enquiry, error=[error], form_data=normalize_enquiry_form_data(form_data)))
        return render(request, "enquiry/enquiry_form.html", context)

    payload = normalize_enquiry_payload(form_data)
    if enquiry is None:
        enquiry = Enquiry.objects.create(**payload)
        messages.success(request, f"{enquiry.name} enquiry added successfully.")
    else:
        for field, value in payload.items():
            setattr(enquiry, field, value)
        enquiry.save()
        messages.success(request, f"{enquiry.name} enquiry updated successfully.")
    return redirect("enquiry_detail", id=enquiry.id)


def build_conversion_context(enquiry, error=None, form_data=None):
    form_data = form_data or {}
    return {
        "enquiry": enquiry,
        "error": error or [],
        "courses": Course.objects.all().order_by("name"),
        "trainers": Trainer.objects.all().order_by("name"),
        "batches": Batch.objects.all().order_by("time"),
        "centers": Center.objects.all().order_by("name"),
        "counsellors": Counsellor.objects.select_related("center").all(),
        "form_data": {
            "course": form_data.get("course", str(enquiry.interested_course_id) if enquiry.interested_course_id else ""),
            "trainer": form_data.get("trainer", ""),
            "batch": form_data.get("batch", str(enquiry.preferred_batch_id) if enquiry.preferred_batch_id else ""),
            "center": form_data.get("center", str(enquiry.preferred_center_id) if enquiry.preferred_center_id else ""),
            "counsellor": form_data.get("counsellor", str(enquiry.assigned_counsellor_id) if enquiry.assigned_counsellor_id else ""),
            "joining_date": form_data.get("joining_date", enquiry.expected_joining_date.isoformat() if enquiry.expected_joining_date else date.today().isoformat()),
            "course_fee": form_data.get("course_fee", enquiry.fee_discussed if enquiry.fee_discussed else ""),
            "paid_fee": form_data.get("paid_fee", ""),
            "reference_source": form_data.get("reference_source", enquiry.source or ""),
            "status": form_data.get("status", "active"),
        },
    }


def save_enquiry_conversion(request, enquiry, context):
    form_data = {
        "course": request.POST.get("course") or None,
        "trainer": request.POST.get("trainer") or None,
        "batch": request.POST.get("batch") or None,
        "center": request.POST.get("center") or None,
        "counsellor": request.POST.get("counsellor") or None,
        "joining_date": request.POST.get("joining_date") or None,
        "course_fee": request.POST.get("course_fee") or None,
        "paid_fee": request.POST.get("paid_fee") or None,
        "reference_source": (request.POST.get("reference_source") or "").strip(),
        "status": request.POST.get("status") or "active",
    }

    error = validate_conversion_form(form_data)
    if error:
        context.update(build_conversion_context(enquiry, error=[error], form_data=form_data))
        return render(request, "enquiry/convert_enquiry.html", context)

    duplicate_student = find_student_by_mobile(enquiry.mobile_no)
    if duplicate_student:
        context.update(
            build_conversion_context(
                enquiry,
                error=[f"A student already exists with this mobile number: {duplicate_student.name} ({duplicate_student.student_id})."],
                form_data=form_data,
            )
        )
        return render(request, "enquiry/convert_enquiry.html", context)

    with transaction.atomic():
        student = Student.objects.create(
            name=enquiry.name,
            mobile_no=enquiry.mobile_no,
            alt_mobile_no=enquiry.alt_mobile_no or None,
            guardian_name=enquiry.guardian_name or None,
            guardian_mobile=enquiry.guardian_mobile or None,
            qualification=enquiry.qualification or None,
            address=enquiry.address or None,
            joining_date=form_data["joining_date"],
            counsellor_id=form_data["counsellor"],
            course_fee=form_data["course_fee"] or None,
            paid_fee=form_data["paid_fee"] or None,
            trainer_id=form_data["trainer"],
            batch_id=form_data["batch"],
            center_id=form_data["center"],
            reference_source=form_data["reference_source"] or enquiry.source or None,
            status=form_data["status"],
        )
        student.courses.set([form_data["course"]])

        enquiry.converted_student = student
        enquiry.converted_at = date.today()
        enquiry.status = "admitted"
        enquiry.assigned_counsellor_id = form_data["counsellor"]
        enquiry.preferred_center_id = form_data["center"]
        enquiry.preferred_batch_id = form_data["batch"]
        enquiry.interested_course_id = form_data["course"]
        enquiry.expected_joining_date = form_data["joining_date"]
        enquiry.save()

    messages.success(request, f"{enquiry.name} converted to admission successfully.")
    return redirect("student_detail", id=student.id)


def validate_enquiry_form(form_data, enquiry=None):
    if not form_data["name"]:
        return "Student name is required."
    if not form_data["mobile_no"]:
        return "Mobile number is required."
    duplicate_enquiry = find_enquiry_by_mobile(form_data["mobile_no"], exclude_id=enquiry.id if enquiry else None)
    if duplicate_enquiry:
        return f"An enquiry already exists with this mobile number: {duplicate_enquiry.name}."
    duplicate_student = find_student_by_mobile(form_data["mobile_no"])
    if duplicate_student:
        return f"A student already exists with this mobile number: {duplicate_student.name} ({duplicate_student.student_id})."
    return None


def validate_conversion_form(form_data):
    required_fields = {
        "course": "Select course.",
        "trainer": "Select trainer.",
        "batch": "Select batch.",
        "center": "Select center.",
        "joining_date": "Select joining date.",
    }
    for field, error_message in required_fields.items():
        if not form_data.get(field):
            return error_message
    return None


def normalize_enquiry_payload(form_data):
    return {
        "name": form_data["name"],
        "mobile_no": form_data["mobile_no"],
        "alt_mobile_no": form_data["alt_mobile_no"] or None,
        "guardian_name": form_data["guardian_name"] or None,
        "guardian_mobile": form_data["guardian_mobile"] or None,
        "age": form_data["age"],
        "qualification": form_data["qualification"] or None,
        "address": form_data["address"] or None,
        "enquiry_date": form_data["enquiry_date"] or date.today(),
        "interested_course_id": form_data["interested_course_id"],
        "preferred_batch_id": form_data["preferred_batch_id"],
        "preferred_center_id": form_data["preferred_center_id"],
        "fee_discussed": form_data["fee_discussed"],
        "expected_joining_date": form_data["expected_joining_date"] or None,
        "source": form_data["source"] or None,
        "assigned_counsellor_id": form_data["assigned_counsellor_id"],
        "status": form_data["status"],
        "next_follow_up_date": form_data["next_follow_up_date"] or None,
        "last_follow_up_date": form_data["last_follow_up_date"] or None,
        "follow_up_remarks": form_data["follow_up_remarks"] or None,
        "demo_date": form_data["demo_date"] or None,
        "demo_result": form_data["demo_result"] or None,
        "admission_probability": form_data["admission_probability"],
        "lost_reason": form_data["lost_reason"] or None,
    }


def normalize_enquiry_form_data(form_data):
    return {
        "name": form_data["name"],
        "mobile_no": form_data["mobile_no"],
        "alt_mobile_no": form_data["alt_mobile_no"],
        "guardian_name": form_data["guardian_name"],
        "guardian_mobile": form_data["guardian_mobile"],
        "age": form_data["age"] or "",
        "qualification": form_data["qualification"],
        "address": form_data["address"],
        "enquiry_date": form_data["enquiry_date"] or "",
        "interested_course": form_data["interested_course_id"] or "",
        "preferred_batch": form_data["preferred_batch_id"] or "",
        "preferred_center": form_data["preferred_center_id"] or "",
        "fee_discussed": form_data["fee_discussed"] or "",
        "expected_joining_date": form_data["expected_joining_date"] or "",
        "source": form_data["source"],
        "assigned_counsellor": form_data["assigned_counsellor_id"] or "",
        "status": form_data["status"],
        "next_follow_up_date": form_data["next_follow_up_date"] or "",
        "last_follow_up_date": form_data["last_follow_up_date"] or "",
        "follow_up_remarks": form_data["follow_up_remarks"],
        "demo_date": form_data["demo_date"] or "",
        "demo_result": form_data["demo_result"],
        "admission_probability": form_data["admission_probability"],
        "lost_reason": form_data["lost_reason"],
    }


def normalize_mobile_number(value):
    digits = re.sub(r"\D", "", value or "")
    if len(digits) >= 10:
        return digits[-10:]
    return digits


def find_enquiry_by_mobile(value, exclude_id=None):
    target = normalize_mobile_number(value)
    if not target:
        return None
    enquiries = Enquiry.objects.all()
    if exclude_id:
        enquiries = enquiries.exclude(pk=exclude_id)
    for enquiry in enquiries:
        if normalize_mobile_number(enquiry.mobile_no) == target:
            return enquiry
    return None


def find_student_by_mobile(value, exclude_id=None):
    target = normalize_mobile_number(value)
    if not target:
        return None
    students = Student.objects.all()
    if exclude_id:
        students = students.exclude(pk=exclude_id)
    for student in students:
        if normalize_mobile_number(student.mobile_no) == target:
            return student
    return None
