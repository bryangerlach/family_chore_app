from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from chores.models import Profile, Task, Reward, DailyTaskStatus, RedemptionLog

class FamilyChoreComprehensiveTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Create test profiles
        self.child = Profile.objects.create(name="Leo", user_type="child", emoji="🦖")
        
        # Create tasks with specific schedules (e.g. today's weekday)
        self.today = timezone.localdate()
        python_wd = self.today.weekday()
        self.today_sunday_index = str((python_wd + 1) % 7)
        
        self.scheduled_task = Task.objects.create(
            title="Take out trash", 
            star_value=2, 
            allowed_days=self.today_sunday_index
        )
        self.unscheduled_task = Task.objects.create(
            title="Mow lawn", 
            star_value=5, 
            allowed_days="99" # Invalid index so it never matches today
        )
        
        # Create different reward types
        self.recurring_reward = Reward.objects.create(title="Extra Tablet", star_cost=3, reward_type="recurring")
        self.weekly_reward = Reward.objects.create(title="Free Ice Cream", star_cost=0, reward_type="weekly")
        self.one_time_reward = Reward.objects.create(title="New Toy", star_cost=10, reward_type="one_time", is_one_time=True)

    def test_star_balance_ledger(self):
        """Test that star balance correctly calculates earnings minus redemptions."""
        self.assertEqual(self.child.get_stars_balance(), 0)
        
        # Earn stars via approved task status
        ts = DailyTaskStatus.objects.create(child=self.child, task=self.scheduled_task, date=self.today, status='approved')
        self.assertEqual(self.child.get_stars_balance(), 2)
        
        # Spend stars via approved reward redemption
        RedemptionLog.objects.create(child=self.child, reward=self.recurring_reward, status='approved')
        self.assertEqual(self.child.get_stars_balance(), -1) # 2 - 3 = -1

    def test_child_dashboard_task_filtering(self):
        """Test that child dashboard only shows tasks scheduled for today."""
        response = self.client.get(reverse('child_dashboard', args=[self.child.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Take out trash")
        self.assertNotContains(response, "Mow lawn")

    def test_task_approval_workflow(self):
        """Test child request, parent approval, and reset workflows."""
        ts = DailyTaskStatus.objects.create(child=self.child, task=self.scheduled_task, date=self.today, status='pending')
        
        # Child requests approval
        response = self.client.post(reverse('request_approval', args=[ts.id]))
        ts.refresh_from_db()
        self.assertEqual(ts.status, 'waiting')
        
        # Parent session login
        session = self.client.session
        session['is_parent_authenticated'] = True
        session.save()
        
        # Parent approves task
        response = self.client.post(reverse('approve_task', args=[ts.id]))
        ts.refresh_from_db()
        self.assertEqual(ts.status, 'approved')
        self.assertEqual(self.child.get_stars_balance(), 2)

        # Parent resets task back to pending
        response = self.client.post(reverse('reset_task', args=[ts.id]))
        ts.refresh_from_db()
        self.assertEqual(ts.status, 'pending')

    def test_reward_redemption_rules(self):
        """Test recurring, weekly reset, and one-time reward limitations."""
        # Give child plenty of stars
        DailyTaskStatus.objects.create(child=self.child, task=self.scheduled_task, date=self.today, status='approved')
        DailyTaskStatus.objects.create(child=self.child, task=self.scheduled_task, date=self.today - timedelta(days=1), status='approved')
        
        # 1. One-time reward should hide after claim
        RedemptionLog.objects.create(child=self.child, reward=self.one_time_reward, status='pending')
        response = self.client.get(reverse('child_dashboard', args=[self.child.id]))
        self.assertNotContains(response, "New Toy")

        # 2. Weekly reward should hide after claim this week
        RedemptionLog.objects.create(child=self.child, reward=self.weekly_reward, status='approved')
        response = self.client.get(reverse('child_dashboard', args=[self.child.id]))
        self.assertNotContains(response, "Free Ice Cream")

    def test_parent_authentication_and_management(self):
        """Test parent login, adding tasks, editing tasks, and deleting tasks."""
        # Unauthenticated access check
        response = self.client.get(reverse('parent_dashboard'))
        self.assertEqual(response.status_code, 302)
        
        # Authenticate parent session
        session = self.client.session
        session['is_parent_authenticated'] = True
        session.save()
        
        response = self.client.get(reverse('parent_dashboard'))
        self.assertEqual(response.status_code, 200)
        
        # Test adding a task via POST
        response = self.client.post(reverse('add_task'), {
            'title': 'Clean Room',
            'star_value': '3',
            'allowed_days': ['0', '1', '2', '3', '4', '5', '6']
        })
        self.assertTrue(Task.objects.filter(title='Clean Room').exists())
        
        # Test editing a task
        task = Task.objects.get(title='Clean Room')
        response = self.client.post(reverse('edit_task', args=[task.id]), {
            'title': 'Deep Clean Room',
            'star_value': '4'
        })
        task.refresh_from_db()
        self.assertEqual(task.title, 'Deep Clean Room')
        self.assertEqual(task.star_value, 4)

        # Test deleting a task
        response = self.client.post(reverse('delete_task', args=[task.id]))
        self.assertFalse(Task.objects.filter(id=task.id).exists())

    def test_emoji_customization(self):
        """Test updating child profile emoji via preset or manual entry."""
        response = self.client.post(reverse('update_child_emoji', args=[self.child.id]), {
            'emoji': '🚀'
        })
        self.child.refresh_from_db()
        self.assertEqual(self.child.emoji, '🚀')