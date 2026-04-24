from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from student.models import Batch, Center, Course, Student, Trainer, TrainerSchedule


def trainer_list(request):
    query = request.GET.get("q", "").strip()
    trainers = Trainer.objects.prefetch_related("courses").annotate(
        student_count=Count("student", distinct=True),
        schedule_count=Count("trainerschedule", distinct=True),
    ).order_by("name")
    if query:
        trainers = trainers.filter(
            Q(name__icontains=query) |
            Q(mobile__icontains=query) |
            Q(courses__name__icontains=query)
        ).distinct()

    return render(
        request,
        "trainer/trainer_list.html",
        {
            "trainers": trainers,
            "query": query,
            "total_trainers": trainers.count(),
        },
    )


def trainer_detail(request, id):
    trainer = get_object_or_404(Trainer.objects.prefetch_related("courses"), id=id)
    schedules = TrainerSchedule.objects.select_related("center", "batch").filter(trainer=trainer)
    assigned_students = Student.objects.filter(trainer=trainer).select_related("batch", "center").order_by("name")
    return render(
        request,
        "trainer/trainer_detail.html",
        {
            "trainer": trainer,
            "schedules": schedules,
            "assigned_students": assigned_students,
            "student_count": assigned_students.count(),
        },
    )


def add_trainer(request):
    courses = Course.objects.all().order_by("name")
    if request.method == "POST":
        trainer = Trainer.objects.create(
            name=request.POST.get("name"),
            age=request.POST.get("age") or None,
            dob=request.POST.get("dob") or None,
            mobile=request.POST.get("mobile"),
            joining_date=request.POST.get("joining_date") or None,
        )
        trainer.courses.set(request.POST.getlist("courses"))
        messages.success(request, f"{trainer.name} added successfully.")
        return redirect("trainer_detail", id=trainer.id)
    return render(request, "trainer/add_trainer.html", {"courses": courses})


def update_trainer(request, id):
    trainer = get_object_or_404(Trainer, id=id)
    courses = Course.objects.all().order_by("name")
    if request.method == "POST":
        trainer.name = request.POST.get("name")
        trainer.age = request.POST.get("age") or None
        trainer.dob = request.POST.get("dob") or None
        trainer.mobile = request.POST.get("mobile")
        trainer.joining_date = request.POST.get("joining_date") or None
        trainer.save()
        trainer.courses.set(request.POST.getlist("courses"))
        messages.success(request, f"{trainer.name} updated successfully.")
        return redirect("trainer_detail", id=trainer.id)
    return render(request, "trainer/update_trainer.html", {"trainer": trainer, "courses": courses})


def delete_trainer(request, id):
    trainer = get_object_or_404(Trainer, id=id)
    trainer_name = trainer.name
    trainer.delete()
    messages.success(request, f"{trainer_name} deleted successfully.")
    return redirect("trainer_list")


def trainer_schedule_page(request):
    trainer_id = request.GET.get("trainer", "").strip()
    schedules = TrainerSchedule.objects.select_related("trainer", "center", "batch").order_by(
        "batch__time", "trainer__name", "center__name"
    )
    if trainer_id:
        schedules = schedules.filter(trainer_id=trainer_id)

    all_batches = list(Batch.objects.all().order_by("time"))
    all_centers = list(Center.objects.all().order_by("name"))
    assigned_pairs = set(TrainerSchedule.objects.values_list("batch_id", "center_id"))
    uncovered_slots = []
    for batch in all_batches:
        missing_centers = [center for center in all_centers if (batch.id, center.id) not in assigned_pairs]
        if missing_centers:
            uncovered_slots.append(
                {
                    "batch": batch,
                    "missing_centers": missing_centers,
                    "missing_count": len(missing_centers),
                }
            )

    return render(
        request,
        "trainer/schedule_list.html",
        {
            "schedules": schedules,
            "trainers": Trainer.objects.all().order_by("name"),
            "centers": Center.objects.all().order_by("name"),
            "batches": Batch.objects.all().order_by("time"),
            "selected_trainer_id": trainer_id,
            "uncovered_slots": uncovered_slots,
        },
    )


