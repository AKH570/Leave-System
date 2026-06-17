from django.templatetags.static import static

from .models import Employee, EmpProfile


def current_profile_picture(request):
    default_avatar_url = static('images/avatar.png')
    profile_picture_url = default_avatar_url

    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        try:
            employee = Employee.objects.select_related('extended_profile').get(user=user)
            profile, _ = EmpProfile.objects.get_or_create(employee=employee)
            if profile.profile_picture:
                profile_picture_url = profile.profile_picture.url
        except Employee.DoesNotExist:
            pass

    return {
        'current_profile_picture_url': profile_picture_url,
        'default_avatar_url': default_avatar_url,
    }
