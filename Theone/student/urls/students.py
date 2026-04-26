from django.urls import path

from student import views

urlpatterns = [
    path("student-registration", views.student_registration, name="student_registration"),
    path("record/", views.record, name="record"),
    path("record/export/", views.export_student_records_csv, name="export_student_records_csv"),
    path("fees/pending/", views.pending_fee_list, name="pending_fee_list"),
    path("fees/pending/export/", views.export_pending_fees_csv, name="export_pending_fees_csv"),
    path("reports/today-collection/", views.today_collection_dashboard, name="today_collection_dashboard"),
    path("reports/today-collection/export/", views.export_today_collection_csv, name="export_today_collection_csv"),
    path("reports/daily-admissions/", views.daily_admissions_report, name="daily_admissions_report"),
    path("reports/daily-admissions/export/", views.export_daily_admissions_csv, name="export_daily_admissions_csv"),
    path("reports/overview/", views.reporting_dashboard, name="reporting_dashboard"),
    path("student/<int:id>/", views.student_detail, name="student_detail"),
    path("student/<int:id>/edit/", views.update_student, name="update_student"),
]