def add_schedule(request, trainer_id=None):
    initial_trainer = get_object_or_404(Trainer, id=trainer_id) if trainer_id else None
    trainers = Trainer.objects.all().order_by("name")
    centers = Center.objects.all().order_by("name")
    batches = Batch.objects.all().order_by("time")

    if request.method == "POST":
        selected_trainer = get_object_or_404(Trainer, id=request.POST.get("trainer"))
        start_batch_id = request.POST.get("start_batch")
        end_batch_id = request.POST.get("end_batch")
        center_id = request.POST.get("center") or None

        try:
            created_count = create_bulk_trainer_schedule(
                trainer=selected_trainer,
                start_batch_id=start_batch_id,
                end_batch_id=end_batch_id,
                center_id=center_id,
            )
        except ValidationError as exc:
            return render(
                request,
                "trainer/add_schedule.html",
                {
                    "trainer": initial_trainer,
                    "selected_trainer_id": request.POST.get("trainer", ""),
                    "selected_center_id": center_id or "",
                    "selected_start_batch_id": start_batch_id or "",
                    "selected_end_batch_id": end_batch_id or "",
                    "trainers": trainers,
                    "centers": centers,
                    "batches": batches,
                    "error": exc.messages,
                },
            )

        messages.success(request, f"{created_count} schedule slot(s) added successfully.")
        return redirect("trainer_schedule_page")

    return render(
        request,
        "trainer/add_schedule.html",
        {
            "trainer": initial_trainer,
            "selected_trainer_id": str(initial_trainer.id) if initial_trainer else "",
            "selected_center_id": "",
            "selected_start_batch_id": "",
            "selected_end_batch_id": "",
            "trainers": trainers,
            "centers": centers,
            "batches": batches,
        },
    )


def update_schedule(request, id):
    schedule = get_object_or_404(TrainerSchedule.objects.select_related("trainer", "center", "batch"), id=id)
    trainers = Trainer.objects.all().order_by("name")
    centers = Center.objects.all().order_by("name")
    batches = Batch.objects.all().order_by("time")

    if request.method == "POST":
        schedule.trainer_id = request.POST.get("trainer")
        schedule.center_id = request.POST.get("center")
        schedule.batch_id = request.POST.get("batch")
        try:
            schedule.save()
        except ValidationError as exc:
            return render(
                request,
                "trainer/update_schedule.html",
                {
                    "schedule": schedule,
                    "trainers": trainers,
                    "centers": centers,
                    "batches": batches,
                    "error": exc.messages,
                },
            )
        messages.success(request, "Schedule updated successfully.")
        return redirect("trainer_schedule_page")

    return render(
        request,
        "trainer/update_schedule.html",
        {"schedule": schedule, "trainers": trainers, "centers": centers, "batches": batches},
    )


def delete_schedule(request, id):
    schedule = get_object_or_404(TrainerSchedule.objects.select_related("trainer"), id=id)
    messages.success(request, "Schedule deleted successfully.")
    schedule.delete()
    return redirect("trainer_schedule_page")


def create_bulk_trainer_schedule(trainer, start_batch_id, end_batch_id, center_id=None):
    if not start_batch_id or not end_batch_id:
        raise ValidationError("Select both start batch and end batch.")

    batch_map = {batch.id: batch for batch in Batch.objects.all().order_by("time")}
    try:
        start_batch_id = int(start_batch_id)
        end_batch_id = int(end_batch_id)
    except (TypeError, ValueError):
        raise ValidationError("Invalid batch range selected.")

    start_batch = batch_map.get(start_batch_id)
    end_batch = batch_map.get(end_batch_id)
    if not start_batch or not end_batch:
        raise ValidationError("Selected batch range is not available.")

    ordered_batches = list(batch_map.values())
    start_index = next((index for index, batch in enumerate(ordered_batches) if batch.id == start_batch.id), None)
    end_index = next((index for index, batch in enumerate(ordered_batches) if batch.id == end_batch.id), None)
    if start_index is None or end_index is None or start_index > end_index:
        raise ValidationError("End batch must be after start batch.")

    created_count = 0
    for batch in ordered_batches[start_index:end_index + 1]:
        schedule = TrainerSchedule(trainer=trainer, batch=batch, center_id=center_id)
        try:
            schedule.save()
        except ValidationError as exc:
            if "already assigned for the selected batch time" in " ".join(exc.messages):
                continue
            raise
        created_count += 1

    if created_count == 0:
        raise ValidationError("No new schedule slot was created. Selected range may already exist.")
    return created_count
