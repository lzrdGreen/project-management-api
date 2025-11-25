from django import template
from django.utils.safestring import mark_safe
import re

register = template.Library()

@register.filter
def highlight(text, search_term):
    if search_term:
        # Use regex to find and wrap the search term in a <span> with background color
        highlighted = re.sub(f'({re.escape(search_term)})', r'<span style="background-color: #e6f598;">\1</span>', text, flags=re.IGNORECASE)
        return mark_safe(highlighted)        
    return text
