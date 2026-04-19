from django.shortcuts import render,redirect,get_object_or_404
from django.http import HttpResponse
from django.db.models import Q,Count
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt

from .models import Student, Course, Counsellor, Trainer, Batch, Center, StudentCourse, Installment, Attendance, \
    TrainerSchedule, CenterLogistics
from datetime import date, datetime
from django.http import JsonResponse
from django.contrib import messages
from datetime import date as today_date
from .templatetags.dict_extras import register


# All Views Present here

def index(request):
    return render(request, 'index.html')

# Create your views here.
def student_registration(request):
    courses = Course.objects.all()  # get all courses
    counsellors = Counsellor.objects.all()
    trainers = Trainer.objects.all()
    batches = Batch.objects.all()
    centers = Center.objects.all()

    if request.method == 'POST':
        name = request.POST.get('name')
        counsellor_id = request.POST.get('counsellor')
        mobile = request.POST.get('mobile_no')
        alt_mobile = request.POST.get('alt_mobile_no')
        dob = request.POST.get('dob')
        joining_date = request.POST.get('joining_date')
        selected_courses = request.POST.getlist('courses')
        course_fee = request.POST.get('course_fee')
        paid_fee = request.POST.get('paid_fee')
        trainer_id = request.POST.get('trainer')
        batch_id = request.POST.get('batch')
        center_id = request.POST.get('center')


        student = Student.objects.create(
            name=name,
            mobile_no=mobile,
            alt_mobile_no=alt_mobile,
            dob=dob,
            joining_date=joining_date,
            counsellor_id=counsellor_id,
            course_fee=course_fee,
            paid_fee=paid_fee,
            trainer_id=trainer_id,
            batch_id=batch_id,
            center_id=center_id
        )
        student.courses.set(selected_courses)
        # ✅ SUCCESS MESSAGE
        messages.success(request, "Student updated successfully ✅")
        return redirect('student_detail', id=student.id)


    return render(request, 'student-registration.html',{'courses': courses,'counsellors': counsellors,'trainers': trainers, 'batches': batches,'centers': centers})



def record(request):
    students = Student.objects.all()
    query = request.GET.get('q')

    # 🔥 GET FILTER VALUE
    status_filter = request.GET.get('status')
    search = request.GET.get('search')

    # 🔥 PAYMENT STATUS FILTER (MAPPED LOGIC)
    if status_filter:
        if status_filter == "Paid":
            students = [
                s for s in students if s.remaining_fee == 0
            ]

        elif status_filter == "Pending":
            students = [
                s for s in students if s.total_paid == 0
            ]

        elif status_filter == "Partial":
            students = [
                s for s in students if 0 < s.remaining_fee < (s.course_fee or 0)
            ]

            # 🔥 SEARCH (DB LEVEL)
        if search:
            students = students.filter(name__icontains=search)

    if query:
        students = students.filter(
            Q(name__icontains=query) |
            Q(mobile_no__icontains=query) |
            Q(counsellor__name__icontains=query) |
            Q(courses__name__icontains=query)
        ).distinct()

    return render(request, 'record.html',{'students':students,'status_filter': status_filter,'search': search})


def student_detail(request, id):
    from datetime import date
    student = get_object_or_404(Student, id=id)
    trainers = Trainer.objects.all()
    batches = Batch.objects.all()
    centers = Center.objects.all()
    today = date.today()
    attendance_dict = {
        a.student_id: a.status
        for a in Attendance.objects.filter(date=today)
    }
    attendance = Attendance.objects.filter(student=student).order_by('-date')
    if request.method == "POST":
        trainer_id = request.POST.get('trainer')
        batch_id = request.POST.get('batch')
        center_id = request.POST.get('center')

        student.trainer_id = trainer_id
        student.batch_id = batch_id
        student.center_id = center_id
        student.save()
        # attendance = Attendance.objects.filter(student=student)


        return JsonResponse({'status': 'success'})

    return render(request, 'student_detail.html', {
        'student': student,
        'trainers': trainers,
        'batches': batches,
        'centers': centers,
        "attendance_dict": attendance_dict,
        'attendance': attendance,
        'show_student_nav': True
    })
