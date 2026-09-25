from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    if dictionary and key in dictionary:
        return dictionary.get(key)
    return None

@register.filter
def is_task_allowed(task, date_obj):
    """Checks if a task is allowed/scheduled on a given datetime.date object."""
    if not task.allowed_days:
        return True
    # Python's weekday(): Mon=0 ... Sun=6
    # Our Sunday-based index: Sun=0, Mon=1 ... Sat=6
    python_wd = date_obj.weekday()
    sunday_based_wd = str((python_wd + 1) % 7)
    
    allowed = task.allowed_days.split(',')
    return sunday_based_wd in allowed