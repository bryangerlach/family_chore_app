from django.urls import path
from . import views

urlpatterns = [
    path('', views.profile_list, name='profile_list'),
    path('child/<int:profile_id>/', views.child_dashboard, name='child_dashboard'),
    path('child/<int:profile_id>/update-emoji/', views.update_child_emoji, name='update_child_emoji'), # <-- Added this line
    path('task/<int:task_status_id>/request/', views.request_approval, name='request_approval'),
    
    # Parent Protected URLs
    path('parent/login/', views.parent_login, name='parent_login'),
    path('parent/', views.parent_dashboard, name='parent_dashboard'),
    path('parent/logout/', views.parent_logout, name='parent_logout'),
    path('task/<int:task_status_id>/approve/', views.approve_task, name='approve_task'),
    path('task/<int:task_status_id>/reset/', views.reset_task, name='reset_task'),
    path('parent/update-status/<int:child_id>/<int:task_id>/<str:date_str>/', views.update_weekly_status, name='update_weekly_status'),
    path('parent/add-profile/', views.add_profile, name='add_profile'),
    path('parent/add-task/', views.add_task, name='add_task'),
]