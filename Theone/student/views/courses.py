from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from student.models import Course, StudentCourse, Trainer


def course_list(request):
    query = request.GET.get("q", "").strip()
    courses = Course.objects.annotate(
        trainer_count=Count("trainer", distinct=True),
        student_count=Count("studentcourse", distinct=True),
    ).prefetch_related("trainer_set").order_by("name")

    if query:
        courses = courses.filter(
            Q(name__icontains=query) | Q(trainer__name__icontains=query)
        ).distinct()

    return render(
        request,
        "course/course_list.html",
        {
            "courses": courses,
            "query": query,
            "total_courses": courses.count(),
        },
    )


def course_detail(request, id):
    course = get_object_or_404(Course.objects.prefetch_related("trainer_set"), id=id)
    student_courses = StudentCourse.objects.select_related("student").filter(course=course).order_by("student__name")
    return render(
        request,
        "course/course_detail.html",
        {
            "course": course,
            "trainers": course.trainer_set.all().order_by("name"),
            "student_courses": student_courses,
            "student_count": student_courses.count(),
        },
    )


def add_course(request):
    trainers = Trainer.objects.all().order_by("name")
    if request.method == "POST":
        course_name = (request.POST.get("name") or "").strip()
        error = validate_course_name(course_name)
        if error:
            return render(
                request,
                "course/course_form.html",
                {
                    "trainers": trainers,
                    "selected_name": course_name,
                    "selected_description": (request.POST.get("description") or "").strip(),
                    "selected_trainers": request.POST.getlist("trainers"),
                    "error": [error],
                },
            )

        course = Course.objects.create(
            name=course_name,
            description=(request.POST.get("description") or "").strip() or None,
        )
        course.trainer_set.set(request.POST.getlist("trainers"))
        messages.success(request, f"{course.name} added successfully.")
        return redirect("course_detail", id=course.id)

    return render(
        request,
        "course/course_form.html",
        {"trainers": trainers, "selected_name": "", "selected_description": "", "selected_trainers": [], "error": []},
    )


def update_course(request, id):
    course = get_object_or_404(Course, id=id)
    trainers = Trainer.objects.all().order_by("name")
    if request.method == "POST":
        course_name = (request.POST.get("name") or "").strip()
        error = validate_course_name(course_name, course=course)
        if error:
            return render(
                request,
                "course/course_form.html",
                {
                    "course": course,
                    "trainers": trainers,
                    "selected_name": course_name,
                    "selected_description": (request.POST.get("description") or "").strip(),
                    "selected_trainers": request.POST.getlist("trainers"),
                    "error": [error],
                },
            )

        course.name = course_name
        course.description = (request.POST.get("description") or "").strip() or None
        course.save()
        course.trainer_set.set(request.POST.getlist("trainers"))
        messages.success(request, f"{course.name} updated successfully.")
        return redirect("course_detail", id=course.id)

    return render(
        request,
        "course/course_form.html",
        {
            "course": course,
            "trainers": trainers,
            "selected_name": course.name,
            "selected_description": course.description or "",
            "selected_trainers": [str(trainer_id) for trainer_id in course.trainer_set.values_list("id", flat=True)],
            "error": [],
        },
    )


def delete_course(request, id):
    course = get_object_or_404(Course, id=id)
    if StudentCourse.objects.filter(course=course).exists():
        messages.error(
            request,
            f"Cannot delete {course.name}. This course is already assigned to students or exam records.",
        )
        return redirect("course_detail", id=course.id)

    course_name = course.name
    course.delete()
    messages.success(request, f"{course_name} deleted successfully.")
    return redirect("course_list")


def validate_course_name(course_name, course=None):
    if not course_name:
        return "Course name is required."

    duplicate_courses = Course.objects.filter(name__iexact=course_name)
    if course:
        duplicate_courses = duplicate_courses.exclude(pk=course.pk)
    if duplicate_courses.exists():
        return "A course with this name already exists."
    return None
