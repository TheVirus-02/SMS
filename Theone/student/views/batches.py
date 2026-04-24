from datetime import datetime, time

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render

from student.models import Batch, Center, Student, Trainer, TrainerSchedule


STANDARD_BATCH_HOURS = range(7, 21)


def batch_list(request):
    query = request.GET.get("q", "").strip()
    centers = list(Center.objects.all().order_by("name"))
    batches = (
        Batch.objects.annotate(
            student_count=Count("student", distinct=True),
            schedule_count=Count("trainerschedule", distinct=True),
        )
        .prefetch_related(
            Prefetch(
                "trainerschedule_set",
                queryset=TrainerSchedule.objects.select_related("trainer", "center").order_by(
                    "center__name", "trainer__name"
                ),
            )
        )
        .order_by("time", "name")
    )
    batches = list(batches)
    if query:
        normalized_query = query.lower()
        filtered_batches = []
        for batch in batches:
            batch_terms = [
                batch.name or "",
                batch.time.strftime("%I %p").lstrip("0") if batch.time else "",
                batch.time.strftime("%H:%M") if batch.time else "",
            ]
            batch_terms.extend(schedule.trainer.name for schedule in batch.trainerschedule_set.all() if schedule.trainer_id)
            batch_terms.extend(schedule.center.name for schedule in batch.trainerschedule_set.all() if schedule.center_id)
            if any(normalized_query in term.lower() for term in batch_terms):
                filtered_batches.append(batch)
        batches = filtered_batches

    grid_rows = []
    for batch in batches:
        assignments_by_center = {}
        for schedule in batch.trainerschedule_set.all():
            assignments_by_center.setdefault(schedule.center_id, []).append(schedule)

        grid_rows.append(
            {
                "batch": batch,
                "student_count": batch.student_count,
                "cells": [
                    {
                        "center": center,
                        "schedules": assignments_by_center.get(center.id, []),
                    }
                    for center in centers
                ],
            }
        )

    return render(
        request,
        "batch/batch_list.html",
        {
            "batches": batches,
            "centers": centers,
            "grid_rows": grid_rows,
            "query": query,
            "total_batches": len(batches),
            "total_students": Student.objects.filter(batch__isnull=False).count(),
        },
    )


def batch_detail(request, id):
    batch = get_object_or_404(Batch, id=id)
    schedules = TrainerSchedule.objects.select_related("trainer", "center").filter(batch=batch).order_by(
        "center__name", "trainer__name"
    )
    students = Student.objects.select_related("trainer", "center").filter(batch=batch).order_by(
        "center__name", "name"
    )

    center_summary = []
    for center in Center.objects.order_by("name"):
        center_students = [student for student in students if student.center_id == center.id]
        center_schedules = [schedule for schedule in schedules if schedule.center_id == center.id]
        if center_students or center_schedules:
            center_summary.append(
                {
                    "center": center,
                    "student_count": len(center_students),
                    "students": center_students,
                    "schedules": center_schedules,
                }
            )

    return render(
        request,
        "batch/batch_detail.html",
        {
            "batch": batch,
            "schedules": schedules,
            "students": students,
            "center_summary": center_summary,
        },
    )


def add_batch(request):
    context = build_batch_form_context()
    if request.method == "POST":
        return save_batch_form(request, context)
    return render(request, "batch/batch_form.html", context)


def update_batch(request, id):
    batch = get_object_or_404(Batch, id=id)
    context = build_batch_form_context(batch=batch)
    if request.method == "POST":
        return save_batch_form(request, context, batch=batch)
    return render(request, "batch/batch_form.html", context)


def delete_batch(request, id):
    batch = get_object_or_404(Batch, id=id)
    assigned_student_count = Student.objects.filter(batch=batch).count()
    if assigned_student_count:
        messages.error(
            request,
            f"Cannot delete {batch}. {assigned_student_count} student(s) are still assigned to this batch.",
        )
        return redirect("batch_detail", id=batch.id)

    batch.delete()
    messages.success(request, "Batch deleted successfully.")
    return redirect("batch_list")


def add_batch_assignment(request, batch_id):
    batch = get_object_or_404(Batch, id=batch_id)
    context = build_assignment_form_context(batch=batch)
    if request.method == "POST":
        return save_batch_assignment_form(request, context, batch=batch)
    return render(request, "batch/assignment_form.html", context)


def update_batch_assignment(request, id):
    schedule = get_object_or_404(TrainerSchedule.objects.select_related("batch"), id=id)
    context = build_assignment_form_context(batch=schedule.batch, schedule=schedule)
    if request.method == "POST":
        return save_batch_assignment_form(request, context, batch=schedule.batch, schedule=schedule)
    return render(request, "batch/assignment_form.html", context)


def delete_batch_assignment(request, id):
    schedule = get_object_or_404(TrainerSchedule.objects.select_related("batch"), id=id)
    batch_id = schedule.batch_id
    schedule.delete()
    messages.success(request, "Batch trainer allocation deleted successfully.")
    return redirect("batch_detail", id=batch_id)


def create_standard_batches(request):
    if request.method != "POST":
        return redirect("batch_list")

    created_count = 0
    for hour in STANDARD_BATCH_HOURS:
        slot_time = time(hour=hour, minute=0)
        if Batch.objects.filter(time=slot_time).exists():
            continue
        Batch.objects.create(time=slot_time)
        created_count += 1

    if created_count:
        messages.success(request, f"{created_count} standard batch slot(s) created successfully.")
    else:
        messages.info(request, "All standard batch slots already exist.")
    return redirect("batch_list")


