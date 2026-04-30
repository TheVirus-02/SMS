from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect

from student.models import Batch, Center, Counsellor, Enquiry, Student, Trainer


ROLE_ADMIN = "admin"
ROLE_COUNSELLOR = "counsellor"
ROLE_TRAINER = "trainer"


def get_portal_role(user):
    if not getattr(user, "is_authenticated", False):
        return None
    if hasattr(user, "counsellor_profile"):
        return ROLE_COUNSELLOR
    if hasattr(user, "trainer_profile"):
        return ROLE_TRAINER
    if user.is_superuser or user.is_staff:
        return ROLE_ADMIN
    return None


def require_portal_account(user):
    role = get_portal_role(user)
    if role:
        return role
    raise PermissionDenied("This account is not linked to a portal role.")


def portal_redirect_name(user):
    role = get_portal_role(user)
    if role == ROLE_COUNSELLOR:
        return "counsellor_dashboard"
    if role == ROLE_TRAINER:
        return "trainer_dashboard"
    return "index"


def portal_login_required(view_func):
    @login_required(login_url="portal_login")
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        require_portal_account(request.user)
        return view_func(request, *args, **kwargs)

    return wrapped


def role_required(*allowed_roles):
    def decorator(view_func):
        @portal_login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            role = get_portal_role(request.user)
            if role not in allowed_roles:
                messages.error(request, "You do not have access to that page.")
                return redirect(portal_redirect_name(request.user))
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


def capability_required(capability_check, *allowed_roles):
    def decorator(view_func):
        @portal_login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            role = get_portal_role(request.user)
            if allowed_roles and role not in allowed_roles:
                messages.error(request, "You do not have access to that page.")
                return redirect(portal_redirect_name(request.user))
            if not capability_check(request.user):
                messages.error(request, "You do not have access to that page.")
                return redirect(portal_redirect_name(request.user))
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


def get_portal_profile(user):
    role = get_portal_role(user)
    if role == ROLE_COUNSELLOR:
        return get_counsellor_for_user(user)
    if role == ROLE_TRAINER:
        return get_trainer_for_user(user)
    return None


def profile_flag_enabled(user, field_name):
    role = get_portal_role(user)
    if role == ROLE_ADMIN:
        return True
    profile = get_portal_profile(user)
    return bool(profile and getattr(profile, field_name, False))


def profile_record_scope(user):
    role = get_portal_role(user)
    if role == ROLE_ADMIN:
        return "all"
    profile = get_portal_profile(user)
    return getattr(profile, "record_scope", None)


def user_can_access_student_registration(user):
    return profile_flag_enabled(user, "can_access_student_registration")


def user_can_access_student_records(user):
    return profile_flag_enabled(user, "can_access_student_records")


def user_can_edit_students(user):
    return profile_flag_enabled(user, "can_edit_students")


def user_can_manage_fees(user):
    return profile_flag_enabled(user, "can_manage_fees")


def user_can_access_enquiries(user):
    return profile_flag_enabled(user, "can_access_enquiries")


def user_can_convert_enquiries(user):
    return profile_flag_enabled(user, "can_convert_enquiries")


def user_can_view_exams(user):
    return profile_flag_enabled(user, "can_view_exams")


def user_can_view_reports(user):
    return profile_flag_enabled(user, "can_view_reports")


def user_can_manage_batches(user):
    return profile_flag_enabled(user, "can_manage_batches")


def user_can_access_attendance(user):
    return profile_flag_enabled(user, "can_access_attendance")


def user_can_access_logistics(user):
    return profile_flag_enabled(user, "can_access_logistics")


def user_can_send_fee_reminders(user):
    role = get_portal_role(user)
    if role == ROLE_ADMIN:
        return True
    if role == ROLE_COUNSELLOR:
        counsellor = get_counsellor_for_user(user)
        return bool(counsellor and counsellor.can_send_fee_reminders)
    return False


def user_can_send_follow_up_reminders(user):
    role = get_portal_role(user)
    if role == ROLE_ADMIN:
        return True
    if role == ROLE_COUNSELLOR:
        counsellor = get_counsellor_for_user(user)
        return bool(counsellor and counsellor.can_send_follow_up_reminders)
    return False


def user_can_access_reminder_center(user):
    return user_can_send_fee_reminders(user) or user_can_send_follow_up_reminders(user)


def get_counsellor_for_user(user):
    return getattr(user, "counsellor_profile", None)


def get_trainer_for_user(user):
    return getattr(user, "trainer_profile", None)


