from django import template


register = template.Library()


@register.simple_tag
def url_name_active(request, *url_names):
    """Return whether the current resolved URL name belongs to a menu group."""
    resolver_match = getattr(request, 'resolver_match', None)
    current_url_name = getattr(resolver_match, 'url_name', None)
    return current_url_name in url_names
