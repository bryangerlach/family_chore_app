from datetime import timedelta, datetime
import csv
import io
import urllib.request
import random
import json
from collections import defaultdict
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import (
    Profile, Task, DailyTaskStatus, Reward, RedemptionLog, 
    CoinLedger, QuizQuestion, QuizAttempt, CoinStoreItem, 
    QuizWrongAttempt, StarLedger, ArcadeHighScore, VirtualPet, ParentNotificationConfig
)
from .utils import send_notification


# ==========================================
# CORE & PUBLIC VIEWS
# ==========================================

def profile_list(request):
    profiles = Profile.objects.all()
    return render(request, 'chores/profile_list.html', {'profiles': profiles})


# ==========================================
# CHILD PORTALS & GAMIFICATION
# ==========================================

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
            already_claimed = RedemptionLog.objects.filter(child=profile, reward=reward).exists()
            if already_claimed:
                continue
        elif reward.reward_type == 'weekly':
            claimed_this_week = RedemptionLog.objects.filter(
                child=profile, 
                reward=reward, 
                redeemed_at__date__gte=start_sunday
            ).exists()
            if claimed_this_week:
                continue
                
        available_rewards.append(reward)

    solved_question_ids = QuizAttempt.objects.filter(child=profile).values_list('question_id', flat=True)
    available_quiz_count = QuizQuestion.objects.filter(child=profile).exclude(id__in=solved_question_ids).count()
    
    return render(request, 'chores/child_dashboard.html', {
        'profile': profile,
        'task_statuses': task_statuses,
        'rewards': available_rewards,
        'stars_balance': profile.get_stars_balance(),
        'coins_balance': profile.get_coin_balance(),
        'available_quiz_count': available_quiz_count,
    })


def update_child_emoji(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id, user_type='child')
    if request.method == 'POST':
        new_emoji = request.POST.get('emoji')
        if new_emoji:
            profile.emoji = new_emoji
            profile.save()
    return redirect('child_dashboard', profile_id=profile.id)


def request_approval(request, task_status_id):
    task_status = get_object_or_404(DailyTaskStatus, id=task_status_id)
    if task_status.status == 'pending':
        task_status.status = 'waiting'
        task_status.save()
        
        send_notification(
            title="Chore Needs Approval! 🧹",
            message=f"{task_status.child.name} completed '{task_status.task.title}' and is waiting for review.",
            event_type="chore_waiting"
        )
        
    return redirect('child_dashboard', profile_id=task_status.child.id)


def redeem_reward(request, profile_id, reward_id):
    child = get_object_or_404(Profile, id=profile_id, user_type='child')
    reward = get_object_or_404(Reward, id=reward_id)
    
    if child.get_stars_balance() >= reward.star_cost:
        RedemptionLog.objects.create(child=child, reward=reward, status='pending')
        
        StarLedger.objects.create(
            child=child,
            amount=-reward.star_cost,
            reason=f"Requested reward: {reward.title}"
        )
        
        send_notification(
            title="Reward Requested! 🎁",
            message=f"{child.name} requested to redeem '{reward.title}' for {reward.star_cost} stars!",
            event_type="reward_requested"
        )
        
    return redirect('child_dashboard', profile_id=child.id)

