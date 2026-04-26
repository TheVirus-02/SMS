from django.urls import path

from student import views

urlpatterns = [
    path("automation/reminders/", views.reminder_center, name="reminder_center"),
    path("automation/reminders/student/<int:student_id>/fee/", views.send_fee_reminder, name="send_fee_reminder"),
    path("automation/reminders/bulk-fee/", views.send_bulk_fee_reminders, name="send_bulk_fee_reminders"),
    path("automation/reminders/enquiry/<int:enquiry_id>/follow-up/", views.send_enquiry_follow_up_reminder, name="send_enquiry_follow_up_reminder"),
    path("automation/reminders/bulk-follow-up/", views.send_bulk_follow_up_reminders, name="send_bulk_follow_up_reminders"),
    path("automation/logs/", views.communication_log_list, name="communication_log_list"),
    path("automation/daily-summary/", views.daily_summary, name="daily_summary"),
    path("automation/analytics/", views.staff_center_analytics, name="staff_center_analytics"),
]
