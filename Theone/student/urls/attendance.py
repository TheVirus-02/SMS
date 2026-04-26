from django.urls import path

from student import views

urlpatterns = [
    path("attendance/", views.attendance_batches, name="attendance_batches"),
    path("attendance/batch/<int:batch_id>/", views.attendance_batch_detail, name="attendance_batch_detail"),
    path("attendance/daily-absentees/", views.daily_absentees, name="daily_absentees"),
    path("attendance/monthly-summary/", views.attendance_monthly_summary, name="attendance_monthly_summary"),
    path("attendance/mark/<int:trainer_id>/<int:batch_id>/", views.mark_attendance, name="mark_attendance"),
    path("attendance/save/<int:student_id>/", views.save_attendance_record, name="save_attendance_record"),
    path("trainer/<int:trainer_id>/batches/", views.trainer_batches, name="trainer_batches"),
    path("batch/<int:batch_id>/students/", views.batch_students, name="batch_students"),
]
