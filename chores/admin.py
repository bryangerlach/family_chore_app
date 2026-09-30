from django.contrib import admin
from .models import (
    Profile, Task, DailyTaskStatus, Reward, RedemptionLog, 
    StarLedger, CoinStoreItem, CoinLedger, QuizQuestion, 
    QuizAttempt, QuizWrongAttempt, ArcadeHighScore, 
    VirtualPet, ParentNotificationConfig
)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'user_type', 'emoji', 'get_stars_balance', 'get_coin_balance')
    list_filter = ('user_type',)
    search_fields = ('name',)

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'star_value', 'allowed_days')
    search_fields = ('title',)

@admin.register(DailyTaskStatus)
class DailyTaskStatusAdmin(admin.ModelAdmin):
    list_display = ('child', 'task', 'date', 'status')
    list_filter = ('status', 'date')
    search_fields = ('child__name', 'task__title')

@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ('title', 'star_cost', 'reward_type')
    list_filter = ('reward_type',)

@admin.register(RedemptionLog)
class RedemptionLogAdmin(admin.ModelAdmin):
    list_display = ('child', 'reward', 'status', 'redeemed_at')
    list_filter = ('status',)

@admin.register(StarLedger)
class StarLedgerAdmin(admin.ModelAdmin):
    list_display = ('child', 'amount', 'reason', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('child__name', 'reason')

@admin.register(CoinStoreItem)
class CoinStoreItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'coin_cost', 'star_value_granted')

@admin.register(CoinLedger)
class CoinLedgerAdmin(admin.ModelAdmin):
    list_display = ('child', 'amount', 'reason', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('child__name', 'reason')

@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'question_type', 'coin_reward')
    list_filter = ('question_type',)

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('child', 'question', 'solved_at')

@admin.register(QuizWrongAttempt)
class QuizWrongAttemptAdmin(admin.ModelAdmin):
    list_display = ('child', 'question', 'option_chosen', 'timestamp')

@admin.register(ArcadeHighScore)
class ArcadeHighScoreAdmin(admin.ModelAdmin):
    list_display = ('child', 'game_title', 'score', 'updated_at')
    list_filter = ('game_key',)
    search_fields = ('child__name', 'game_title')

@admin.register(VirtualPet)
class VirtualPetAdmin(admin.ModelAdmin):
    list_display = ('name', 'child', 'species', 'level', 'hunger', 'happiness')
    search_fields = ('name', 'child__name')

@admin.register(ParentNotificationConfig)
class ParentNotificationConfigAdmin(admin.ModelAdmin):
    list_display = ('parent', 'webhook_url', 'notify_chore_waiting', 'notify_reward_requested', 'notify_quiz_completed')
    search_fields = ('parent__name', 'webhook_url')