from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    USER_TYPE_CHOICES = (
        ('child', 'Child'),
        ('parent', 'Parent'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=50)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='child')
    pin = models.CharField(max_length=4, blank=True, null=True, help_text="4-digit PIN for kids")
    emoji = models.CharField(max_length=10, default="👦", help_text="Profile icon emoji") # <-- Added this line

    def __str__(self):
        return f"{self.name} ({self.user_type})"

class Task(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.title

class DailyTaskStatus(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('waiting', 'Waiting Approval'),
        ('approved', 'Approved / Completed'),
    )
    
    child = models.ForeignKey(Profile, on_delete=models.CASCADE, limit_choices_to={'user_type': 'child'})
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"{self.child.name} - {self.task.title} [{self.status}] ({self.date})"