from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import AuditLog


def permission_required(permission):
    """A 403-producing permission decorator with superuser support via has_perm."""
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.has_perm(permission):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (forwarded.split(',')[0].strip() if forwarded
            else request.META.get('REMOTE_ADDR'))


def audit(request, action, module, obj='', **details):
    AuditLog.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        action=action,
        module=module,
        object_repr=str(obj)[:255],
        details=details,
        ip_address=client_ip(request),
    )