def update_student(request, id):

    student = get_object_or_404(Student, id=id)
    trainers = Trainer.objects.all()
    batches = Batch.objects.all()
    centers = Center.objects.all()
    courses = Course.objects.all()

    if request.method == "POST":
        student.name = request.POST.get('name')
        student.mobile_no = request.POST.get('mobile_no')
        student.trainer_id = request.POST.get('trainer')
        student.batch_id = request.POST.get('batch')
        student.center_id = request.POST.get('center')

        student.course_fee = request.POST.get('course_fee')
        student.paid_fee = request.POST.get('paid_fee')
        student.status = request.POST.get('status')


        student.save()


        # ManyToMany update
        selected_courses = list(set(request.POST.getlist('courses')))
        # Remove only unselected courses
        StudentCourse.objects.filter(student=student).exclude(course_id__in=selected_courses).delete()

        for course_id in selected_courses:
            is_completed = request.POST.get(f'completed_{course_id}') == 'on'
            raw_date = request.POST.get(f'date_{course_id}')
            completion_date = raw_date if raw_date else None
            # Auto set today's date if completed but no date given
            if is_completed and not completion_date:
                completion_date = today_date.today()

            StudentCourse.objects.update_or_create(
                student=student,
                course_id=course_id,
                defaults={
                    'is_completed': is_completed,
                    'completion_date': completion_date
                }
            )

        return redirect('student_detail', id=student.id)

    return render(request, 'student_update.html', {
        'student': student,
        'trainers': trainers,
        'batches': batches,
        'centers': centers,
        'courses': courses,
        'show_student_nav': True
    })

def add_installment(request, student_id):
    student = get_object_or_404(Student, id=student_id)

    if request.method == "POST":
        Installment.objects.create(
            student=student,
            installment_no=request.POST.get('installment_no'),
            installment_date=request.POST.get('installment_date'),
            amount=request.POST.get('amount')
        )

        return redirect('student_detail', id=student.id)

    return render(request, 'installment_add.html', {'student': student,'show_student_nav': True})


def trainer_batches(request, trainer_id):
    trainer = Trainer.objects.get(id=trainer_id)
    batches = Batch.objects.filter(trainer=trainer)

    return render(request, "batch_list.html", {
        "trainer": trainer,
        "batches": batches
    })

def batch_students(request, batch_id):
    batch = Batch.objects.get(id=batch_id)
    students = Student.objects.filter(batch=batch)

    today = date.today()

    attendance_map = {
        a.student_id: a.status
        for a in Attendance.objects.filter(date=today)
    }

    if request.method == "POST":
        for student in students:
            status = request.POST.get(f"status_{student.id}")

            if status:
                Attendance.objects.update_or_create(
                    student=student,
                    date=today,
                    defaults={'status': status}
                )

        return redirect(request.path)

    return render(request, "batch_students.html", {
        "batch": batch,
        "students": students,
        "attendance_map": attendance_map,
        "today": today
    })

def trainer_list(request):
    trainers = Trainer.objects.all()
    return render(request, 'trainer/trainer_list.html', {
        'trainers': trainers
    })

def trainer_detail(request, id):
    trainer = Trainer.objects.get(id=id)
    schedules = TrainerSchedule.objects.filter(trainer=trainer)

    return render(request, 'trainer/trainer_detail.html', {
        'trainer': trainer,
        'schedules': schedules
    })

def add_schedule(request, trainer_id):
    trainer = Trainer.objects.get(id=trainer_id)

    if request.method == "POST":
        center_id = request.POST.get('center')
        batch_id = request.POST.get('batch')
        start = request.POST.get('start_time')
        end = request.POST.get('end_time')

        TrainerSchedule.objects.create(
            trainer=trainer,
            center_id=center_id,
            batch_id=batch_id,
            start_time=start,
            end_time=end
        )

        return redirect(f"/trainer/{trainer.id}/")

    centers = Center.objects.all()
    batches = Batch.objects.all()

    return render(request, 'trainer/add_schedule.html', {
        'trainer': trainer,
        'centers': centers,
        'batches': batches
    })

def add_trainer(request):
    courses = Course.objects.all()
    if request.method == "POST":
        trainer = Trainer.objects.create(
            name=request.POST.get('name'),
            age=request.POST.get('age') or None,
            dob=request.POST.get('dob') or None,
            mobile=request.POST.get('mobile'),
            joining_date=request.POST.get('joining_date') or None,
        )
        # 🔥 Add courses
        selected_courses = request.POST.getlist('courses')
        trainer.courses.set(selected_courses)
        return redirect('trainer_list')

    return render(request, 'trainer/add_trainer.html',{'courses': courses})

def delete_trainer(request, id):
    trainer = Trainer.objects.get(id=id)
    trainer.delete()
    return redirect('trainer_list')

def update_trainer(request, id):
    trainer = Trainer.objects.get(id=id)
    courses = Course.objects.all()
    if request.method == "POST":
        trainer.name = request.POST.get('name')
        trainer.age = request.POST.get('age') or None
        trainer.dob = request.POST.get('dob') or None
        trainer.mobile = request.POST.get('mobile')
        trainer.joining_date = request.POST.get('joining_date') or None

        trainer.save()

        # 🔥 Update courses
        selected_courses = request.POST.getlist('courses')
        trainer.courses.set(selected_courses)
        return redirect('trainer_detail', id=trainer.id)

    return render(request, 'trainer/update_trainer.html', {
        'trainer': trainer,"courses": courses
    })


