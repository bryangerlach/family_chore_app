from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    # General / Profile Selection
    path('', views.profile_list, name='profile_list'),

    # --- Child Gamification Portals ---
    path('child/<int:profile_id>/', views.child_dashboard, name='child_dashboard'),
    path('child/<int:profile_id>/history/', views.child_star_history, name='child_star_history'),
    path('child/<int:profile_id>/quiz/', views.quiz_hub, name='quiz_hub'),
    path('child/<int:profile_id>/quiz/<int:question_id>/submit/', views.submit_quiz, name='submit_quiz'),
    path('child/<int:profile_id>/coins/', views.coin_store, name='coin_store'),
    path('child/<int:profile_id>/coins/buy/<int:item_id>/', views.buy_coin_item, name='buy_coin_item'),
    path('child/<int:profile_id>/update-emoji/', views.update_child_emoji, name='update_child_emoji'),
    path('child/<int:profile_id>/redeem/<int:reward_id>/', views.redeem_reward, name='redeem_reward'),
    path('task/<int:task_status_id>/request/', views.request_approval, name='request_approval'),

    # --- Parent Authentication & Command Center ---
    path('parent/login/', views.parent_login, name='parent_login'),
    path('parent/', views.parent_dashboard, name='parent_dashboard'),
    path('parent/logout/', views.parent_logout, name='parent_logout'),
    path('parent/management/', views.management_hub, name='management_hub'),
    path('parent/child/<int:profile_id>/coin-history/', views.child_coin_history, name='child_coin_history'),

    # --- Parent Management Actions ---
    # Task approvals & scheduling
    path('task/<int:task_status_id>/approve/', views.approve_task, name='approve_task'),
    path('task/<int:task_status_id>/deny/', views.deny_task, name='deny_task'),
    path('task/<int:task_status_id>/reset/', views.reset_task, name='reset_task'),
    path('parent/update-status/<int:child_id>/<int:task_id>/<str:date_str>/', views.update_weekly_status, name='update_weekly_status'),
    path('child/<int:child_id>/adjust-stars/', views.adjust_child_stars, name='adjust_child_stars'),
    path('child/<int:child_id>/adjust-coins/', views.adjust_child_coins, name='adjust_child_coins'),
    path('ledger/star/<int:ledger_id>/reverse/', views.reverse_star_ledger, name='reverse_star_ledger'),
    path('ledger/coin/<int:ledger_id>/reverse/', views.reverse_coin_ledger, name='reverse_coin_ledger'),
    
    # Profiles
    path('parent/add-profile/', views.add_profile, name='add_profile'),
    path('profile/delete/<int:profile_id>/', views.delete_profile, name='delete_profile'),

    # Tasks Management
    path('parent/add-task/', views.add_task, name='add_task'),
    path('parent/edit-task/<int:task_id>/', views.edit_task, name='edit_task'),
    path('parent/delete-task/<int:task_id>/', views.delete_task, name='delete_task'),

    # Rewards Management & Approvals
    path('parent/add-reward/', views.add_reward, name='add_reward'),
    path('parent/edit-reward/<int:reward_id>/', views.edit_reward, name='edit_reward'),
    path('parent/delete-reward/<int:reward_id>/', views.delete_reward, name='delete_reward'),
    path('parent/approve-reward/<int:redemption_id>/', views.approve_reward, name='approve_reward'),
    path('parent/deny-reward/<int:redemption_id>/', views.deny_reward, name='deny_reward'),

    # Quizzes Management & Imports
    path('parent/add-quiz/', views.add_quiz_question, name='add_quiz_question'),
    path('parent/delete-quiz/<int:q_id>/', views.delete_quiz_question, name='delete_quiz_question'),
    path('parent/import-text-quizzes/', views.import_quizzes_from_text, name='import_quizzes_from_text'),
    path('parent/import-sheet-quizzes/', views.import_quizzes_from_sheet, name='import_quizzes_from_sheet'),

    # Coin Store Items Management
    path('parent/add-coin-item/', views.add_coin_store_item, name='add_coin_store_item'),
    path('parent/delete-coin-item/<int:item_id>/', views.delete_coin_store_item, name='delete_coin_store_item'),

    path('child/<int:profile_id>/arcade/', views.arcade_hub, name='arcade_hub'),
    path('child/<int:profile_id>/arcade/star-dash/', views.arcade_star_dash, name='arcade_star_dash'),
    path('child/<int:profile_id>/arcade/star-catcher/', views.arcade_star_catcher, name='arcade_star_catcher'),
    path('child/<int:profile_id>/arcade/bonus/', views.arcade_bonus, name='claim_arcade_bonus'),
    path('child/<int:profile_id>/arcade/balloon-pop/', views.arcade_balloon_pop, name='arcade_balloon_pop'),
    path('child/<int:profile_id>/arcade/math-monster/', views.arcade_math_monster, name='arcade_math_monster'),
    path('child/<int:profile_id>/arcade/memory-match/', views.arcade_memory_match, name='arcade_memory_match'),
    path('child/<int:profile_id>/arcade/submit-score/', views.submit_arcade_score, name='submit_arcade_score'),
    path('child/<int:profile_id>/arcade/scores/', views.arcade_high_scores_view, name='arcade_high_scores'),
    path('parent/arcade/leaderboard/', views.parent_arcade_leaderboard, name='parent_arcade_leaderboard'),
    path('child/<int:profile_id>/pet/', views.pet_room_view, name='pet_room'),
    path('child/<int:profile_id>/pet/action/feed/', views.pet_action_feed, name='pet_action_feed'),
    path('child/<int:profile_id>/pet/action/clean/', views.pet_action_clean, name='pet_action_clean'),
    path('child/<int:profile_id>/arcade/number-runner/', views.arcade_number_runner, name='arcade_number_runner'),
    path('child/<int:profile_id>/arcade/star-fireworks/', views.arcade_fireworks, name='arcade_star_fireworks'),
    path('child/<int:profile_id>/arcade/number-jump/', views.arcade_number_jump, name='arcade_number_jump'),
    path('parent/notifications/update/', views.update_notifications, name='update_notifications'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)