'''
Created on Oct 8, 2017

@author: theo
'''
from django import template
register = template.Library()

@register.simple_tag
def bootstrap_alert(tags):
    return 'danger' if tags == 'error' else tags

