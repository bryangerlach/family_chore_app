from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import Profile, Task, DailyTaskStatus, Reward, RedemptionLog, CoinLedger, QuizQuestion, QuizAttempt, CoinStoreItem, QuizWrongAttempt, RedemptionLog
from datetime import datetime
import csv
import io
import urllib.request
from django.db import IntegrityError
import random

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
    
    # Calculate current week's start (Sunday)
    days_since_sunday = (today.weekday() + 1) % 7
    start_sunday = today - timedelta(days=days_since_sunday)
    
    available_rewards = []
    for reward in Reward.objects.all():
        if reward.reward_type == 'one_time':
            # Hide if claimed or requested ever
            already_claimed = RedemptionLog.objects.filter(child=profile, reward=reward).exists()
            if already_claimed:
                continue
        elif reward.reward_type == 'weekly':
            # Hide if claimed or requested *this week* (since Sunday)
            claimed_this_week = RedemptionLog.objects.filter(
                child=profile, 
                reward=reward, 
                redeemed_at__date__gte=start_sunday
            ).exists()
            if claimed_this_week:
                continue
                
        available_rewards.append(reward)
    
    return render(request, 'chores/child_dashboard.html', {
        'profile': profile,
        'task_statuses': task_statuses,
        'rewards': available_rewards,
        'stars_balance': profile.get_stars_balance(),
        'coins_balance': profile.get_coin_balance(),
    })