def reverse_star_ledger(request, ledger_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    entry = get_object_or_404(StarLedger, id=ledger_id)
    
    StarLedger.objects.create(
        child=entry.child,
        amount=-entry.amount,
        reason=f"Reversal of star entry #{entry.id}: {entry.reason}"
    )
    
    return redirect('child_star_history', profile_id=entry.child.id)


def reverse_coin_ledger(request, ledger_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    entry = get_object_or_404(CoinLedger, id=ledger_id)
    
    CoinLedger.objects.create(
        child=entry.child,
        amount=-entry.amount,
        reason=f"Reversal of coin entry #{entry.id}: {entry.reason}"
    )
    
    return redirect('child_coin_history', profile_id=entry.child.id)

def adjust_child_stars(request, child_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    child = get_object_or_404(Profile, id=child_id, user_type='child')
    
    if request.method == 'POST':
        try:
            amount = int(request.POST.get('amount', 0))
            reason = request.POST.get('reason', 'Parent adjustment').strip()
            
            if amount != 0 and reason:
                StarLedger.objects.create(
                    child=child,
                    amount=amount,
                    reason=f"Manual Adjustment: {reason}"
                )
        except ValueError:
            pass
            
    return redirect('parent_dashboard')

def adjust_child_coins(request, child_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    child = get_object_or_404(Profile, id=child_id, user_type='child')
    
    if request.method == 'POST':
        try:
            amount = int(request.POST.get('amount', 0))
            reason = request.POST.get('reason', 'Parent adjustment').strip()
            
            if amount != 0 and reason:
                CoinLedger.objects.create(
                    child=child,
                    amount=amount,
                    reason=f"Manual Adjustment: {reason}"
                )
        except ValueError:
            pass
            
    return redirect('parent_dashboard')

def quiz_hub(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id, user_type='child')
    
    solved_question_ids = QuizAttempt.objects.filter(
        child=profile
    ).values_list('question_id', flat=True)
    
    available_questions = QuizQuestion.objects.filter(child=profile).exclude(id__in=solved_question_ids)
    
    questions_data = []
    for q in available_questions:
        wrong_attempts = QuizWrongAttempt.objects.filter(
            child=profile, 
            question=q
        )
        wrong_count = wrong_attempts.count()
        q.wrong_options = list(wrong_attempts.values_list('option_chosen', flat=True))
        q.current_reward = max(1, q.coin_reward - wrong_count)
        questions_data.append(q)
    
    # Shuffle available questions normally
    random.shuffle(questions_data)
    
    # If an answer was just marked incorrect, pin that specific question to the top!
    focus_id = request.GET.get('focus')
    if focus_id:
        try:
            focus_id = int(focus_id)
            for i, q in enumerate(questions_data):
                if q.id == focus_id:
                    focused_q = questions_data.pop(i)
                    questions_data.insert(0, focused_q)
                    break
        except ValueError:
            pass

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
    
    if request.method == 'POST':
        selected_answer = request.POST.get('answer')
        
        already_solved = QuizAttempt.objects.filter(
            child=profile, 
            question=question
        ).exists()
        
        if already_solved:
            return redirect(f"/child/{profile.id}/quiz/?feedback=already_solved")
            
        if selected_answer == question.correct_answer:
            wrong_count = QuizWrongAttempt.objects.filter(
                child=profile, 
                question=question
            ).count()
            earned_coins = max(1, question.coin_reward - wrong_count)
            
            try:
                QuizAttempt.objects.create(child=profile, question=question)
                CoinLedger.objects.create(
                    child=profile,
                    amount=earned_coins,
                    reason=f"Correct Quiz Answer ({earned_coins}🪙): {question.question_text[:15]}..."
                )
                send_notification(
                    title="Quiz Completed! 🧠",
                    message=f"{profile.name} answered a quiz question correctly and earned {earned_coins} coins!",
                    event_type="quiz_completed"
                )
            except IntegrityError:
                return redirect(f"/child/{profile.id}/quiz/?feedback=already_solved")
                
            return redirect(f"/child/{profile.id}/quiz/?feedback=correct")
        else:
            QuizWrongAttempt.objects.create(
                child=profile, 
                question=question, 
                option_chosen=selected_answer
            )
            return redirect(f"/child/{profile.id}/quiz/?feedback=incorrect&focus={question.id}")
            
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
        
        # If item grants stars, log directly to StarLedger
        if item.star_value_granted > 0:
            StarLedger.objects.create(
                child=profile,
                amount=item.star_value_granted,
                reason=f"Purchased: {item.title}"
            )
            
        return redirect(f"/child/{profile.id}/coins/?feedback=success")
    else:
        return redirect(f"/child/{profile.id}/coins/?feedback=not_enough")


# ==========================================
# PARENT AUTHENTICATION & COMMAND HUB
# ==========================================

def parent_login(request):
    error = None
    if request.method == 'POST':
        entered_pin = request.POST.get('pin')
        parent_profile = Profile.objects.filter(user_type='parent', pin=entered_pin).first()
        
        if parent_profile:
            request.session['is_parent_authenticated'] = True
            request.session['parent_profile_id'] = parent_profile.id
            return redirect('parent_dashboard')
        else:
            error = "Incorrect PIN. Try again."
            
    return render(request, 'chores/parent_login.html', {'error': error})


def parent_logout(request):
    request.session['is_parent_authenticated'] = False
    return redirect('profile_list')


def parent_dashboard(request):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')

    parent_profile_id = request.session.get('parent_profile_id')
    if not parent_profile_id:
        parent_profile = Profile.objects.filter(user_type='parent').first()
        if parent_profile:
            parent_profile_id = parent_profile.id
            request.session['parent_profile_id'] = parent_profile_id

    print("profile")
    print(parent_profile_id)
        
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
        
    children_summary = []
    for child in children:
        statuses = DailyTaskStatus.objects.filter(child=child, date=today, task__in=active_today_tasks)
        total_tasks = statuses.count()
        approved_tasks = statuses.filter(status='approved').count()
        percent = int((approved_tasks / total_tasks * 100)) if total_tasks > 0 else 0
        
        solved_ids = QuizAttempt.objects.filter(child=child).values_list('question_id', flat=True)
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
        'parent_profile_id': parent_profile_id
    })


def management_hub(request):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')

    parents = Profile.objects.filter(user_type='parent')
        
    return render(request, 'chores/management_hub.html', {
        'tasks': Task.objects.all(),
        'rewards': Reward.objects.all(),
        'coin_items': CoinStoreItem.objects.all(),
        'quiz_questions': QuizQuestion.objects.all(),
        'profiles': Profile.objects.all(),
        'parents': parents,
    })


def child_star_history(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id, user_type='child')
    ledgers = StarLedger.objects.filter(child=profile).order_by('-timestamp')
    
    is_parent = request.session.get('is_parent_authenticated', False)
    
    if is_parent:
        back_url = reverse('parent_dashboard')
    else:
        back_url = reverse('child_dashboard', args=[profile.id])
    
    return render(request, 'chores/star_history.html', {
        'profile': profile,
        'ledgers': ledgers,
        'stars_balance': profile.get_stars_balance(),
        'back_url': back_url,
        'is_parent': is_parent,
    })


def child_coin_history(request, profile_id):   
    child = get_object_or_404(Profile, id=profile_id, user_type='child')
    ledgers = CoinLedger.objects.filter(child=child).order_by('-timestamp')
    
    is_parent = request.session.get('is_parent_authenticated', False)
    
    if is_parent:
        back_url = reverse('parent_dashboard')
    else:
        back_url = reverse('child_dashboard', args=[child.id])
    
    return render(request, 'chores/coin_history.html', {
        'child': child,
        'ledgers': ledgers,
        'back_url': back_url,
        'is_parent': is_parent,
    })


# ==========================================
# PARENT MANAGEMENT & ADMINISTRATION ACTIONS
# ==========================================

# Profiles
def add_profile(request):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    if request.method == 'POST':
        name = request.POST.get('name')
        user_type = request.POST.get('user_type', 'child')
        pin = request.POST.get('pin', '')
        emoji = request.POST.get('emoji', '👦')
        if name:
            Profile.objects.create(name=name, user_type=user_type, pin=pin, emoji=emoji)
    return redirect('parent_dashboard')


def delete_profile(request, profile_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
    if request.method == 'POST':
        profile = get_object_or_404(Profile, id=profile_id)
        profile.delete()
    return redirect('parent_dashboard')


# Tasks & Scheduling
def add_task(request):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        star_value = request.POST.get('star_value', 1)
        image = request.FILES.get('image')
        
        days_list = request.POST.getlist('allowed_days')
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
        
        if request.POST.get('clear_image') == 'on':
            if task.image:
                task.image.delete(save=False)
            task.image = None
        elif 'image' in request.FILES:
            task.image = request.FILES['image']
            
        days_list = request.POST.getlist('allowed_days')
        if days_list:
            task.allowed_days = ",".join(days_list)
            
        task.save()
        return redirect('parent_dashboard')
        
    return render(request, 'chores/edit_task.html', {'task': task})


def delete_task(request, task_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
    task = get_object_or_404(Task, id=task_id)
    task.delete()
    return redirect('parent_dashboard')


def approve_task(request, task_status_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
    action = request.POST.get('action')
    if action == 'reject':
        task_status = get_object_or_404(DailyTaskStatus, id=task_status_id)
        task_status.status = 'denied'
        task_status.save()
    else:
        task_status = get_object_or_404(DailyTaskStatus, id=task_status_id)
        if task_status.status == 'waiting':
            task_status.status = 'approved'
            task_status.save()
            
            # Log earned stars to StarLedger
            StarLedger.objects.create(
                child=task_status.child,
                amount=task_status.task.star_value,
                reason=f"Completed chore: {task_status.task.title}"
            )
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
    
    if status_obj.status == 'approved':
        # Unapproving: revert status and deduct stars via ledger
        status_obj.status = 'pending'
        status_obj.save()
        
        StarLedger.objects.create(
            child=child,
            amount=-task.star_value,
            reason=f"Unapproved chore ({target_date}): {task.title}"
        )
    else:
        # Approving: set status and add stars via ledger
        status_obj.status = 'approved'
        status_obj.save()
        
        StarLedger.objects.create(
            child=child,
            amount=task.star_value,
            reason=f"Completed chore ({target_date}): {task.title}"
        )
    
    return redirect('parent_dashboard')


# Rewards Management & Approvals
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
    action = request.POST.get('action')
    if action == 'reject':
        # Refund stars via StarLedger
        StarLedger.objects.create(
            child=redemption.child,
            amount=redemption.reward.star_cost,
            reason=f"Refund: Denied reward '{redemption.reward.title}'"
        )
        redemption.delete()
    else:
        redemption.status = 'approved'
        redemption.save()
    return redirect('parent_dashboard')


def deny_reward(request, redemption_id):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
    redemption = get_object_or_404(RedemptionLog, id=redemption_id)
    StarLedger.objects.create(
        child=redemption.child,
        amount=redemption.reward.star_cost,
        reason=f"Refund: Denied reward '{redemption.reward.title}'"
    )
    redemption.delete()
    return redirect('parent_dashboard')


# Quiz Management & Imports
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


def import_quizzes_from_text(request):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    if request.method == 'POST':
        child_id = request.POST.get('child_id')
        child = get_object_or_404(Profile, id=child_id, user_type='child')
        raw_text = request.POST.get('raw_text', '')
        
        QuizQuestion.objects.filter(child=child).delete()
        
        io_string = io.StringIO(raw_text.strip())
        reader = csv.reader(io_string)
        
        for row in reader:
            if not row or (len(row) == 1 and row[0].strip().startswith('#')):
                continue
                
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


# Coin Store Management
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


def arcade_hub(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)
    
    if profile.user_type == 'parent':
        back_url = reverse('parent_dashboard')
    else:
        back_url = reverse('child_dashboard', args=[profile.id])
        
    return render(request, 'chores/arcade_hub.html', {
        'profile': profile,
        'coin_balance': profile.get_coin_balance(),
        'back_url': back_url,
    })

def arcade_star_dash(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)
    hs = ArcadeHighScore.objects.filter(child=profile, game_key='star_dash').first()
    return render(request, 'chores/arcade_dash.html', {
        'profile': profile,
        'coin_balance': profile.get_coin_balance(),
        'high_score': hs.score if hs else 0,
    })

def arcade_star_catcher(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)
    hs = ArcadeHighScore.objects.filter(child=profile, game_key='star_catcher').first()
    return render(request, 'chores/arcade_catcher.html', {
        'profile': profile,
        'coin_balance': profile.get_coin_balance(),
        'high_score': hs.score if hs else 0,
    })

@require_POST
def arcade_bonus(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id, user_type='child')
    
    # Record +1 coin bonus for arcade high score
    CoinLedger.objects.create(
        child=profile,
        amount=1,
        reason="Arcade High Score Bonus! 🪙🕹️"
    )
    
    return JsonResponse({'status': 'success', 'new_balance': profile.get_coin_balance()})

def arcade_balloon_pop(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)
    hs = ArcadeHighScore.objects.filter(child=profile, game_key='balloon_pop').first()
    return render(request, 'chores/arcade_balloon.html', {
        'profile': profile,
        'coin_balance': profile.get_coin_balance(),
        'high_score': hs.score if hs else 0,
    })

def arcade_math_monster(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)
    hs = ArcadeHighScore.objects.filter(child=profile, game_key='math_monster').first()
    return render(request, 'chores/arcade_math.html', {
        'profile': profile,
        'coin_balance': profile.get_coin_balance(),
        'high_score': hs.score if hs else 0,
    })

def arcade_memory_match(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)
    
    hs_1 = ArcadeHighScore.objects.filter(child=profile, game_key='memory_match_1').first()
    hs_2 = ArcadeHighScore.objects.filter(child=profile, game_key='memory_match_2').first()
    
    return render(request, 'chores/arcade_memory.html', {
        'profile': profile,
        'coin_balance': profile.get_coin_balance(),
        'high_score_1': hs_1.score if hs_1 else 999,
        'high_score_2': hs_2.score if hs_2 else 999,
    })

@require_POST
def submit_arcade_score(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)
    try:
        data = json.loads(request.body)
        game_key = data.get('game_key')
        game_title = data.get('game_title', 'Game')
        score = int(data.get('score', 0))
        is_lower_better = data.get('is_lower_better', False) # e.g., for Memory Match moves
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid payload'}, status=400)

    obj, created = ArcadeHighScore.objects.get_or_create(
        child=profile,
        game_key=game_key,
        defaults={'game_title': game_title, 'score': score}
    )

    new_record = False
    if not created:
        if is_lower_better:
            if score < obj.score: # fewer moves is better
                obj.score = score
                obj.game_title = game_title
                obj.save()
                new_record = True
        else:
            if score > obj.score: # higher score is better
                obj.score = score
                obj.game_title = game_title
                obj.save()
                new_record = True
    else:
        new_record = True

    earned_bonus = False
    if new_record:
        CoinLedger.objects.create(
            child=profile,
            amount=1,
            reason=f"Arcade High Score Bonus ({game_title})! 🪙🕹️"
        )
        earned_bonus = True

    return JsonResponse({
        'status': 'success',
        'new_record': new_record,
        'earned_bonus': earned_bonus,
        'high_score': obj.score,
        'new_balance': profile.get_coin_balance()
    })

def arcade_high_scores_view(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)
    
    if profile.user_type == 'parent':
        dashboard_url = reverse('parent_dashboard')
    else:
        dashboard_url = reverse('child_dashboard', args=[profile.id])
        
    config = ParentNotificationConfig.objects.first()
    show_shared = config.show_shared_leaderboard if config else True
    
    if show_shared or profile.user_type == 'parent':
        players = Profile.objects.all()
        all_scores = ArcadeHighScore.objects.select_related('child').all()
        unique_games = all_scores.values('game_key', 'game_title').distinct()
        score_map = {(s.game_key, s.child_id): s for s in all_scores}
        
        leaderboard_data = []
        for game in unique_games:
            game_key = game['game_key']
            game_title = game['game_title']
            is_memory_match = ('memory' in game_key.lower())
            default_score = 999 if is_memory_match else '---'
            
            # First, gather scores for this game to find the winning benchmark
            valid_scores = []
            for player in players:
                score_obj = score_map.get((game_key, player.id))
                if score_obj:
                    valid_scores.append(score_obj.score)
            
            # Determine the best score value (lowest for memory, highest for others)
            best_score = None
            if valid_scores:
                best_score = min(valid_scores) if is_memory_match else max(valid_scores)
            
            row = {'game_key': game_key, 'game_title': game_title, 'child_scores': []}
            for player in players:
                score_obj = score_map.get((game_key, player.id))
                score_val = score_obj.score if score_obj else default_score
                
                # Check if this player holds the top record
                is_leader = (best_score is not None and score_val == best_score)
                
                row['child_scores'].append({
                    'child': player,
                    'score': score_val,
                    'is_leader': is_leader, # <-- Flag leader
                    'updated_at': score_obj.updated_at if score_obj else None
                })
            leaderboard_data.append(row)
            
        return render(request, 'chores/arcade_leaderboard.html', {
            'profile': profile,
            'coin_balance': profile.get_coin_balance(),
            'leaderboard_data': leaderboard_data,
            'dashboard_url': dashboard_url,
            'is_shared_view': True,
        })
    else:
        scores = ArcadeHighScore.objects.filter(child=profile).order_by('-updated_at')
        return render(request, 'chores/arcade_scores.html', {
            'profile': profile,
            'scores': scores,
            'coin_balance': profile.get_coin_balance(),
            'dashboard_url': dashboard_url,
            'is_shared_view': False,
        })

def parent_arcade_leaderboard(request):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    children = Profile.objects.filter()
    
    # Fetch all database high scores
    all_scores = ArcadeHighScore.objects.select_related('child').all()
    
    # Dynamically discover unique games present in the database 
    # (combines game_key and game_title pairs)
    unique_games = all_scores.values('game_key', 'game_title').distinct()
    
    # Map (game_key, child_id) -> score object
    score_map = {(s.game_key, s.child_id): s for s in all_scores}
    
    # Build a structured list of dynamically found games with each child's score
    leaderboard_data = []
    for game in unique_games:
        game_key = game['game_key']
        game_title = game['game_title']
        
        # Check if it's memory match so we know the default fallback score (lower is better)
        is_memory_match = ('memory' in game_key.lower())
        default_score = 999 if is_memory_match else '---'
        
        row = {'game_key': game_key, 'game_title': game_title, 'child_scores': []}
        for child in children:
            score_obj = score_map.get((game_key, child.id))
            row['child_scores'].append({
                'child': child,
                'score': score_obj.score if score_obj else default_score,
                'updated_at': score_obj.updated_at if score_obj else None
            })
        leaderboard_data.append(row)

    return render(request, 'chores/arcade_leaderboard.html', {
        'children': children,
        'leaderboard_data': leaderboard_data,
    })

def pet_room_view(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id, user_type='child')
    pet, created = VirtualPet.objects.get_or_create(child=profile, defaults={'name': 'StarBuddy'})
    
    return render(request, 'chores/pet_room.html', {
        'profile': profile,
        'pet': pet,
        'coin_balance': profile.get_coin_balance(),
    })

@require_POST
def pet_action_feed(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id, user_type='child')
    pet = get_object_or_404(VirtualPet, child=profile)
    
    pet.hunger = min(100, pet.hunger + 30)
    pet.add_xp(15)
    pet.save()
    
    return JsonResponse({
        'status': 'success',
        'hunger': pet.hunger,
        'happiness': pet.happiness,
        'poop_count': pet.poop_count,
        'level': pet.level,
        'experience': pet.experience,
        'species': pet.get_species_name(),
        'emoji': pet.get_emoji()
    })

@require_POST
def pet_action_clean(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id, user_type='child')
    pet = get_object_or_404(VirtualPet, child=profile)
    
    pet.poop_count = 0
    pet.happiness = min(100, pet.happiness + 20)
    pet.add_xp(10)
    pet.save()
    
    return JsonResponse({
        'status': 'success',
        'happiness': pet.happiness,
        'poop_count': pet.poop_count,
        'level': pet.level,
        'experience': pet.experience
    })

def arcade_number_runner(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)
    
    # Fetch high score from database
    high_score_obj = ArcadeHighScore.objects.filter(child=profile, game_key='number_runner').first()
    high_score = high_score_obj.score if high_score_obj else 0
    
    return render(request, 'chores/arcade_number_runner.html', {
        'profile': profile,
        'coin_balance': profile.get_coin_balance(),
        'high_score': high_score,
    })

def arcade_fireworks(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)
    hs = ArcadeHighScore.objects.filter(child=profile, game_key='star_fireworks').first()
    return render(request, 'chores/arcade_fireworks.html', {
        'profile': profile,
        'coin_balance': profile.get_coin_balance(),
        'high_score': hs.score if hs else 0,
    })

def arcade_number_jump(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)
    hs = ArcadeHighScore.objects.filter(child=profile, game_key='number_jump').first()
    return render(request, 'chores/arcade_number_jump.html', {
        'profile': profile,
        'coin_balance': profile.get_coin_balance(),
        'high_score': hs.score if hs else 0,
    })

def update_notifications(request):
    if not request.session.get('is_parent_authenticated'):
        return redirect('parent_login')
        
    if request.method == 'POST':
        parent_id = request.POST.get('parent_id')
        parent = get_object_or_404(Profile, id=parent_id, user_type='parent')
        
        config, created = ParentNotificationConfig.objects.get_or_create(parent=parent)
        config.webhook_url = request.POST.get('webhook_url', '').strip()
        config.notify_chore_waiting = 'notify_chore_waiting' in request.POST
        config.notify_reward_requested = 'notify_reward_requested' in request.POST
        config.notify_quiz_completed = 'notify_quiz_completed' in request.POST
        config.show_shared_leaderboard = 'show_shared_leaderboard' in request.POST
        config.save()
        
    return redirect('management_hub')