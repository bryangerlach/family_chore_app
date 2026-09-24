from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Task(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='task_images/', blank=True, null=True)
    star_value = models.PositiveIntegerField(default=1, help_text="Stars earned when approved")
    
    # Stores allowed weekdays as comma-separated integers (0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat)
    # Blank means available every day.
    allowed_days = models.CharField(max_length=20, default="0,1,2,3,4,5,6", help_text="Comma-separated days: 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat")

    def __str__(self):
        return f"{self.title} ({self.star_value} ⭐)"

class Profile(models.Model):
    USER_TYPE_CHOICES = (
        ('child', 'Child'),
        ('parent', 'Parent'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=50)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='child')
    pin = models.CharField(max_length=4, blank=True, null=True, help_text="4-digit PIN for kids")
    emoji = models.CharField(max_length=10, default="👦", help_text="Profile icon emoji")

    def get_stars_balance(self):
        # Earned stars from approved tasks
        earned = DailyTaskStatus.objects.filter(child=self, status='approved').aggregate(
            total=models.Sum('task__star_value')
        )['total'] or 0
        
        # Spent stars on approved redemptions (or pending/approved depending on your preference)
        spent = RedemptionLog.objects.filter(child=self, status='approved').aggregate(
            total=models.Sum('reward__star_cost')
        )['total'] or 0
        
        return earned - spent

    def __str__(self):
        return f"{self.name} ({self.user_type})"

class Reward(models.Model):
    title = models.CharField(max_length=100)
    star_cost = models.PositiveIntegerField(default=1, help_text="Stars required to redeem")
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.title} ({self.star_cost} ⭐)"

class RedemptionLog(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
    )
    child = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='redemptions')
    reward = models.ForeignKey(Reward, on_delete=models.CASCADE)
    redeemed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending') # <-- Updated field

    def __str__(self):
        return f"{self.child.name} requested {self.reward.title} ({self.status})"

class DailyTaskStatus(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('waiting', 'Waiting for Approval'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
    )
    child = models.ForeignKey(Profile, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"{self.child.name} - {self.task.title} ({self.status})"