from django.urls import path

from student import views

urlpatterns = [
    path("courses/", views.course_list, name="course_list"),
    path("courses/add/", views.add_course, name="add_course"),
    path("courses/<int:id>/", views.course_detail, name="course_detail"),
    path("courses/<int:id>/edit/", views.update_course, name="update_course"),
    path("courses/<int:id>/delete/", views.delete_course, name="delete_course"),
]
