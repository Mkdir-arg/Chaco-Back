from django import template
from django.contrib.auth.models import Group

register = template.Library()


@register.simple_tag
def get_available_groups():
    return Group.objects.all()
