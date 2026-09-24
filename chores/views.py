from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import Profile, Task, DailyTaskStatus, Reward, RedemptionLog
from datetime import datetime

def profile_list(request):
    profiles = Profile.objects.all()
    return render(request, 'chores/profile_list.html', {'profiles': profiles})

def child_dashboard(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id, user_type='child')
    today = timezone.localdate()
    
    python_wd = today.weekday()
    sunday_based_wd = str((python_wd + 1) % 7)
    
    all_tasks = Task.objects.all()
    active_tasks = []
    for task in all_tasks:
        allowed = task.allowed_days.split(',') if task.allowed_days else ["0","1","2","3","4","5","6"]
        if sunday_based_wd in allowed:
            active_tasks.append(task)
            DailyTaskStatus.objects.get_or_create(
                child=profile,
                task=task,
                date=today,
                defaults={'status': 'pending'}
            )
        
    task_statuses = DailyTaskStatus.objects.filter(child=profile, date=today, task__in=active_tasks)
    
    # Filter out one-time rewards the child has already redeemed or requested
    claimed_reward_ids = RedemptionLog.objects.filter(child=profile).values_list('reward_id', flat=True)
    available_rewards = []
    for reward in Reward.objects.all():
        if reward.is_one_time and reward.id in claimed_reward_ids:
            continue # Skip this reward since it's already claimed/requested
        available_rewards.append(reward)
    
    return render(request, 'chores/child_dashboard.html', {
        'profile': profile,
        'task_statuses': task_statuses,
        'rewards': available_rewards, # <-- Pass filtered list
        'stars_balance': profile.get_stars_balance(),
    })

def add_reward(request):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    if request.method == 'POST':
        title = request.POST.get('title')
        star_cost = request.POST.get('star_cost', 1)
        description = request.POST.get('description', '')
        is_one_time = request.POST.get('is_one_time') == 'on' # <-- Capture checkbox
        
        if title:
            Reward.objects.create(
                title=title, 
                star_cost=star_cost, 
                description=description,
                is_one_time=is_one_time
            )
    return redirect('parent_dashboard')