from datetime import date

def attendance_batches(request):
    batches = Batch.objects.all().order_by('time')
    centers = Center.objects.all()

    batch_data = []

    for batch in batches:
        center_list = []

        for center in centers:

            # ✅ TOTAL STUDENTS (NOT PRESENT)
            total_students = Student.objects.filter(
                batch=batch,
                center=center
            ).count()

            # ✅ LOGISTICS
            log = CenterLogistics.objects.filter(center=center).first()
            working_pc = log.working_pc if log else 0

            # 🔥 FINAL CALCULATION
            available_pc = working_pc - total_students

            center_list.append({
                'center': center.name,
                'available': available_pc,
                'students': total_students
            })

        batch_data.append({
            'batch': batch,
            'centers': center_list
        })

    return render(request, 'attendance/batches.html', {
        'batch_data': batch_data
    })


def attendance_batch_detail(request, batch_id):
    batch = Batch.objects.get(id=batch_id)
    schedules = TrainerSchedule.objects.filter(batch=batch).select_related('trainer', 'center')
    data = {}

    for s in schedules:
        center = s.center
        if center.id not in data:
            data[center.id] = {
                'center_name': center.name,
                'trainers': [],
                'total_students': 0
            }
        # 🔥 count students for this trainer + batch + center
        student_count = Student.objects.filter(
            trainer=s.trainer,
            batch=batch,
            center=center
        ).count()

        data[center.id]['trainers'].append({
            'trainer': s.trainer,
            'count': student_count
        })

        # 🔥 add to center total
        data[center.id]['total_students'] += student_count

    return render(request, 'attendance/batch_detail.html', {
        'batch': batch,
        'data': data.values()
    })


def mark_attendance(request, trainer_id, batch_id):
    trainer = Trainer.objects.get(id=trainer_id)
    batch = Batch.objects.get(id=batch_id)
    students = Student.objects.filter(trainer=trainer, batch=batch)
    today = date.today()
    attendance_map = Attendance.objects.filter(date=today)
    attendance_dict = {a.student_id: a.status for a in attendance_map}

    if request.method == "POST":
        for student in students:
            status = request.POST.get(f"status_{student.id}")

            if status:
                Attendance.objects.update_or_create(
                    student=student,
                    date=today,
                    defaults={'status': status}
                )

        return redirect('attendance_batches')

    return render(request, 'attendance/mark_attendance.html', {
        'students': students,
        'trainer': trainer,
        'batch': batch,
        'attendance_dict': attendance_dict,
        'today': today
    })

def update_schedule(request, id):
    schedule = get_object_or_404(TrainerSchedule, id=id)

    centers = Center.objects.all()
    batches = Batch.objects.all()

    if request.method == "POST":
        try:
            schedule.center_id = request.POST.get('center')
            schedule.batch_id = request.POST.get('batch')
            schedule.start_time = request.POST.get('start_time')
            schedule.end_time = request.POST.get('end_time')

            schedule.save()  # will trigger your conflict validation

            return redirect('trainer_detail', id=schedule.trainer.id)

        except ValidationError as e:
            return render(request, 'trainer/update_schedule.html', {
                'schedule': schedule,
                'centers': centers,
                'batches': batches,
                'error': e.messages
            })

    return render(request, 'trainer/update_schedule.html', {
        'schedule': schedule,
        'centers': centers,
        'batches': batches
    })

def delete_schedule(request, id):
    schedule = get_object_or_404(TrainerSchedule, id=id)
    trainer_id = schedule.trainer.id

    schedule.delete()

    return redirect('trainer_detail', id=trainer_id)


# Logistic Work -- Record of No. of PC Available.
def logistics_dashboard(request):
    centers = Center.objects.all()

    for center in centers:
        CenterLogistics.objects.get_or_create(center=center)

    logs = CenterLogistics.objects.select_related('center')

    return render(request, 'logistics/dashboard.html', {
        'logs': logs
    })

def update_logistics(request, id, action):
    log = CenterLogistics.objects.get(id=id)


    log.save()
    return redirect('logistics_dashboard')

@csrf_exempt
def update_total_pc(request, id):
    if request.method == "POST":
        log = CenterLogistics.objects.get(id=id)

        new_total = int(request.POST.get('total_pc', 0))
        log.total_pc = new_total
        log.save()

        return JsonResponse({
            'status': 'success',
            'total_pc': log.total_pc,
            'working_pc': log.working_pc
        })

def update_repair_pc(request, id):
    if request.method == "POST":
        log = get_object_or_404(CenterLogistics, id=id)

        new_repair = int(request.POST.get('repair_pc', 0))
        log.repair_pc = new_repair
        log.save()

        return JsonResponse({
            'status': 'success',
            'repair_pc': log.repair_pc,
            'working_pc': log.working_pc
        })