def add_reward(request):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    if request.method == 'POST':
        title = request.POST.get('title')
        star_cost = request.POST.get('star_cost', 1)
        description = request.POST.get('description', '')
        reward_type = request.POST.get('reward_type', 'recurring')
        is_one_time = (reward_type == 'one_time')
        
        if title:
            Reward.objects.create(
                title=title, 
                star_cost=star_cost, 
                description=description,
                reward_type=reward_type,
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
        reward_type = request.POST.get('reward_type', 'recurring')
        reward.reward_type = reward_type
        reward.is_one_time = (reward_type == 'one_time')
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
    python_wd = today.weekday()
    sunday_based_wd = str((python_wd + 1) % 7)
    
    children = Profile.objects.filter(user_type='child')
    tasks = Task.objects.all()
    rewards = Reward.objects.all()
    
    active_today_tasks = []
    for task in tasks:
        allowed = task.allowed_days.split(',') if task.allowed_days else ["0","1","2","3","4","5","6"]
        if sunday_based_wd in allowed:
            active_today_tasks.append(task)
            
    if children.exists():
        for child in children:
            for task in active_today_tasks:
                DailyTaskStatus.objects.get_or_create(
                    child=child,
                    task=task,
                    date=today,
                    defaults={'status': 'pending'}
                )
            
    waiting_tasks = DailyTaskStatus.objects.filter(status='waiting', date=today, task__in=active_today_tasks) if children.exists() else DailyTaskStatus.objects.none()
    waiting_rewards = RedemptionLog.objects.filter(status='pending')
    
    cutoff_time = timezone.now() - timedelta(hours=18)
    
    children_summary = []
    for child in children:
        statuses = DailyTaskStatus.objects.filter(child=child, date=today, task__in=active_today_tasks)
        total_tasks = statuses.count()
        approved_tasks = statuses.filter(status='approved').count()
        percent = int((approved_tasks / total_tasks * 100)) if total_tasks > 0 else 0
        
        solved_ids = QuizAttempt.objects.filter(child=child, solved_at__gte=cutoff_time).values_list('question_id', flat=True)
        unanswered_quizzes = QuizQuestion.objects.filter(child=child).exclude(id__in=solved_ids).count()
        
        children_summary.append({
            'child': child,
            'star_balance': child.get_stars_balance(),
            'coin_balance': child.get_coin_balance(),
            'approved_tasks': approved_tasks,
            'total_tasks': total_tasks,
            'percent': percent,
            'unanswered_quizzes': unanswered_quizzes,
            'statuses': statuses
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

    return render(request, 'chores/parent_dashboard.html', {
        'waiting_tasks': waiting_tasks,
        'waiting_rewards': waiting_rewards,
        'children_summary': children_summary,
        'weekly_data': weekly_data,
        'dates_list': dates_list,
        'tasks': tasks,
        'rewards': rewards,
        'profiles': Profile.objects.all(),
        'quiz_questions': QuizQuestion.objects.all(),
        'coin_items': CoinStoreItem.objects.all(),
    })

def management_hub(request):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    return render(request, 'chores/management_hub.html', {
        'tasks': Task.objects.all(),
        'rewards': Reward.objects.all(),
        'coin_items': CoinStoreItem.objects.all(),
        'quiz_questions': QuizQuestion.objects.all(),
        'profiles': Profile.objects.all(),
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

def delete_profile(request, profile_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
    if request.method == 'POST':
        profile = get_object_or_404(Profile, id=profile_id)
        profile.delete()
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

def quiz_hub(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id, user_type='child')
    cutoff_time = timezone.now() - timedelta(hours=18)
    
    solved_question_ids = QuizAttempt.objects.filter(
        child=profile, 
        solved_at__gte=cutoff_time
    ).values_list('question_id', flat=True)
    
    available_questions = QuizQuestion.objects.filter(child=profile).exclude(id__in=solved_question_ids)
    
    questions_data = []
    for q in available_questions:
        wrong_attempts = QuizWrongAttempt.objects.filter(
            child=profile, 
            question=q, 
            timestamp__gte=cutoff_time
        )
        wrong_count = wrong_attempts.count()
        q.wrong_options = list(wrong_attempts.values_list('option_chosen', flat=True))
        q.current_reward = max(1, q.coin_reward - wrong_count)
        questions_data.append(q)
    
    # Shuffle the questions into a random order every time the page loads
    random.shuffle(questions_data)
    
    feedback = request.GET.get('feedback')
    
    return render(request, 'chores/quiz_hub.html', {
        'profile': profile,
        'questions': questions_data,
        'coin_balance': profile.get_coin_balance(),
        'feedback': feedback,
    })

def submit_quiz(request, profile_id, question_id):
    profile = get_object_or_404(Profile, id=profile_id, user_type='child')
    question = get_object_or_404(QuizQuestion, id=question_id)
    cutoff_time = timezone.now() - timedelta(hours=18)
    
    if request.method == 'POST':
        selected_answer = request.POST.get('answer')
        
        already_solved = QuizAttempt.objects.filter(
            child=profile, 
            question=question, 
            solved_at__gte=cutoff_time
        ).exists()
        
        if already_solved:
            return redirect(f"/child/{profile.id}/quiz/?feedback=already_solved")
            
        if selected_answer == question.correct_answer:
            wrong_count = QuizWrongAttempt.objects.filter(
                child=profile, 
                question=question, 
                timestamp__gte=cutoff_time
            ).count()
            earned_coins = max(1, question.coin_reward - wrong_count)
            
            try:
                QuizAttempt.objects.create(child=profile, question=question)
                CoinLedger.objects.create(
                    child=profile,
                    amount=earned_coins,
                    reason=f"Correct Quiz Answer ({earned_coins}🪙): {question.question_text[:15]}..."
                )
            except IntegrityError:
                return redirect(f"/child/{profile.id}/quiz/?feedback=already_solved")
                
            return redirect(f"/child/{profile.id}/quiz/?feedback=correct")
        else:
            # Save which option was chosen wrong
            QuizWrongAttempt.objects.create(
                child=profile, 
                question=question, 
                option_chosen=selected_answer
            )
            return redirect(f"/child/{profile.id}/quiz/?feedback=incorrect")
                
    return redirect('quiz_hub', profile_id=profile.id)

def coin_store(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id, user_type='child')
    items = CoinStoreItem.objects.all()
    feedback = request.GET.get('feedback')
    
    return render(request, 'chores/coin_store.html', {
        'profile': profile,
        'items': items,
        'coin_balance': profile.get_coin_balance(),
        'feedback': feedback,
    })

def child_coin_history(request, profile_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    child = get_object_or_404(Profile, id=profile_id, user_type='child')
    ledgers = CoinLedger.objects.filter(child=child).order_by('-timestamp')
    
    return render(request, 'chores/coin_history.html', {
        'child': child,
        'ledgers': ledgers,
    })

def buy_coin_item(request, profile_id, item_id):
    profile = get_object_or_404(Profile, id=profile_id, user_type='child')
    item = get_object_or_404(CoinStoreItem, id=item_id)
    
    if profile.get_coin_balance() >= item.coin_cost:
        # Deduct coins
        CoinLedger.objects.create(
            child=profile,
            amount=-item.coin_cost,
            reason=f"Purchased: {item.title}"
        )
        
        # If item grants stars, record an approved task earning so balance increases
        if item.star_value_granted > 0:
            dummy_task, _ = Task.objects.get_or_create(
                title=f"Coin Store Purchase: {item.title}",
                defaults={'star_value': item.star_value_granted}
            )
            DailyTaskStatus.objects.create(
                child=profile,
                task=dummy_task,
                date=timezone.localdate(),
                status='approved'
            )
            
        return redirect(f"/child/{profile.id}/coins/?feedback=success")
    else:
        return redirect(f"/child/{profile.id}/coins/?feedback=not_enough")

def add_quiz_question(request):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
    if request.method == 'POST':
        child_id = request.POST.get('child_id')
        child = get_object_or_404(Profile, id=child_id, user_type='child')
        
        QuizQuestion.objects.create(
            child=child,
            question_type=request.POST.get('question_type'),
            passage=request.POST.get('passage'),
            question_text=request.POST.get('question_text'),
            option_a=request.POST.get('option_a'),
            option_b=request.POST.get('option_b'),
            option_c=request.POST.get('option_c'),
            option_d=request.POST.get('option_d'),
            correct_answer=request.POST.get('correct_answer'),
            coin_reward=request.POST.get('coin_reward', 5)
        )
    return redirect('parent_dashboard')

def delete_quiz_question(request, q_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
    get_object_or_404(QuizQuestion, id=q_id).delete()
    return redirect('parent_dashboard')

def add_coin_store_item(request):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
    if request.method == 'POST':
        CoinStoreItem.objects.create(
            title=request.POST.get('title'),
            coin_cost=request.POST.get('coin_cost', 10),
            star_value_granted=request.POST.get('star_value_granted', 0),
            description=request.POST.get('description', '')
        )
    return redirect('parent_dashboard')

def delete_coin_store_item(request, item_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
    get_object_or_404(CoinStoreItem, id=item_id).delete()
    return redirect('parent_dashboard')

def import_quizzes_from_text(request):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    if request.method == 'POST':
        child_id = request.POST.get('child_id')
        child = get_object_or_404(Profile, id=child_id, user_type='child')
        raw_text = request.POST.get('raw_text', '')
        
        # WIPE old questions for this child before importing new ones
        QuizQuestion.objects.filter(child=child).delete()
        
        # Use io.StringIO and csv.reader to safely parse commas and quotes
        io_string = io.StringIO(raw_text.strip())
        reader = csv.reader(io_string)
        
        for row in reader:
            # Skip empty lines or comment lines starting with '#'
            if not row or (len(row) == 1 and row[0].strip().startswith('#')):
                continue
                
            # Clean up whitespace for each column value
            parts = [p.strip() for p in row]
            
            if len(parts) >= 8:
                QuizQuestion.objects.create(
                    child=child,
                    question_type=parts[0].lower(),
                    question_text=parts[1],
                    option_a=parts[2],
                    option_b=parts[3],
                    option_c=parts[4] if parts[4] else None,
                    option_d=parts[5] if parts[5] else None,
                    correct_answer=parts[6].upper(),
                    coin_reward=int(parts[7]) if parts[7].isdigit() else 5,
                    passage=parts[8] if len(parts) > 8 and parts[8] else None
                )
    return redirect('parent_dashboard')

def import_quizzes_from_sheet(request):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    if request.method == 'POST':
        child_id = request.POST.get('child_id')
        child = get_object_or_404(Profile, id=child_id, user_type='child')
        sheet_url = request.POST.get('sheet_url', '')
        
        try:
            response = urllib.request.urlopen(sheet_url)
            csv_data = response.read().decode('utf-8')
            io_string = io.StringIO(csv_data)
            reader = csv.reader(io_string)
            
            header = next(reader, None)
            
            # WIPE old questions for this child before importing new ones
            QuizQuestion.objects.filter(child=child).delete()
            
            for row in reader:
                if len(row) >= 8:
                    QuizQuestion.objects.create(
                        child=child,
                        question_type=row[0].strip().lower(),
                        question_text=row[1].strip(),
                        option_a=row[2].strip(),
                        option_b=row[3].strip(),
                        option_c=row[4].strip() if row[4].strip() else None,
                        option_d=row[5].strip() if row[5].strip() else None,
                        correct_answer=row[6].strip().upper(),
                        coin_reward=int(row[7].strip()) if row[7].strip().isdigit() else 5,
                        passage=row[8].strip() if len(row) > 8 and row[8].strip() else None
                    )
        except Exception as e:
            print(f"Error importing sheet: {e}")
            
    return redirect('parent_dashboard')