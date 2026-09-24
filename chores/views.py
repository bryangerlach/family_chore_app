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
    
    tasks = Task.objects.all()
    for task in tasks:
        DailyTaskStatus.objects.get_or_create(
            child=profile,
            task=task,
            date=today,
            defaults={'status': 'pending'}
        )
        
    task_statuses = DailyTaskStatus.objects.filter(child=profile, date=today)
    rewards = Reward.objects.all() # <-- Pass available rewards to child view
    
    return render(request, 'chores/child_dashboard.html', {
        'profile': profile,
        'task_statuses': task_statuses,
        'rewards': rewards, # <-- Pass rewards here
        'stars_balance': profile.get_stars_balance(), # <-- Pass star balance
    })

def add_reward(request):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    if request.method == 'POST':
        title = request.POST.get('title')
        star_cost = request.POST.get('star_cost', 1)
        description = request.POST.get('description', '')
        if title:
            Reward.objects.create(title=title, star_cost=star_cost, description=description)
    return redirect('parent_dashboard')

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
    
    children = Profile.objects.filter(user_type='child')
    tasks = Task.objects.all()
    rewards = Reward.objects.all()
    
    # Get pending reward requests
    waiting_rewards = RedemptionLog.objects.filter(status='pending') # <-- Added
    
    for child in children:
        for task in tasks:
            DailyTaskStatus.objects.get_or_create(
                child=child,
                task=task,
                date=today,
                defaults={'status': 'pending'}
            )

    waiting_tasks = DailyTaskStatus.objects.filter(status='waiting', date=today)
    
    children_progress = []
    for child in children:
        statuses = DailyTaskStatus.objects.filter(child=child, date=today)
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
        'waiting_rewards': waiting_rewards, # <-- Pass waiting rewards
        'children_progress': children_progress,
        'weekly_data': weekly_data,
        'dates_list': dates_list,
        'tasks': tasks,
        'rewards': rewards,
        'profiles': profiles
    })

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
        star_value = request.POST.get('star_value', 1) # <-- Added
        image = request.FILES.get('image')
        if title:
            Task.objects.create(title=title, description=description, star_value=star_value, image=image)
    return redirect('parent_dashboard')

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