"""
test_social_network.py
Minimum 15 test cases (including edge cases) as required by the brief.
Run with:  python -m unittest discover -s tests -v   (from project root)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core import SocialNetwork, merge_sort, binary_search_by_key, Trie


class TestUsersAndGraph(unittest.TestCase):
    def setUp(self):
        self.net = SocialNetwork()
        self.alice = self.net.add_user("alice")
        self.bob = self.net.add_user("bob")
        self.carol = self.net.add_user("carol")

    def test_add_user_creates_unique_ids(self):
        self.assertNotEqual(self.alice, self.bob)
        self.assertIn(self.alice, self.net.users)

    def test_add_friendship_is_undirected(self):
        self.net.add_friendship(self.alice, self.bob)
        self.assertIn(self.bob, self.net.graph[self.alice])
        self.assertIn(self.alice, self.net.graph[self.bob])

    def test_self_friendship_rejected(self):
        with self.assertRaises(ValueError):
            self.net.add_friendship(self.alice, self.alice)

    def test_friendship_with_unknown_user_raises(self):
        with self.assertRaises(KeyError):
            self.net.add_friendship(self.alice, "u_does_not_exist")

    def test_remove_friendship(self):
        self.net.add_friendship(self.alice, self.bob)
        self.net.remove_friendship(self.alice, self.bob)
        self.assertNotIn(self.bob, self.net.graph[self.alice])

    def test_bfs_mutual_friend_suggestion(self):
        # alice-bob-carol chain: carol should be suggested to alice (1 mutual: bob)
        self.net.add_friendship(self.alice, self.bob)
        self.net.add_friendship(self.bob, self.carol)
        suggestions = self.net.bfs_mutual_friend_suggestions(self.alice)
        suggested_ids = [uid for uid, _count in suggestions]
        self.assertIn(self.carol, suggested_ids)

    def test_bfs_suggestion_for_isolated_user_is_empty(self):
        dave = self.net.add_user("dave")
        self.assertEqual(self.net.bfs_mutual_friend_suggestions(dave), [])

    def test_bfs_suggestion_for_unknown_user_is_empty(self):
        self.assertEqual(self.net.bfs_mutual_friend_suggestions("ghost"), [])

    def test_dfs_connected_component(self):
        self.net.add_friendship(self.alice, self.bob)
        self.net.add_friendship(self.bob, self.carol)
        component = self.net.dfs_connected_component(self.alice)
        self.assertEqual(component, {self.alice, self.bob, self.carol})


class TestPostsAndTimeline(unittest.TestCase):
    def setUp(self):
        self.net = SocialNetwork()
        self.alice = self.net.add_user("alice")
        self.bob = self.net.add_user("bob")
        self.net.add_friendship(self.alice, self.bob)

    def test_create_post_and_like(self):
        pid = self.net.create_post(self.bob, "hello world")
        self.net.like_post(pid)
        self.assertEqual(self.net.posts[pid].likes, 1)

    def test_like_unknown_post_raises(self):
        with self.assertRaises(KeyError):
            self.net.like_post("p_ghost")

    def test_post_by_unknown_author_raises(self):
        with self.assertRaises(KeyError):
            self.net.create_post("u_ghost", "hi")

    def test_timeline_includes_friend_posts(self):
        pid = self.net.create_post(self.bob, "hi from bob")
        timeline = self.net.get_timeline(self.alice)
        self.assertTrue(any(p.post_id == pid for p in timeline))

    def test_timeline_empty_for_new_isolated_user(self):
        carol = self.net.add_user("carol")
        self.assertEqual(self.net.get_timeline(carol), [])

    def test_trending_respects_k_larger_than_available(self):
        self.net.create_post(self.bob, "only post")
        trending = self.net.get_trending_posts(k=10)
        self.assertEqual(len(trending), 1)


class TestModerationAndSearch(unittest.TestCase):
    def setUp(self):
        self.net = SocialNetwork()
        self.alice = self.net.add_user("alice")
        self.pid = self.net.create_post(self.alice, "spammy content")

    def test_flag_and_review_removes_content(self):
        self.net.flag_post(self.pid, "spam")
        action = self.net.review_next_flagged(remove=True)
        self.assertEqual(action.action, "remove")
        self.assertEqual(self.net.posts[self.pid].content, "[removed by moderator]")

    def test_review_with_empty_queue_returns_none(self):
        self.assertIsNone(self.net.review_next_flagged(remove=True))

    def test_undo_restores_previous_content(self):
        original = self.net.posts[self.pid].content
        self.net.flag_post(self.pid, "spam")
        self.net.review_next_flagged(remove=True)
        self.net.undo_last_moderation()
        self.assertEqual(self.net.posts[self.pid].content, original)

    def test_undo_with_empty_audit_log_returns_none(self):
        self.assertIsNone(self.net.undo_last_moderation())

    def test_search_users_by_prefix(self):
        self.net.add_user("alicia")
        results = self.net.search_users_by_prefix("ali")
        usernames = {u.username for u in results}
        self.assertEqual(usernames, {"alice", "alicia"})

    def test_search_prefix_no_match(self):
        self.assertEqual(self.net.search_users_by_prefix("zzz"), [])


class TestSortingAndSearching(unittest.TestCase):
    def test_merge_sort_ascending(self):
        data = [5, 3, 8, 1, 9, 2]
        self.assertEqual(merge_sort(data), [1, 2, 3, 5, 8, 9])

    def test_merge_sort_descending(self):
        data = [5, 3, 8, 1, 9, 2]
        self.assertEqual(merge_sort(data, reverse=True), [9, 8, 5, 3, 2, 1])

    def test_merge_sort_empty_and_single(self):
        self.assertEqual(merge_sort([]), [])
        self.assertEqual(merge_sort([42]), [42])

    def test_binary_search_found_and_not_found(self):
        data = [1, 3, 5, 7, 9]
        self.assertEqual(binary_search_by_key(data, 7), 3)
        self.assertIsNone(binary_search_by_key(data, 4))

    def test_trie_prefix_search_directly(self):
        trie = Trie()
        trie.insert("bob", "u1")
        trie.insert("bobby", "u2")
        results = trie.search_prefix("bob")
        matched_ids = {uid for _prefix, uid in results}
        self.assertEqual(matched_ids, {"u1", "u2"})


if __name__ == "__main__":
    unittest.main()
