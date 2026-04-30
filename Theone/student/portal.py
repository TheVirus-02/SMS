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
    if user.is_superuser or user.is_staff:
        return ROLE_ADMIN
    if hasattr(user, "counsellor_profile"):
        return ROLE_COUNSELLOR
    if hasattr(user, "trainer_profile"):
        return ROLE_TRAINER
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


def user_can_manage_fees(user):
    return get_portal_role(user) in {ROLE_ADMIN, ROLE_COUNSELLOR}


def user_can_view_exams(user):
    return get_portal_role(user) == ROLE_ADMIN


def user_can_manage_batches(user):
    return get_portal_role(user) in {ROLE_ADMIN, ROLE_COUNSELLOR}


def user_can_access_attendance(user):
    return get_portal_role(user) in {ROLE_ADMIN, ROLE_TRAINER}


def user_can_access_logistics(user):
    return get_portal_role(user) in {ROLE_ADMIN, ROLE_COUNSELLOR, ROLE_TRAINER}


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
        if not counsellor or not counsellor.center_id:
            return queryset.none()
        return queryset.filter(center_id=counsellor.center_id)
    if role == ROLE_TRAINER:
        trainer = get_trainer_for_user(user)
        if not trainer:
            return queryset.none()
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
        if counsellor.center_id:
            return queryset.filter(
                Q(assigned_counsellor=counsellor) | Q(preferred_center_id=counsellor.center_id)
            ).distinct()
        return queryset.filter(assigned_counsellor=counsellor)
    return queryset.none()


def scope_centers_for_user(user, queryset=None):
    queryset = queryset or Center.objects.all()
    role = get_portal_role(user)
    if role == ROLE_ADMIN:
        return queryset
    if role == ROLE_COUNSELLOR:
        counsellor = get_counsellor_for_user(user)
        if not counsellor or not counsellor.center_id:
            return queryset.none()
        return queryset.filter(id=counsellor.center_id)
    if role == ROLE_TRAINER:
        trainer = get_trainer_for_user(user)
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
        if not counsellor or not counsellor.center_id:
            return queryset.none()
        return queryset.filter(
            Q(student__center_id=counsellor.center_id) | Q(trainerschedule__center_id=counsellor.center_id)
        ).distinct()
    if role == ROLE_TRAINER:
        trainer = get_trainer_for_user(user)
        if not trainer:
            return queryset.none()
        return queryset.filter(id=trainer.id)
    return queryset.none()


def scope_batches_for_user(user, queryset=None):
    queryset = queryset or Batch.objects.all()
    role = get_portal_role(user)
    if role == ROLE_ADMIN:
        return queryset
    if role == ROLE_COUNSELLOR:
        counsellor = get_counsellor_for_user(user)
        if not counsellor or not counsellor.center_id:
            return queryset.none()
        return queryset.filter(
            Q(student__center_id=counsellor.center_id) | Q(trainerschedule__center_id=counsellor.center_id)
        ).distinct()
    if role == ROLE_TRAINER:
        trainer = get_trainer_for_user(user)
        if not trainer:
            return queryset.none()
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
        return queryset.filter(id=counsellor.id)
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
