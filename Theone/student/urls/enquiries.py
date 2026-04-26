from django.urls import path

from student import views

urlpatterns = [
    path("enquiries/", views.enquiry_list, name="enquiry_list"),
    path("enquiries/export/", views.export_enquiries_csv, name="export_enquiries_csv"),
    path("enquiries/today-follow-up/", views.today_follow_up, name="today_follow_up"),
    path("enquiries/add/", views.add_enquiry, name="add_enquiry"),
    path("enquiries/<int:id>/", views.enquiry_detail, name="enquiry_detail"),
    path("enquiries/<int:id>/edit/", views.update_enquiry, name="update_enquiry"),
    path("enquiries/<int:id>/delete/", views.delete_enquiry, name="delete_enquiry"),
    path("enquiries/<int:id>/convert/", views.convert_enquiry, name="convert_enquiry"),
]
