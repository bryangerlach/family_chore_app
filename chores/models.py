from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ==========================================
#  CORE PROFILES
# ==========================================

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
        # Sum all ledger entries (task earnings, coin store purchases, refunds, etc.)
        total_stars = StarLedger.objects.filter(child=self).aggregate(
            total=models.Sum('amount')
        )['total'] or 0
        return total_stars
        
    def get_coin_balance(self):
        return sum(t.amount for t in self.coin_transactions.all())

    def __str__(self):
        return f"{self.name} ({self.user_type})"


# ==========================================
#  TASKS & DAILY TRACKING
# ==========================================

class Task(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='task_images/', blank=True, null=True)
    star_value = models.PositiveIntegerField(default=1, help_text="Stars earned when approved")
    
    # Stores allowed weekdays as comma-separated integers (0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat)
    allowed_days = models.CharField(
        max_length=20, 
        default="0,1,2,3,4,5,6", 
        help_text="Comma-separated days: 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat"
    )

    def __str__(self):
        return f"{self.title} ({self.star_value} ⭐)"


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


# ==========================================
#  REWARDS & REDEMPTIONS
# ==========================================

class Reward(models.Model):
    REWARD_TYPES = [
        ('recurring', 'Recurring (Unlimited)'),
        ('one_time', 'One-Time Only (Never again once claimed)'),
        ('weekly', 'Once Per Week (Resets every Sunday)'),
    ]

    title = models.CharField(max_length=100)
    star_cost = models.IntegerField(default=0, help_text="Stars required to redeem")
    description = models.TextField(blank=True, null=True)
    reward_type = models.CharField(max_length=20, choices=REWARD_TYPES, default='recurring')
    is_one_time = models.BooleanField(default=False)  # Kept for backward compatibility

    def __str__(self):
        return f"{self.title} ({self.star_cost} ⭐)"


class RedemptionLog(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
    ]
    child = models.ForeignKey(Profile, on_delete=models.CASCADE)
    reward = models.ForeignKey(Reward, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    redeemed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.child.name} requested {self.reward.title} ({self.status})"

class StarLedger(models.Model):
    child = models.ForeignKey(Profile, on_delete=models.CASCADE)
    amount = models.IntegerField() # Positive for earned, negative for spent/redeemed
    reason = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)


# ==========================================
#  COIN ECONOMY & STORE
# ==========================================

class CoinStoreItem(models.Model):
    title = models.CharField(max_length=100, help_text="e.g., 1 Star Point")
    coin_cost = models.PositiveIntegerField(default=10)
    star_value_granted = models.PositiveIntegerField(default=0, help_text="Stars granted when bought")
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.title} ({self.coin_cost} 🪙)"


class CoinLedger(models.Model):
    child = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='coin_transactions')
    amount = models.IntegerField(help_text="Positive for earned, negative for spent")
    reason = models.CharField(max_length=200)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.child.name}: {self.amount:+d} coins ({self.reason})"


# ==========================================
#  QUIZ HUB & TRACKING
# ==========================================

class QuizQuestion(models.Model):
    QUESTION_TYPES = [
        ('math', 'Math Problem'),
        ('reading', 'Reading Comprehension'),
    ]
    
    child = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='quiz_questions', null=True, blank=True)
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='math')
    passage = models.TextField(blank=True, null=True, help_text="For reading: the story or paragraph")
    question_text = models.TextField(help_text="The question to answer")
    
    option_a = models.CharField(max_length=100)
    option_b = models.CharField(max_length=100)
    option_c = models.CharField(max_length=100, blank=True, null=True)
    option_d = models.CharField(max_length=100, blank=True, null=True)
    
    CORRECT_CHOICES = [('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')]
    correct_answer = models.CharField(max_length=1, choices=CORRECT_CHOICES)
    coin_reward = models.PositiveIntegerField(default=5, help_text="Coins earned for correct answer")

    def __str__(self):
        child_name = self.child.name if self.child else "General"
        return f"[{child_name}] [{self.get_question_type_display()}] {self.question_text[:25]}..."


class QuizAttempt(models.Model):
    child = models.ForeignKey(Profile, on_delete=models.CASCADE)
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    solved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        pass


class QuizWrongAttempt(models.Model):
    child = models.ForeignKey(Profile, on_delete=models.CASCADE)
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    option_chosen = models.CharField(max_length=1, blank=True, null=True)  # Tracks 'A', 'B', 'C', or 'D'
    timestamp = models.DateTimeField(auto_now_add=True)