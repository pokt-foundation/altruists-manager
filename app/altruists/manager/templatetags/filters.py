from django import template
from django.template.defaultfilters import stringfilter
from django.utils import timezone
import calendar
from datetime import datetime

register = template.Library()

@register.filter
@stringfilter
def safeURL(value):
    if "@" in value:
        value = value[value.index('@')+1:]
    else:
      value = value[value.index('//')+2:]
    return value

@register.simple_tag
def n_ago_first(months_ago):
    today = timezone.now()
    N_months_ago = (today.month - months_ago) % 12 or 12

    year = today.year - N_months_ago // 12
    # month = (today.month - N_months_ago) % 12 or 12

    return datetime(year, N_months_ago, 1).strftime('%Y-%m-%d')

@register.simple_tag
def n_ago_last(months_ago):
    today = timezone.now()
    N_months_ago = (today.month - months_ago) % 12 or 12
    year = today.year - N_months_ago // 12
    # month = (today.month - N_months_ago) % 12 or 12
    # get the number of days in the resulting month
    num_days = calendar.monthrange(year, N_months_ago)[1]

    return datetime(year, N_months_ago, num_days).strftime('%Y-%m-%d')