def edit_reward(request, reward_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    reward = get_object_or_404(Reward, id=reward_id)
    
    if request.method == 'POST':
        reward.title = request.POST.get('title', reward.title)
        reward.star_cost = request.POST.get('star_cost', reward.star_cost)
        reward.description = request.POST.get('description', reward.description)
        reward.is_one_time = request.POST.get('is_one_time') == 'on'
        reward.save()
        
        return redirect('parent_dashboard')
        
    return render(request, 'chores/edit_reward.html', {'reward': reward})

def redeem_reward(request, profile_id, reward_id):
    child = get_object_or_404(Profile, id=profile_id, user_type='child')
    reward = get_object_or_404(Reward, id=reward_id)
    
    # Check if child has enough stars
    if child.get_stars_balance() >= reward.star_cost:
        RedemptionLog.objects.create(child=child, reward=reward)
        
    return redirect('child_dashboard', profile_id=child.id)

def request_approval(request, task_status_id):
    task_status = get_object_or_404(DailyTaskStatus, id=task_status_id)
    if task_status.status == 'pending':
        task_status.status = 'waiting'
        task_status.save()
    return redirect('child_dashboard', profile_id=task_status.child.id)

def parent_login(request):
    error = None
    if request.method == 'POST':
        entered_pin = request.POST.get('pin')
        parent_profile = Profile.objects.filter(user_type='parent', pin=entered_pin).first()
        
        if parent_profile:
            request.session['is_parent_authenticated'] = True
            return redirect('parent_dashboard')
        else:
            error = "Incorrect PIN. Try again."
            
    return render(request, 'chores/parent_login.html', {'error': error})

def parent_dashboard(request):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    today = timezone.localdate()
    
    # Determine today's day index (Sun=0 ... Sat=6)
    python_wd = today.weekday()
    sunday_based_wd = str((python_wd + 1) % 7)
    
    children = Profile.objects.filter(user_type='child')
    tasks = Task.objects.all()
    rewards = Reward.objects.all()
    
    # Filter tasks active on today's day of the week for progress reporting
    active_today_tasks = []
    for task in tasks:
        allowed = task.allowed_days.split(',') if task.allowed_days else ["0","1","2","3","4","5","6"]
        if sunday_based_wd in allowed:
            active_today_tasks.append(task)
            
    waiting_rewards = RedemptionLog.objects.filter(status='pending')
    
    for child in children:
        for task in active_today_tasks:
            DailyTaskStatus.objects.get_or_create(
                child=child,
                task=task,
                date=today,
                defaults={'status': 'pending'}
            )

    waiting_tasks = DailyTaskStatus.objects.filter(status='waiting', date=today, task__in=active_today_tasks)
    
    children_progress = []
    for child in children:
        # Only fetch statuses for tasks scheduled for today
        statuses = DailyTaskStatus.objects.filter(child=child, date=today, task__in=active_today_tasks)
        total_tasks = statuses.count()
        approved_tasks = statuses.filter(status='approved').count()
        percent = int((approved_tasks / total_tasks * 100)) if total_tasks > 0 else 0
        
        children_progress.append({
            'child': child,
            'statuses': statuses,
            'total_tasks': total_tasks,
            'approved_tasks': approved_tasks,
            'percent': percent
        })

    days_since_sunday = (today.weekday() + 1) % 7
    start_sunday = today - timedelta(days=days_since_sunday)
    dates_list = [start_sunday + timedelta(days=i) for i in range(7)]
    
    weekly_data = []
    for child in children:
        day_statuses = {}
        for d in dates_list:
            st_map = {st.task_id: st.status for st in DailyTaskStatus.objects.filter(child=child, date=d)}
            day_statuses[d] = st_map
        weekly_data.append({
            'child': child,
            'day_statuses': day_statuses
        })

    profiles = Profile.objects.all()
    
    return render(request, 'chores/parent_dashboard.html', {
        'waiting_tasks': waiting_tasks,
        'waiting_rewards': waiting_rewards,
        'children_progress': children_progress,
        'weekly_data': weekly_data,
        'dates_list': dates_list,
        'tasks': tasks,
        'rewards': rewards,
        'profiles': profiles,
    })

def child_star_history(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id, user_type='child')
    
    # Approved task earnings
    earned_tasks = DailyTaskStatus.objects.filter(child=profile, status='approved').order_by('-date')
    
    # Approved reward redemptions
    spent_rewards = RedemptionLog.objects.filter(child=profile, status='approved').order_by('-redeemed_at')
    
    return render(request, 'chores/star_history.html', {
        'profile': profile,
        'earned_tasks': earned_tasks,
        'spent_rewards': spent_rewards,
        'stars_balance': profile.get_stars_balance(),
    })

def delete_task(request, task_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
    task = get_object_or_404(Task, id=task_id)
    task.delete()
    return redirect('parent_dashboard')

def delete_reward(request, reward_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
    reward = get_object_or_404(Reward, id=reward_id)
    reward.delete()
    return redirect('parent_dashboard')

def approve_reward(request, redemption_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
    redemption = get_object_or_404(RedemptionLog, id=redemption_id)
    redemption.status = 'approved'
    redemption.save()
    return redirect('parent_dashboard')

def deny_reward(request, redemption_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
    redemption = get_object_or_404(RedemptionLog, id=redemption_id)
    redemption.status = 'denied'
    redemption.save()
    return redirect('parent_dashboard')

def approve_task(request, task_status_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    task_status = get_object_or_404(DailyTaskStatus, id=task_status_id)
    if task_status.status == 'waiting':
        task_status.status = 'approved'
        task_status.save()
    return redirect('parent_dashboard')

def deny_task(request, task_status_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
    task_status = get_object_or_404(DailyTaskStatus, id=task_status_id)
    task_status.status = 'denied'
    task_status.save()
    return redirect('parent_dashboard')

def reset_task(request, task_status_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    task_status = get_object_or_404(DailyTaskStatus, id=task_status_id)
    task_status.status = 'pending'
    task_status.save()
    return redirect('parent_dashboard')

def add_profile(request):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    if request.method == 'POST':
        name = request.POST.get('name')
        user_type = request.POST.get('user_type', 'child')
        pin = request.POST.get('pin', '')
        emoji = request.POST.get('emoji', '👦') # <-- Added this line
        if name:
            Profile.objects.create(name=name, user_type=user_type, pin=pin, emoji=emoji) # <-- Added emoji here
    return redirect('parent_dashboard')

def add_task(request):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        star_value = request.POST.get('star_value', 1)
        image = request.FILES.get('image')
        
        # Get selected checkboxes from form
        days_list = request.POST.getlist('allowed_days') # Returns list of strings like ['1', '2', '3', '4', '5']
        allowed_days = ",".join(days_list) if days_list else "0,1,2,3,4,5,6"
        
        if title:
            Task.objects.create(
                title=title, 
                description=description, 
                star_value=star_value, 
                image=image,
                allowed_days=allowed_days
            )
    return redirect('parent_dashboard')

def edit_task(request, task_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    task = get_object_or_404(Task, id=task_id)
    
    if request.method == 'POST':
        task.title = request.POST.get('title', task.title)
        task.description = request.POST.get('description', task.description)
        task.star_value = request.POST.get('star_value', task.star_value)
        
        # Handle reference image update if a new one is provided
        if 'image' in request.FILES:
            task.image = request.FILES['image']
            
        # Handle days of week checkboxes
        days_list = request.POST.getlist('allowed_days')
        if days_list:
            task.allowed_days = ",".join(days_list)
            
        task.save()
        return redirect('parent_dashboard')
        
    return render(request, 'chores/edit_task.html', {'task': task})

def parent_logout(request):
    request.session['is_parent_authenticated'] = False
    return redirect('profile_list')

def update_weekly_status(request, child_id, task_id, date_str):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    child = get_object_or_404(Profile, id=child_id, user_type='child')
    task = get_object_or_404(Task, id=task_id)
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    status_obj, created = DailyTaskStatus.objects.get_or_create(
        child=child,
        task=task,
        date=target_date,
        defaults={'status': 'pending'}
    )
    
    # Toggle status: if approved, set to pending; otherwise set to approved
    if status_obj.status == 'approved':
        status_obj.status = 'pending'
    else:
        status_obj.status = 'approved'
    status_obj.save()
    
    return redirect('parent_dashboard')

def update_child_emoji(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id, user_type='child')
    if request.method == 'POST':
        new_emoji = request.POST.get('emoji')
        if new_emoji:
            profile.emoji = new_emoji
            profile.save()
    return redirect('child_dashboard', profile_id=profile.id)