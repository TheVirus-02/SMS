from django.urls import path

from student import views

urlpatterns = [
    path("student-registration", views.student_registration, name="student_registration"),
    path("record/", views.record, name="record"),
    path("student/<int:id>/", views.student_detail, name="student_detail"),
    path("student/<int:id>/edit/", views.update_student, name="update_student"),
]

