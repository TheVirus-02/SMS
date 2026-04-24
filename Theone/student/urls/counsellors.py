from django.urls import path

from student import views

urlpatterns = [
    path("counsellors/", views.counsellor_list, name="counsellor_list"),
    path("counsellors/add/", views.add_counsellor, name="add_counsellor"),
    path("counsellors/<int:id>/", views.counsellor_detail, name="counsellor_detail"),
    path("counsellors/<int:id>/edit/", views.update_counsellor, name="update_counsellor"),
    path("counsellors/<int:id>/delete/", views.delete_counsellor, name="delete_counsellor"),
]
