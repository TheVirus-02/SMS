from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from student.models import Center, CenterLogistics, Student
from student.portal import (
    ROLE_ADMIN,
    ROLE_COUNSELLOR,
    ROLE_TRAINER,
    role_required,
    scope_centers_for_user,
)


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR, ROLE_TRAINER)
def logistics_dashboard(request):
    rows = []
    total_capacity = 0
    total_repair = 0
    total_remaining_pc = 0
    total_students = 0
    total_remaining_place = 0

    for center in scope_centers_for_user(request.user, Center.objects.all()).order_by("name"):
        log, _ = CenterLogistics.objects.get_or_create(center=center)
        student_count = Student.objects.filter(center=center).count()
        remaining_place = max(log.total_capacity - student_count, 0)

        rows.append(
            {
                "log": log,
                "student_count": student_count,
                "remaining_place": remaining_place,
            }
        )
        total_capacity += log.total_capacity
        total_repair += log.repair_pc
        total_remaining_pc += log.remaining_pc
        total_students += student_count
        total_remaining_place += remaining_place

    return render(
        request,
        "logistics/dashboard.html",
        {
            "rows": rows,
            "summary": {
                "total_capacity": total_capacity,
                "total_repair": total_repair,
                "total_remaining_pc": total_remaining_pc,
                "total_students": total_students,
                "total_remaining_place": total_remaining_place,
            },
        },
    )


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR, ROLE_TRAINER)
def update_logistics(request, id, action):
    log = CenterLogistics.objects.get(id=id)
    log.save()
    return redirect("logistics_dashboard")


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR, ROLE_TRAINER)
def update_total_pc(request, id):
    if request.method != "POST":
        return HttpResponseBadRequest("POST request required.")

    log = get_object_or_404(CenterLogistics.objects.select_related("center"), center__in=scope_centers_for_user(request.user, Center.objects.all()), id=id)
    try:
        new_total = max(int(request.POST.get("total_pc", 0)), 0)
    except (TypeError, ValueError):
        return JsonResponse({"status": "error", "message": "Enter a valid total capacity."}, status=400)

    log.total_pc = new_total
    log.save()
    return JsonResponse(build_logistics_payload(log))


@role_required(ROLE_ADMIN, ROLE_COUNSELLOR, ROLE_TRAINER)
def update_repair_pc(request, id):
    if request.method != "POST":
        return HttpResponseBadRequest("POST request required.")

    log = get_object_or_404(CenterLogistics.objects.select_related("center"), center__in=scope_centers_for_user(request.user, Center.objects.all()), id=id)
    try:
        new_repair = max(int(request.POST.get("repair_pc", 0)), 0)
    except (TypeError, ValueError):
        return JsonResponse({"status": "error", "message": "Enter a valid repair PC count."}, status=400)

    log.repair_pc = new_repair
    log.save()
    return JsonResponse(build_logistics_payload(log))


def build_logistics_payload(log):
    student_count = Student.objects.filter(center=log.center).count()
    return {
        "status": "success",
        "total_capacity": log.total_capacity,
        "repair_pc": log.repair_pc,
        "remaining_pc": log.remaining_pc,
        "student_count": student_count,
        "remaining_place": max(log.total_capacity - student_count, 0),
    }
