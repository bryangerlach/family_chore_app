from django.contrib import admin
from .models import (
    Profile, Task, DailyTaskStatus, Reward, 
    RedemptionLog, CoinStoreItem, CoinLedger, QuizQuestion
)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'user_type', 'pin', 'get_stars_balance', 'get_coin_balance')
    search_fields = ('name',)

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'star_value', 'allowed_days')
    search_fields = ('title',)

@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ('title', 'star_cost', 'reward_type')
    list_filter = ('reward_type',)

@admin.register(RedemptionLog)
class RedemptionLogAdmin(admin.ModelAdmin):
    list_display = ('child', 'reward', 'redeemed_at', 'status')
    list_filter = ('status', 'redeemed_at')
    list_editable = ('status',) # Allows you to change pending -> approved/denied directly from the list view!

@admin.register(CoinStoreItem)
class CoinStoreItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'coin_cost', 'star_value_granted')

@admin.register(CoinLedger)
class CoinLedgerAdmin(admin.ModelAdmin):
    list_display = ('child', 'amount', 'reason', 'timestamp')
    search_fields = ('child__name', 'reason')

@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'child', 'question_type', 'coin_reward')
    list_filter = ('question_type',)