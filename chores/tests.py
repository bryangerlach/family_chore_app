from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from chores.models import (
    Profile,
    Task,
    DailyTaskStatus,
    QuizQuestion,
    QuizAttempt,
    QuizWrongAttempt,
    Reward,
    RedemptionLog,
    CoinStoreItem,
    CoinLedger,
    StarLedger,
    ArcadeHighScore
)
import json

class QuizAttemptTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.parent = Profile.objects.create(name="Dad", user_type="parent")
        self.child = Profile.objects.create(name="Leo", user_type="child")
        
        self.question = QuizQuestion.objects.create(
            child=self.child,
            question_type="math",
            question_text="What is 5 + 5?",
            option_a="8",
            option_b="10",
            option_c="11",
            option_d="12",
            correct_answer="B",
            coin_reward=5
        )

    def test_solved_quiz_blocks_re_answering(self):
        """Verify that a child attempting an already solved quiz is redirected and blocked."""
        QuizAttempt.objects.create(child=self.child, question=self.question)
        
        response = self.client.post(
            reverse('submit_quiz', args=[self.child.id, self.question.id]),
            {'answer': 'B'}
        )
        self.assertRedirects(response, f"/child/{self.child.id}/quiz/?feedback=already_solved", fetch_redirect_response=False)

    def test_solved_quiz_remains_unavailable(self):
        """Verify that once solved, the question is excluded from available quizzes."""
        QuizAttempt.objects.create(child=self.child, question=self.question)
        
        solved_ids = QuizAttempt.objects.filter(child=self.child).values_list('question_id', flat=True)
        available_questions = QuizQuestion.objects.filter(child=self.child).exclude(id__in=solved_ids)
        
        self.assertEqual(available_questions.count(), 0)


class CsvBatchImportTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.parent = Profile.objects.create(name="Mom", user_type="parent", pin="1234")
        self.child = Profile.objects.create(name="Mia", user_type="child")
        
        session = self.client.session
        session['is_parent_authenticated'] = True
        session.save()

    def test_import_quizzes_from_text_view_with_wipe_and_replace(self):
        """Verify that import_quizzes_from_text wipes old questions and correctly parses CSV rows."""
        QuizQuestion.objects.create(
            child=self.child,
            question_type="math",
            question_text="Old Question?",
            option_a="1", option_b="2", correct_answer="A"
        )
        self.assertEqual(QuizQuestion.objects.filter(child=self.child).count(), 1)
        
        csv_payload = (
            'math,"If you have 3 apples, and eat 2, how many are left?",0,1,2,3,B,5,\n'
            'reading,"Spell the word for ""feline""",dog,cat,bird,fish,B,5,Optional Passage'
        )
        
        response = self.client.post(reverse('import_quizzes_from_text'), {
            'child_id': self.child.id,
            'raw_text': csv_payload
        })
        
        self.assertEqual(response.status_code, 302)
        
        questions = QuizQuestion.objects.filter(child=self.child)
        self.assertEqual(questions.count(), 2)
        
        q1 = questions.first()
        self.assertEqual(q1.question_type, "math")
        self.assertEqual(q1.correct_answer, "B")
        self.assertIn("3 apples", q1.question_text)


class RewardApprovalWorkflowTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.parent = Profile.objects.create(name="Dad", user_type="parent")
        self.child = Profile.objects.create(name="Sam", user_type="child")
        
        task = Task.objects.create(title="Earn Stars Task", star_value=30)
        DailyTaskStatus.objects.create(child=self.child, task=task, status='approved')
        
        self.reward = Reward.objects.create(title="Extra Screen Time", star_cost=20, reward_type="recurring")
        
        session = self.client.session
        session['is_parent_authenticated'] = True
        session.save()

    def test_reward_approval_view_workflow(self):
        """Test child redemption log creation and parent approval view action."""
        redemption = RedemptionLog.objects.create(child=self.child, reward=self.reward, status="pending")
        self.assertEqual(redemption.status, "pending")
        
        response = self.client.get(reverse('approve_reward', args=[redemption.id]))
        self.assertEqual(response.status_code, 302)
        
        redemption.refresh_from_db()
        self.assertEqual(redemption.status, "approved")

    def test_reward_denial_view_workflow(self):
        """Test parent denial view endpoint on a pending redemption."""
        redemption = RedemptionLog.objects.create(child=self.child, reward=self.reward, status='pending')
        
        response = self.client.post(reverse('approve_reward', args=[redemption.id]), {'action': 'reject'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(RedemptionLog.objects.filter(id=redemption.id).exists())

    def test_reject_reward_refunds_stars(self):
        """Verify that rejecting a reward request via approve_reward view refunds the stars."""
        StarLedger.objects.create(child=self.child, amount=10, reason="Completed chore")
        self.assertEqual(self.child.get_stars_balance(), 10)
        
        redemption = RedemptionLog.objects.create(child=self.child, reward=self.reward, status='pending')
        StarLedger.objects.create(child=self.child, amount=-20, reason="Requested reward")
        
        response = self.client.post(reverse('approve_reward', args=[redemption.id]), {'action': 'reject'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(RedemptionLog.objects.filter(id=redemption.id).exists())


class CoinStoreAndLedgerTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.child = Profile.objects.create(name="Eli", user_type="child")
        
        CoinLedger.objects.create(child=self.child, amount=50, reason="Initial Bank")
        self.store_item = CoinStoreItem.objects.create(title="1 Star Point", coin_cost=15, star_value_granted=1)

    def test_coin_store_purchase_deducts_coins_and_grants_stars(self):
        """Verify that purchasing an item deducts coins and correctly triggers star credit."""
        self.assertEqual(self.child.get_coin_balance(), 50)
        
        response = self.client.get(reverse('buy_coin_item', args=[self.child.id, self.store_item.id]))
        self.assertEqual(response.status_code, 302)
        
        self.child.refresh_from_db()
        self.assertEqual(self.child.get_coin_balance(), 35)
        self.assertEqual(self.child.get_stars_balance(), 1)

    def test_multiple_coin_store_purchases_same_day(self):
        """Verify multiple purchases on the same day work without collision."""
        self.client.get(reverse('buy_coin_item', args=[self.child.id, self.store_item.id]))
        self.client.get(reverse('buy_coin_item', args=[self.child.id, self.store_item.id]))
        
        self.child.refresh_from_db()
        self.assertEqual(self.child.get_coin_balance(), 20)
        self.assertEqual(self.child.get_stars_balance(), 2)
        
        dashboard_response = self.client.get(reverse('child_dashboard', args=[self.child.id]))
        self.assertEqual(dashboard_response.status_code, 200)


class TaskImageAndEditTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.parent = Profile.objects.create(name="Dad", user_type="parent")
        
        session = self.client.session
        session['is_parent_authenticated'] = True
        session.save()
        
        self.task = Task.objects.create(title="Clean Room", star_value=3)

    def test_edit_task_clears_image(self):
        """Verify that checking 'clear_image' successfully removes the image from the task."""
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff'
            b'\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00'
            b'\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
        )
        self.task.image = SimpleUploadedFile('small.gif', small_gif, content_type='image/gif')
        self.task.save()
        self.assertTrue(bool(self.task.image))
        
        response = self.client.post(reverse('edit_task', args=[self.task.id]), {
            'title': 'Clean Room Updated',
            'star_value': 3,
            'clear_image': 'on'
        })
        
        self.assertEqual(response.status_code, 302)
        self.task.refresh_from_db()
        self.assertFalse(bool(self.task.image))


class ManualAdjustmentTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.parent = Profile.objects.create(name="Dad", user_type="parent", pin="1234")
        self.child = Profile.objects.create(name="Leo", user_type="child")
        
        session = self.client.session
        session['is_parent_authenticated'] = True
        session.save()

    def test_adjust_child_stars_success(self):
        """Verify parent can manually add and deduct stars."""
        url = reverse('adjust_child_stars', args=[self.child.id])
        
        self.client.post(url, {'amount': '10', 'reason': 'Bonus reward'})
        self.assertEqual(self.child.get_stars_balance(), 10)
        
        self.client.post(url, {'amount': '-3', 'reason': 'Penalty'})
        self.assertEqual(self.child.get_stars_balance(), 7)

    def test_adjust_child_coins_success(self):
        """Verify parent can manually add and deduct coins."""
        url = reverse('adjust_child_coins', args=[self.child.id])
        
        self.client.post(url, {'amount': '25', 'reason': 'Allowance'})
        self.assertEqual(self.child.get_coin_balance(), 25)
        
        self.client.post(url, {'amount': '-5', 'reason': 'Fine'})
        self.assertEqual(self.child.get_coin_balance(), 20)

    def test_unauthenticated_adjustment_redirects(self):
        """Verify unauthenticated users cannot adjust balances."""
        unauth_client = Client()
        url = reverse('adjust_child_stars', args=[self.child.id])
        res = unauth_client.post(url, {'amount': '5', 'reason': 'Unauthorized'})
        self.assertEqual(res.status_code, 302)


class ArcadeAndReversalTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.parent = Profile.objects.create(name="Dad", user_type="parent")
        self.child = Profile.objects.create(name="Timmy", user_type="child")
        
        session = self.client.session
        session['is_parent_authenticated'] = True
        session.save()

    def test_arcade_high_score_bonus_awards_coin(self):
        """Verify submitting high score awards +1 coin."""
        url = reverse('submit_arcade_score', args=[self.child.id])
        response = self.client.post(
            url,
            data=json.dumps({'game_key': 'star_dash', 'game_title': 'Star Dash', 'score': 150, 'is_lower_better': False}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['earned_bonus'])
        self.assertEqual(self.child.get_coin_balance(), 1)

    def test_arcade_high_score_lower_is_better(self):
        """Verify lower score logic for Memory Match."""
        ArcadeHighScore.objects.create(child=self.child, game_key='memory_match', game_title='Memory Match', score=15)
        url = reverse('submit_arcade_score', args=[self.child.id])
        
        # Submit worse score (20 moves) -> should not update
        res_worse = self.client.post(url, data=json.dumps({'game_key': 'memory_match', 'score': 20, 'is_lower_better': True}), content_type='application/json')
        self.assertFalse(res_worse.json()['new_record'])
        
        # Submit better score (10 moves) -> should update
        res_better = self.client.post(url, data=json.dumps({'game_key': 'memory_match', 'score': 10, 'is_lower_better': True}), content_type='application/json')
        self.assertTrue(res_better.json()['new_record'])

    def test_arcade_high_scores_view(self):
        """Verify child trophy room view loads successfully."""
        ArcadeHighScore.objects.create(child=self.child, game_key='balloon_pop', game_title='Balloon Pop', score=45)
        response = self.client.get(reverse('arcade_high_scores', args=[self.child.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Balloon Pop')

    def test_parent_arcade_leaderboard_view(self):
        """Verify parent leaderboard view loads successfully."""
        child2 = Profile.objects.create(name="Mia", user_type="child")
        ArcadeHighScore.objects.create(child=self.child, game_key='star_dash', game_title='Star Dash', score=100)
        ArcadeHighScore.objects.create(child=child2, game_key='star_dash', game_title='Star Dash', score=200)
        
        response = self.client.get(reverse('parent_arcade_leaderboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Timmy')
        self.assertContains(response, 'Mia')

    def test_reverse_star_ledger_entry(self):
        """Verify reversing a StarLedger entry creates offsetting counter-entry."""
        entry = StarLedger.objects.create(child=self.child, amount=10, reason="Bonus")
        self.assertEqual(self.child.get_stars_balance(), 10)
        
        self.client.post(reverse('reverse_star_ledger', args=[entry.id]))
        self.assertEqual(self.child.get_stars_balance(), 0)

    def test_reverse_coin_ledger_entry(self):
        """Verify reversing a CoinLedger entry creates offsetting counter-entry."""
        entry = CoinLedger.objects.create(child=self.child, amount=25, reason="Allowance")
        self.assertEqual(self.child.get_coin_balance(), 25)
        
        self.client.post(reverse('reverse_coin_ledger', args=[entry.id]))
        self.assertEqual(self.child.get_coin_balance(), 0)