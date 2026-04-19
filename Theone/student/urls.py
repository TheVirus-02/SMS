from django.contrib import admin
from django.urls import path,include
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('student-registration', views.student_registration, name='student_registration'),
    path('record/',views.record,name='record'),
    path('student/<int:id>/', views.student_detail, name='student_detail'),
    path('student/<int:id>/edit/', views.update_student, name='update_student'),
    path('student/<int:student_id>/installment/add/', views.add_installment, name='add_installment'),
    path('trainer/', views.trainer_list, name='trainer_list'),
    path('trainer/<int:id>/', views.trainer_detail, name='trainer_detail'),
    path('trainer/<int:trainer_id>/schedule/add/', views.add_schedule, name='add_schedule'),
    path('trainer/add/', views.add_trainer, name='add_trainer'),
    path('trainer/delete/<int:id>/', views.delete_trainer, name='delete_trainer'),
    path('trainer/update/<int:id>/', views.update_trainer, name='update_trainer'),
    path('attendance/', views.attendance_batches, name='attendance_batches'),
    path('attendance/batch/<int:batch_id>/', views.attendance_batch_detail, name='attendance_batch_detail'),
    path('attendance/mark/<int:trainer_id>/<int:batch_id>/', views.mark_attendance, name='mark_attendance'),
    path('trainer/<int:trainer_id>/schedule/add/', views.add_schedule, name='add_schedule'),
    path('schedule/<int:id>/update/', views.update_schedule, name='update_schedule'),
    path('schedule/<int:id>/delete/', views.delete_schedule, name='delete_schedule'),
    path('logistics/', views.logistics_dashboard, name='logistics_dashboard'),
    # path('logistics/update/<int:id>/<str:action>/', views.update_logistics, name='update_logistics'),
    path('logistics/update-total/<int:id>/', views.update_total_pc, name='update_total_pc'),
    path('logistics/update-repair/<int:id>/', views.update_repair_pc, name='update_repair_pc'),

]