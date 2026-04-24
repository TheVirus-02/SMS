from django.urls import path

from student import views

urlpatterns = [
    path("batches/", views.batch_list, name="batch_list"),
    path("batches/add/", views.add_batch, name="add_batch"),
    path("batches/create-standard/", views.create_standard_batches, name="create_standard_batches"),
    path("batches/<int:id>/", views.batch_detail, name="batch_detail"),
    path("batches/<int:id>/edit/", views.update_batch, name="update_batch"),
    path("batches/<int:id>/delete/", views.delete_batch, name="delete_batch"),
    path("batches/<int:batch_id>/assignments/add/", views.add_batch_assignment, name="add_batch_assignment"),
    path("batches/assignments/<int:id>/edit/", views.update_batch_assignment, name="update_batch_assignment"),
    path("batches/assignments/<int:id>/delete/", views.delete_batch_assignment, name="delete_batch_assignment"),
]
