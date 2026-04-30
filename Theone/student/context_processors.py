from student.portal import (
    ROLE_ADMIN,
    ROLE_COUNSELLOR,
    ROLE_TRAINER,
    get_counsellor_for_user,
    get_portal_role,
    get_trainer_for_user,
    user_can_access_enquiries,
    user_can_access_student_records,
    user_can_access_student_registration,
    user_can_access_attendance,
    user_can_access_logistics,
    user_can_access_reminder_center,
    user_can_convert_enquiries,
    user_can_edit_students,
    user_can_manage_batches,
    user_can_manage_fees,
    user_can_send_fee_reminders,
    user_can_send_follow_up_reminders,
    user_can_view_reports,
    user_can_view_exams,
)


def portal_context(request):
    role = get_portal_role(request.user)
    counsellor = get_counsellor_for_user(request.user) if role == ROLE_COUNSELLOR else None
    trainer = get_trainer_for_user(request.user) if role == ROLE_TRAINER else None
    display_name = request.user.get_full_name().strip() or request.user.get_username() if request.user.is_authenticated else ""
    return {
        "portal_user_role": role,
        "portal_is_admin": role == ROLE_ADMIN,
        "portal_is_counsellor": role == ROLE_COUNSELLOR,
        "portal_is_trainer": role == ROLE_TRAINER,
        "portal_can_access_student_registration": user_can_access_student_registration(request.user),
        "portal_can_access_student_records": user_can_access_student_records(request.user),
        "portal_can_edit_students": user_can_edit_students(request.user),
        "portal_can_manage_fees": user_can_manage_fees(request.user),
        "portal_can_access_enquiries": user_can_access_enquiries(request.user),
        "portal_can_convert_enquiries": user_can_convert_enquiries(request.user),
        "portal_can_manage_batches": user_can_manage_batches(request.user),
        "portal_can_access_attendance": user_can_access_attendance(request.user),
        "portal_can_access_logistics": user_can_access_logistics(request.user),
        "portal_can_access_reminder_center": user_can_access_reminder_center(request.user),
        "portal_can_send_fee_reminders": user_can_send_fee_reminders(request.user),
        "portal_can_send_follow_up_reminders": user_can_send_follow_up_reminders(request.user),
        "portal_can_view_reports": user_can_view_reports(request.user),
        "portal_can_view_exams": user_can_view_exams(request.user),
        "portal_counsellor": counsellor,
        "portal_trainer": trainer,
        "portal_display_name": display_name,
    }