def build_batch_form_context(batch=None, error=None, form_data=None):
    form_data = form_data or {}
    initial_schedule = None
    if batch:
        schedules = list(batch.trainerschedule_set.all()[:2])
        if len(schedules) == 1:
            initial_schedule = schedules[0]

    return {
        "batch": batch,
        "error": error or [],
        "trainers": Trainer.objects.all().order_by("name"),
        "centers": Center.objects.all().order_by("name"),
        "selected_name": form_data.get("name", batch.name if batch else ""),
        "selected_time": form_data.get("time", format_time_input(batch.time) if batch else ""),
        "selected_trainer_id": form_data.get(
            "trainer",
            str(initial_schedule.trainer_id) if initial_schedule else "",
        ),
        "selected_center_id": form_data.get(
            "center",
            str(initial_schedule.center_id) if initial_schedule and initial_schedule.center_id else "",
        ),
    }


def build_assignment_form_context(batch, schedule=None, error=None, form_data=None):
    form_data = form_data or {}
    return {
        "batch": batch,
        "schedule": schedule,
        "error": error or [],
        "trainers": Trainer.objects.all().order_by("name"),
        "centers": Center.objects.all().order_by("name"),
        "selected_trainer_id": form_data.get(
            "trainer",
            str(schedule.trainer_id) if schedule else "",
        ),
        "selected_center_id": form_data.get(
            "center",
            str(schedule.center_id) if schedule and schedule.center_id else "",
        ),
    }


def save_batch_form(request, context, batch=None):
    form_data = {
        "name": (request.POST.get("name") or "").strip(),
        "time": (request.POST.get("time") or "").strip(),
        "trainer": (request.POST.get("trainer") or "").strip(),
        "center": (request.POST.get("center") or "").strip(),
    }

    try:
        batch_time = parse_batch_time(form_data["time"])
        validate_batch_form(form_data, batch_time, batch=batch)
    except ValidationError as exc:
        context.update(build_batch_form_context(batch=batch, error=exc.messages, form_data=form_data))
        return render(request, "batch/batch_form.html", context)

    created = batch is None
    try:
        with transaction.atomic():
            if batch is None:
                batch = Batch()
            batch.name = form_data["name"]
            batch.time = batch_time
            batch.save()

            trainer_id = form_data["trainer"] or None
            center_id = form_data["center"] or None
            if trainer_id and center_id:
                existing_schedules = list(batch.trainerschedule_set.all()[:2])
                if len(existing_schedules) == 1:
                    schedule = existing_schedules[0]
                    schedule.trainer_id = trainer_id
                    schedule.center_id = center_id
                    schedule.save()
                elif len(existing_schedules) == 0:
                    TrainerSchedule.objects.create(
                        batch=batch,
                        center_id=center_id,
                        trainer_id=trainer_id,
                    )
    except ValidationError as exc:
        context.update(build_batch_form_context(batch=batch, error=exc.messages, form_data=form_data))
        return render(request, "batch/batch_form.html", context)

    if created:
        messages.success(request, "Batch created successfully.")
    else:
        messages.success(request, "Batch updated successfully.")
    return redirect("batch_detail", id=batch.id)


def save_batch_assignment_form(request, context, batch, schedule=None):
    form_data = {
        "trainer": (request.POST.get("trainer") or "").strip(),
        "center": (request.POST.get("center") or "").strip(),
    }

    try:
        if not form_data["trainer"] or not form_data["center"]:
            raise ValidationError("Select both trainer and center.")

        if schedule is None:
            schedule = TrainerSchedule(batch=batch)
        schedule.trainer_id = form_data["trainer"]
        schedule.center_id = form_data["center"]
        schedule.save()
    except ValidationError as exc:
        context.update(build_assignment_form_context(batch=batch, schedule=schedule, error=exc.messages, form_data=form_data))
        return render(request, "batch/assignment_form.html", context)

    messages.success(
        request,
        "Batch trainer allocation updated successfully."
        if request.resolver_match.url_name == "update_batch_assignment"
        else "Batch trainer allocation added successfully.",
    )
    return redirect("batch_detail", id=batch.id)


def validate_batch_form(form_data, batch_time, batch=None):
    if not batch_time:
        raise ValidationError("Select a valid batch time.")

    duplicate_time_qs = Batch.objects.filter(time=batch_time)
    if batch:
        duplicate_time_qs = duplicate_time_qs.exclude(pk=batch.pk)
    if duplicate_time_qs.exists():
        raise ValidationError("This batch time already exists.")

    trainer_selected = bool(form_data["trainer"])
    center_selected = bool(form_data["center"])
    if trainer_selected != center_selected:
        raise ValidationError("Select both trainer and center together for the initial allocation.")


def parse_batch_time(raw_time):
    for time_format in ("%H:%M", "%H:%M:%S"):
        try:
            parsed = datetime.strptime(raw_time, time_format)
            return parsed.time().replace(second=0, microsecond=0)
        except (TypeError, ValueError):
            continue
    raise ValidationError("Enter batch time in a valid format.")


def format_time_input(value):
    if not value:
        return ""
    return value.strftime("%H:%M")
