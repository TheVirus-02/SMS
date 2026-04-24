from django.urls import path

from student import views

urlpatterns = [
    path("student/<int:student_id>/installment/add/", views.add_installment, name="add_installment"),
]