def trainer_center_ids(trainer):
    if not trainer:
        return []
    center_ids = set(
        Student.objects.filter(trainer=trainer, center_id__isnull=False).values_list("center_id", flat=True)
    )
    center_ids.update(
        trainer.trainerschedule_set.filter(center_id__isnull=False).values_list("center_id", flat=True)
    )
    return sorted(center_ids)


def scope_students_for_user(user, queryset=None):
    queryset = queryset or Student.objects.all()
    role = get_portal_role(user)
    if role == ROLE_ADMIN:
        return queryset
    if role == ROLE_COUNSELLOR:
        counsellor = get_counsellor_for_user(user)
        scope = profile_record_scope(user)
        if not counsellor:
            return queryset.none()
        if scope == Counsellor.RECORD_SCOPE_ALL:
            return queryset
        if scope == Counsellor.RECORD_SCOPE_ASSIGNED:
            return queryset.filter(counsellor_id=counsellor.id)
        if not counsellor.center_id:
            return queryset.none()
        return queryset.filter(center_id=counsellor.center_id)
    if role == ROLE_TRAINER:
        trainer = get_trainer_for_user(user)
        if not trainer:
            return queryset.none()
        scope = profile_record_scope(user)
        if scope == Trainer.RECORD_SCOPE_ALL:
            return queryset
        if scope == Trainer.RECORD_SCOPE_CENTER:
            return queryset.filter(center_id__in=trainer_center_ids(trainer))
        return queryset.filter(trainer=trainer)
    return queryset.none()


def scope_enquiries_for_user(user, queryset=None):
    queryset = queryset or Enquiry.objects.all()
    role = get_portal_role(user)
    if role == ROLE_ADMIN:
        return queryset
    if role == ROLE_COUNSELLOR:
        counsellor = get_counsellor_for_user(user)
        if not counsellor:
            return queryset.none()
        scope = profile_record_scope(user)
        if scope == Counsellor.RECORD_SCOPE_ALL:
            return queryset
        if scope == Counsellor.RECORD_SCOPE_ASSIGNED:
            return queryset.filter(assigned_counsellor=counsellor)
        if counsellor.center_id:
            return queryset.filter(
                Q(assigned_counsellor=counsellor) | Q(preferred_center_id=counsellor.center_id)
            ).distinct()
        return queryset.filter(assigned_counsellor=counsellor)
    if role == ROLE_TRAINER:
        trainer = get_trainer_for_user(user)
        if not trainer:
            return queryset.none()
        scope = profile_record_scope(user)
        if scope == Trainer.RECORD_SCOPE_ALL:
            return queryset
        if scope == Trainer.RECORD_SCOPE_CENTER:
            return queryset.filter(preferred_center_id__in=trainer_center_ids(trainer))
    return queryset.none()


def scope_centers_for_user(user, queryset=None):
    queryset = queryset or Center.objects.all()
    role = get_portal_role(user)
    if role == ROLE_ADMIN:
        return queryset
    if role == ROLE_COUNSELLOR:
        counsellor = get_counsellor_for_user(user)
        scope = profile_record_scope(user)
        if not counsellor:
            return queryset.none()
        if scope == Counsellor.RECORD_SCOPE_ALL:
            return queryset
        if scope == Counsellor.RECORD_SCOPE_ASSIGNED:
            return queryset.filter(
                Q(student__counsellor_id=counsellor.id) | Q(enquiry__assigned_counsellor_id=counsellor.id)
            ).distinct()
        if not counsellor.center_id:
            return queryset.none()
        return queryset.filter(id=counsellor.center_id)
    if role == ROLE_TRAINER:
        trainer = get_trainer_for_user(user)
        if not trainer:
            return queryset.none()
        scope = profile_record_scope(user)
        if scope == Trainer.RECORD_SCOPE_ALL:
            return queryset
        center_ids = trainer_center_ids(trainer)
        return queryset.filter(id__in=center_ids)
    return queryset.none()


