from django.templatetags.static import static

from .models import Employee, EmpProfile, LeaveRequest


def current_profile_picture(request):
    default_avatar_url = static('images/avatar.png')
    profile_picture_url = default_avatar_url

    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        try:
            employee = Employee.objects.select_related('extended_profile').get(user=user)
            try:
                profile = employee.extended_profile
            except EmpProfile.DoesNotExist:
                profile = None
            if profile and profile.profile_picture:
                profile_picture_url = profile.profile_picture.url
        except Employee.DoesNotExist:
            pass

    return {
        'current_profile_picture_url': profile_picture_url,
        'default_avatar_url': default_avatar_url,
    }


def pending_leave_notifications(request):
    """Provide the navbar bell with pending requests visible to this user."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {
            'pending_leave_count': 0,
            'recent_pending_leaves': (),
        }

    pending_leaves = LeaveRequest.objects.filter(status='PENDING')
    is_admin = user.is_superuser or user.is_staff or getattr(user, 'role', '') == 'ADMIN'
    if not is_admin:
        pending_leaves = pending_leaves.filter(employee__user=user)

    recent_pending_leaves = pending_leaves.select_related(
        'employee__user',
        'leave_type',
    ).order_by('-applied_at')[:5]

    return {
        'pending_leave_count': pending_leaves.count(),
        'recent_pending_leaves': recent_pending_leaves,
    }
