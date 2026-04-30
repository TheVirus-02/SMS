from django.urls import path

from student import views

urlpatterns = [
    path("portal/login/", views.portal_login, name="portal_login"),
    path("portal/logout/", views.portal_logout, name="portal_logout"),
    path("portal/counsellor/", views.counsellor_dashboard, name="counsellor_dashboard"),
    path("portal/trainer/", views.trainer_dashboard, name="trainer_dashboard"),
]
