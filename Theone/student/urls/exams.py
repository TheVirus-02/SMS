from django.urls import path

from student import views

urlpatterns = [
    path("exam/register/<int:student_id>/", views.register_exam, name="register_exam"),
    path("exam/dashboard/", views.exam_dashboard, name="exam_dashboard"),
    path("exam/marks/<int:reg_id>/", views.enter_marks, name="enter_marks"),
    path("certificate/dashboard/", views.certificate_dashboard, name="certificate_dashboard"),
    path("certificate/<int:reg_id>/toggle/", views.toggle_certificate_status, name="toggle_certificate_status"),
]
