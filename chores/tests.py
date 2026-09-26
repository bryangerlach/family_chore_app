from django.test import TestCase, Client
from django.urls import reverse
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
    StarLedger
)
from django.utils import timezone

class QuizAttemptTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.parent = Profile.objects.create(name="Dad", user_type="parent")
        self.child = Profile.objects.create(name="Leo", user_type="child")
        
        # Create a quiz question linked to the child
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
        # Simulate a completed quiz attempt
        QuizAttempt.objects.create(
            child=self.child,
            question=self.question
        )
        
        # Post answer to submit_quiz view
        response = self.client.post(
            reverse('submit_quiz', args=[self.child.id, self.question.id]),
            {'answer': 'B'}
        )
        
        # Should redirect back with feedback indicating already solved
        self.assertRedirects(response, f"/child/{self.child.id}/quiz/?feedback=already_solved", fetch_redirect_response=False)

    def test_solved_quiz_remains_unavailable(self):
        """Verify that once solved, the question is excluded from available quizzes."""
        QuizAttempt.objects.create(
            child=self.child,
            question=self.question
        )
        
        solved_ids = QuizAttempt.objects.filter(child=self.child).values_list('question_id', flat=True)
        available_questions = QuizQuestion.objects.filter(child=self.child).exclude(id__in=solved_ids)
        
        self.assertEqual(available_questions.count(), 0)


class CsvBatchImportTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.parent = Profile.objects.create(name="Mom", user_type="parent", pin="1234")
        self.child = Profile.objects.create(name="Mia", user_type="child")
        
        # Authenticate parent session
        session = self.client.session
        session['is_parent_authenticated'] = True
        session.save()

    def test_import_quizzes_from_text_view_with_wipe_and_replace(self):
        """Verify that import_quizzes_from_text wipes old questions and correctly parses CSV rows including quotes and commas."""
        # Create an old question that should be wiped out
        QuizQuestion.objects.create(
            child=self.child,
            question_type="math",
            question_text="Old Question?",
            option_a="1", option_b="2", correct_answer="A"
        )
        self.assertEqual(QuizQuestion.objects.filter(child=self.child).count(), 1)
        
        # CSV payload matching view's expected format (>= 8 parts):
        # type, text, opt_a, opt_b, opt_c, opt_d, correct, reward, passage
        csv_payload = (
            'math,"If you have 3 apples, and eat 2, how many are left?",0,1,2,3,B,5,\n'
            'reading,"Spell the word for ""feline""",dog,cat,bird,fish,B,5,Optional Passage'
        )
        
        response = self.client.post(reverse('import_quizzes_from_text'), {
            'child_id': self.child.id,
            'raw_text': csv_payload
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify wipe-and-replace result
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
        
        # Seed stars via approved task so get_stars_balance() calculates correctly
        task = Task.objects.create(title="Earn Stars Task", star_value=30)
        DailyTaskStatus.objects.create(
            child=self.child,
            task=task,
            status='approved'
        )
        
        self.reward = Reward.objects.create(
            title="Extra Screen Time",
            star_cost=20,
            reward_type="recurring"
        )
        
        # Authenticate parent session
        session = self.client.session
        session['is_parent_authenticated'] = True
        session.save()

    def test_reward_approval_view_workflow(self):
        """Test child redemption log creation and parent approval view action."""
        redemption = RedemptionLog.objects.create(
            child=self.child,
            reward=self.reward,
            status="pending"
        )
        
        self.assertEqual(redemption.status, "pending")
        
        # Call parent approval view endpoint
        response = self.client.get(reverse('approve_reward', args=[redemption.id]))
        self.assertEqual(response.status_code, 302)
        
        redemption.refresh_from_db()
        self.assertEqual(redemption.status, "approved")

    def test_reward_denial_view_workflow(self):
        """Test parent denial view endpoint on a pending redemption."""
        child = Profile.objects.create(name="Leo", user_type="child")
        reward = Reward.objects.create(title="Toy", star_cost=5)
        redemption = RedemptionLog.objects.create(child=child, reward=reward, status='pending')
        
        client = Client()
        session = client.session
        session['is_parent_authenticated'] = True
        session.save()
        
        response = client.post(reverse('approve_reward', args=[redemption.id]), {'action': 'reject'})
        self.assertEqual(response.status_code, 302)
        
        # Since reject deletes the log to refund stars, verify it no longer exists
        self.assertFalse(RedemptionLog.objects.filter(id=redemption.id).exists())

    def test_reject_reward_refunds_stars(self):
        """Verify that rejecting a reward request via approve_reward view refunds the stars."""
        # Setup child and give them 10 stars via StarLedger (representing approved chore earnings)
        child = Profile.objects.create(name="Leo", user_type="child")
        StarLedger.objects.create(
            child=child,
            amount=10,
            reason="Completed chore: Big Chore"
        )
        self.assertEqual(child.get_stars_balance(), 10)
        
        reward = Reward.objects.create(title="Toy", star_cost=5)
        
        # Create a pending redemption (which holds/deducts 5 stars via ledger)
        redemption = RedemptionLog.objects.create(child=child, reward=reward, status='pending')
        
        # Manually deduct 5 stars for the request (as redeem_reward view does)
        StarLedger.objects.create(
            child=child,
            amount=-5,
            reason=f"Requested reward: {reward.title}"
        )
        self.assertEqual(child.get_stars_balance(), 5) # 10 earned - 5 spent
        
        # Authenticate parent session
        client = Client()
        session = client.session
        session['is_parent_authenticated'] = True
        session.save()
        
        # Post reject action to the approve_reward view
        response = client.post(reverse('approve_reward', args=[redemption.id]), {'action': 'reject'})
        self.assertEqual(response.status_code, 302)
        
        # Verify redemption is deleted and stars are fully refunded back to 10
        self.assertFalse(RedemptionLog.objects.filter(id=redemption.id).exists())
        self.assertEqual(child.get_stars_balance(), 10)


class CoinStoreAndLedgerTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.child = Profile.objects.create(name="Eli", user_type="child")
        
        # Seed initial coins via ledger
        CoinLedger.objects.create(
            child=self.child,
            amount=50,
            reason="Initial Bank"
        )
        
        self.store_item = CoinStoreItem.objects.create(
            title="1 Star Point",
            coin_cost=15,
            star_value_granted=1
        )

    def test_coin_store_purchase_deducts_coins_and_grants_stars(self):
        """Verify that purchasing an item deducts coins and correctly triggers star credit."""
        initial_coins = self.child.get_coin_balance()
        self.assertEqual(initial_coins, 50)
        
        response = self.client.get(reverse('buy_coin_item', args=[self.child.id, self.store_item.id]))
        self.assertEqual(response.status_code, 302)
        
        self.child.refresh_from_db()
        # Coins should decrease by 15
        self.assertEqual(self.child.get_coin_balance(), 35)
        # Stars granted should reflect in profile balance calculation
        self.assertEqual(self.child.get_stars_balance(), 1)

    def test_multiple_coin_store_purchases_same_day(self):
        """Verify that purchasing a star-granting item multiple times on the same day works without collision or errors."""
        initial_coins = self.child.get_coin_balance() # 50
        initial_stars = self.child.get_stars_balance() # 0
        
        # First purchase
        response1 = self.client.get(reverse('buy_coin_item', args=[self.child.id, self.store_item.id]))
        self.assertEqual(response1.status_code, 302)
        
        # Second purchase on the same day
        response2 = self.client.get(reverse('buy_coin_item', args=[self.child.id, self.store_item.id]))
        self.assertEqual(response2.status_code, 302)
        
        self.child.refresh_from_db()
        
        # Check balances: 50 - 15 - 15 = 20 coins; 0 + 1 + 1 = 2 stars
        self.assertEqual(self.child.get_coin_balance(), 20)
        self.assertEqual(self.child.get_stars_balance(), 2)
        
        # Verify that loading the child dashboard view doesn't crash with MultipleObjectsReturned
        dashboard_response = self.client.get(reverse('child_dashboard', args=[self.child.id]))
        self.assertEqual(dashboard_response.status_code, 200)

class TaskImageAndEditTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.parent = Profile.objects.create(name="Dad", user_type="parent")
        
        # Authenticate parent session
        session = self.client.session
        session['is_parent_authenticated'] = True
        session.save()
        
        self.task = Task.objects.create(
            title="Clean Room",
            star_value=3
        )

    def test_edit_task_clears_image(self):
        """Verify that checking 'clear_image' successfully removes the image from the task."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        # Assign an initial dummy image
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff'
            b'\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00'
            b'\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
        )
        uploaded_image = SimpleUploadedFile('small.gif', small_gif, content_type='image/gif')
        self.task.image = uploaded_image
        self.task.save()
        self.assertTrue(bool(self.task.image))
        
        # Post edit request with clear_image checked
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
        
        # Authenticate parent session
        session = self.client.session
        session['is_parent_authenticated'] = True
        session.save()

    def test_adjust_child_stars_success(self):
        """Verify parent can manually add and deduct stars via adjust_child_stars view."""
        url = reverse('adjust_child_stars', args=[self.child.id])
        
        # Add stars
        response = self.client.post(url, {'amount': '10', 'reason': 'Bonus reward'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.child.get_stars_balance(), 10)
        self.assertTrue(StarLedger.objects.filter(child=self.child, amount=10).exists())
        
        # Deduct stars
        response = self.client.post(url, {'amount': '-3', 'reason': 'Penalty'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.child.get_stars_balance(), 7)

    def test_adjust_child_coins_success(self):
        """Verify parent can manually add and deduct coins via adjust_child_coins view."""
        url = reverse('adjust_child_coins', args=[self.child.id])
        
        # Add coins
        response = self.client.post(url, {'amount': '25', 'reason': 'Extra allowance'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.child.get_coin_balance(), 25)
        self.assertTrue(CoinLedger.objects.filter(child=self.child, amount=25).exists())
        
        # Deduct coins
        response = self.client.post(url, {'amount': '-5', 'reason': 'Fine'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.child.get_coin_balance(), 20)

    def test_unauthenticated_adjustment_redirects(self):
        """Verify unauthenticated users cannot adjust balances."""
        unauth_client = Client() # Session not authenticated
        url_stars = reverse('adjust_child_stars', args=[self.child.id])
        url_coins = reverse('adjust_child_coins', args=[self.child.id])
        
        res1 = unauth_client.post(url_stars, {'amount': '5', 'reason': 'Unauthorized'})
        res2 = unauth_client.post(url_coins, {'amount': '5', 'reason': 'Unauthorized'})
        
        self.assertEqual(res1.status_code, 302)
        self.assertEqual(res2.status_code, 302)
        self.assertEqual(self.child.get_stars_balance(), 0)
        self.assertEqual(self.child.get_coin_balance(), 0)