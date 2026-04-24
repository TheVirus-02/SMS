from django.urls import path

from student import views

urlpatterns = [
    path("trainer/", views.trainer_list, name="trainer_list"),
    path("trainer/add/", views.add_trainer, name="add_trainer"),
    path("trainer/schedules/", views.trainer_schedule_page, name="trainer_schedule_page"),
    path("trainer/<int:id>/", views.trainer_detail, name="trainer_detail"),
    path("trainer/update/<int:id>/", views.update_trainer, name="update_trainer"),
    path("trainer/delete/<int:id>/", views.delete_trainer, name="delete_trainer"),
    path("schedule/add/", views.add_schedule, name="schedule_add_global"),
    path("trainer/<int:trainer_id>/schedule/add/", views.add_schedule, name="add_schedule"),
    path("schedule/<int:id>/update/", views.update_schedule, name="update_schedule"),
    path("schedule/<int:id>/delete/", views.delete_schedule, name="delete_schedule"),
]
