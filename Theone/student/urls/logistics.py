from django.urls import path

from student import views

urlpatterns = [
    path("logistics/", views.logistics_dashboard, name="logistics_dashboard"),
    path("logistics/update-total/<int:id>/", views.update_total_pc, name="update_total_pc"),
    path("logistics/update-repair/<int:id>/", views.update_repair_pc, name="update_repair_pc"),
]

