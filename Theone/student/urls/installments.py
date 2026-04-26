from django.urls import path

from student import views

urlpatterns = [
    path("student/<int:student_id>/installment/add/", views.add_installment, name="add_installment"),
    path("student/<int:student_id>/admission-receipt/", views.admission_receipt, name="admission_receipt"),
    path("installment/<int:installment_id>/edit/", views.edit_installment, name="edit_installment"),
    path("installment/<int:installment_id>/delete/", views.delete_installment, name="delete_installment"),
    path("installment/<int:installment_id>/receipt/", views.installment_receipt, name="installment_receipt"),
]