def scope_trainers_for_user(user, queryset=None):
    queryset = queryset or Trainer.objects.all()
    role = get_portal_role(user)
    if role == ROLE_ADMIN:
        return queryset
    if role == ROLE_COUNSELLOR:
        counsellor = get_counsellor_for_user(user)
        scope = profile_record_scope(user)
        if not counsellor:
            return queryset.none()
        if scope == Counsellor.RECORD_SCOPE_ALL:
            return queryset
        if scope == Counsellor.RECORD_SCOPE_ASSIGNED:
            return queryset.filter(student__counsellor_id=counsellor.id).distinct()
        if not counsellor.center_id:
            return queryset.none()
        return queryset.filter(
            Q(student__center_id=counsellor.center_id) | Q(trainerschedule__center_id=counsellor.center_id)
        ).distinct()
    if role == ROLE_TRAINER:
        trainer = get_trainer_for_user(user)
        if not trainer:
            return queryset.none()
        scope = profile_record_scope(user)
        if scope == Trainer.RECORD_SCOPE_ALL:
            return queryset
        if scope == Trainer.RECORD_SCOPE_CENTER:
            return queryset.filter(
                Q(student__center_id__in=trainer_center_ids(trainer))
                | Q(trainerschedule__center_id__in=trainer_center_ids(trainer))
            ).distinct()
        return queryset.filter(id=trainer.id)
    return queryset.none()


def scope_batches_for_user(user, queryset=None):
    queryset = queryset or Batch.objects.all()
    role = get_portal_role(user)
    if role == ROLE_ADMIN:
        return queryset
    if role == ROLE_COUNSELLOR:
        counsellor = get_counsellor_for_user(user)
        scope = profile_record_scope(user)
        if not counsellor:
            return queryset.none()
        if scope == Counsellor.RECORD_SCOPE_ALL:
            return queryset
        if scope == Counsellor.RECORD_SCOPE_ASSIGNED:
            return queryset.filter(student__counsellor_id=counsellor.id).distinct()
        if not counsellor.center_id:
            return queryset.none()
        return queryset.filter(
            Q(student__center_id=counsellor.center_id) | Q(trainerschedule__center_id=counsellor.center_id)
        ).distinct()
    if role == ROLE_TRAINER:
        trainer = get_trainer_for_user(user)
        if not trainer:
            return queryset.none()
        scope = profile_record_scope(user)
        if scope == Trainer.RECORD_SCOPE_ALL:
            return queryset
        if scope == Trainer.RECORD_SCOPE_CENTER:
            return queryset.filter(
                Q(student__center_id__in=trainer_center_ids(trainer))
                | Q(trainerschedule__center_id__in=trainer_center_ids(trainer))
            ).distinct()
        return queryset.filter(
            Q(student__trainer=trainer) | Q(trainerschedule__trainer=trainer)
        ).distinct()
    return queryset.none()


def scope_counsellors_for_user(user, queryset=None):
    queryset = queryset or Counsellor.objects.all()
    role = get_portal_role(user)
    if role == ROLE_ADMIN:
        return queryset
    if role == ROLE_COUNSELLOR:
        counsellor = get_counsellor_for_user(user)
        if not counsellor:
            return queryset.none()
        scope = profile_record_scope(user)
        if scope == Counsellor.RECORD_SCOPE_ALL:
            return queryset
        if scope == Counsellor.RECORD_SCOPE_CENTER and counsellor.center_id:
            return queryset.filter(center_id=counsellor.center_id)
        return queryset.filter(id=counsellor.id)
    if role == ROLE_TRAINER:
        trainer = get_trainer_for_user(user)
        if not trainer:
            return queryset.none()
        scope = profile_record_scope(user)
        if scope == Trainer.RECORD_SCOPE_ALL:
            return queryset
        if scope == Trainer.RECORD_SCOPE_CENTER:
            return queryset.filter(center_id__in=trainer_center_ids(trainer)).distinct()
    return queryset.none()


def get_student_for_user_or_404(user, student_id, queryset=None):
    scoped_queryset = scope_students_for_user(user, queryset or Student.objects.all())
    return get_object_or_404(scoped_queryset, id=student_id)


def get_enquiry_for_user_or_404(user, enquiry_id, queryset=None):
    scoped_queryset = scope_enquiries_for_user(user, queryset or Enquiry.objects.all())
    return get_object_or_404(scoped_queryset, id=enquiry_id)


def get_batch_for_user_or_404(user, batch_id, queryset=None):
    scoped_queryset = scope_batches_for_user(user, queryset or Batch.objects.all())
    return get_object_or_404(scoped_queryset, id=batch_id)


def get_trainer_for_user_or_404(user, trainer_id, queryset=None):
    scoped_queryset = scope_trainers_for_user(user, queryset or Trainer.objects.all())
    return get_object_or_404(scoped_queryset, id=trainer_id)


def get_counsellor_for_user_or_404(user, counsellor_id, queryset=None):
    scoped_queryset = scope_counsellors_for_user(user, queryset or Counsellor.objects.all())
    return get_object_or_404(scoped_queryset, id=counsellor_id)
