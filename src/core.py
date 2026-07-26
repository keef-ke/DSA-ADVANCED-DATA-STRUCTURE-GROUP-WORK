"""
core.py
Simplified Social Network (Facebook-lite) - Chapter 23 aligned mini-system.

Combines variants A1-A5 into one coherent system:
  A1 - Friends graph + mutual-friends recommendation      -> Graph + hash counts
  A2 - Timeline feed generation (push model) + caching    -> merge sort + cache dict
  A3 - Post ranking (top-k recent + likes)                -> heap / priority queue
  A4 - Content moderation queue + audit log                -> queue + stack
  A5 - Scalable friend search / autocomplete                -> trie

Mandatory DSA coverage (Section 3 of the brief):
  - Hash table / map      -> users, username_to_id, posts, like counts
  - Stack                 -> audit_log (moderation undo)
  - Queue                 -> moderation_queue (FIFO review pipeline)
  - Heap / priority queue  -> trending posts top-k
  - Graph (BFS/DFS)       -> friendship graph, mutual-friend suggestions, connectivity
  - Sorting + searching    -> merge_sort (O(n log n)) + binary_search (O(log n))
  - Complexity analysis    -> documented per method below, benchmarked in benchmark.py
"""

from __future__ import annotations

import heapq
import itertools
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


# --------------------------------------------------------------------------
# Domain models
# --------------------------------------------------------------------------

@dataclass
class User:
    user_id: str
    username: str
    created_at: float = field(default_factory=time.time)


@dataclass
class Post:
    post_id: str
    author_id: str
    content: str
    created_at: float = field(default_factory=time.time)
    likes: int = 0
    flagged: bool = False


@dataclass
class ModerationAction:
    """A record pushed onto the audit stack so it can be undone (LIFO)."""
    action: str          # "flag" | "remove" | "restore"
    post_id: str
    previous_state: dict


# --------------------------------------------------------------------------
# Trie - used for O(prefix_length + matches) username autocomplete (A5)
# --------------------------------------------------------------------------

class _TrieNode:
    __slots__ = ("children", "is_end", "user_ids")

    def __init__(self):
        self.children: Dict[str, "_TrieNode"] = {}
        self.is_end: bool = False
        self.user_ids: Set[str] = set()


class Trie:
    """Prefix tree over usernames for scalable autocomplete/search.

    Complexity:
      insert(word)         O(L)      L = len(word)
      search_prefix(pref)  O(P + M)  P = len(prefix), M = number of matches returned
    """

    def __init__(self):
        self.root = _TrieNode()

    def insert(self, username: str, user_id: str) -> None:
        node = self.root
        for ch in username.lower():
            node = node.children.setdefault(ch, _TrieNode())
        node.is_end = True
        node.user_ids.add(user_id)

    def _collect(self, node: _TrieNode, prefix: str, out: List[Tuple[str, str]]) -> None:
        if node.is_end:
            for uid in node.user_ids:
                out.append((prefix, uid))
        for ch, child in node.children.items():
            self._collect(child, prefix + ch, out)

    def search_prefix(self, prefix: str, limit: int = 10) -> List[Tuple[str, str]]:
        node = self.root
        prefix = prefix.lower()
        for ch in prefix:
            if ch not in node.children:
                return []
            node = node.children[ch]
        results: List[Tuple[str, str]] = []
        self._collect(node, prefix, results)
        return results[:limit]


# --------------------------------------------------------------------------
# Sorting + searching (implemented explicitly, per Section 3 requirement)
# --------------------------------------------------------------------------

def merge_sort(items: List, key=lambda x: x, reverse: bool = False) -> List:
    """Stable merge sort. O(n log n) time, O(n) space.

    Used for building a user's timeline (posts ordered by recency) and for
    producing a sorted-by-timestamp array that binary_search can then query.
    """
    if len(items) <= 1:
        return items[:]

    mid = len(items) // 2
    left = merge_sort(items[:mid], key, reverse)
    right = merge_sort(items[mid:], key, reverse)

    merged: List = []
    i = j = 0
    cmp = (lambda a, b: a > b) if reverse else (lambda a, b: a < b)
    while i < len(left) and j < len(right):
        if cmp(key(left[i]), key(right[j])) or key(left[i]) == key(right[j]):
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged


def binary_search_by_key(sorted_items: List, target_key, key=lambda x: x) -> Optional[int]:
    """Binary search over a list sorted ascending by `key`. O(log n).

    Returns the index of a matching element, or None if not found.
    Used to answer "does a post at/around timestamp T exist" style queries
    without a linear scan.
    """
    lo, hi = 0, len(sorted_items) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        val = key(sorted_items[mid])
        if val == target_key:
            return mid
        elif val < target_key:
            lo = mid + 1
        else:
            hi = mid - 1
    return None


# --------------------------------------------------------------------------
# Main facade: SocialNetwork
# --------------------------------------------------------------------------

class SocialNetwork:
    def __init__(self):
        # Hash tables (O(1) average lookup)
        self.users: Dict[str, User] = {}
        self.username_to_id: Dict[str, str] = {}
        self.posts: Dict[str, Post] = {}

        # Graph: adjacency list, undirected friendship edges
        self.graph: Dict[str, Set[str]] = {}

        # Trie for autocomplete / search (A5)
        self.trie = Trie()

        # Queue: FIFO moderation pipeline (A4)
        self.moderation_queue: deque = deque()

        # Stack: LIFO audit log, enables undo of the most recent moderation action (A4)
        self.audit_log: List[ModerationAction] = []

        # Simple push-model timeline cache: user_id -> cached sorted post list (A2)
        self._timeline_cache: Dict[str, List[Post]] = {}
        self._cache_dirty: Set[str] = set()

        self._id_counter = itertools.count(1)

    # ---------------- user & friend management ----------------

    def add_user(self, username: str) -> str:
        """O(1) average: hash-table insert + trie insert (O(L))."""
        user_id = f"u{next(self._id_counter)}"
        self.users[user_id] = User(user_id, username)
        self.username_to_id[username.lower()] = user_id
        self.graph[user_id] = set()
        self.trie.insert(username, user_id)
        return user_id

    def add_friendship(self, user_a: str, user_b: str) -> None:
        """O(1) average. Adds an undirected edge in the friendship graph."""
        if user_a == user_b:
            raise ValueError("A user cannot friend themselves.")
        if user_a not in self.users or user_b not in self.users:
            raise KeyError("Both users must exist.")
        self.graph[user_a].add(user_b)
        self.graph[user_b].add(user_a)
        self._cache_dirty.update({user_a, user_b})

    def remove_friendship(self, user_a: str, user_b: str) -> None:
        self.graph.get(user_a, set()).discard(user_b)
        self.graph.get(user_b, set()).discard(user_a)
        self._cache_dirty.update({user_a, user_b})

    def bfs_mutual_friend_suggestions(self, user_id: str, top_k: int = 5) -> List[Tuple[str, int]]:
        """A1: Suggest friends via BFS to depth 2 + hash-map mutual-friend counts.

        Complexity: O(V + E) for the BFS traversal of the local neighbourhood,
        plus O(M log k) to keep the top-k via a heap (M = candidates found).
        """
        if user_id not in self.graph:
            return []

        direct_friends = self.graph[user_id]
        mutual_counts: Dict[str, int] = {}

        visited = {user_id}
        queue = deque([(f, 1) for f in direct_friends])
        visited.update(direct_friends)

        while queue:
            node, depth = queue.popleft()
            if depth == 2 and node != user_id and node not in direct_friends:
                mutual_counts[node] = mutual_counts.get(node, 0) + 1
            if depth < 2:
                for neighbour in self.graph.get(node, ()):
                    if neighbour not in visited:
                        visited.add(neighbour)
                        queue.append((neighbour, depth + 1))
                    elif neighbour != user_id and neighbour not in direct_friends:
                        mutual_counts[neighbour] = mutual_counts.get(neighbour, 0) + 1

        # top-k by mutual-friend count using a heap: O(M log k)
        return heapq.nlargest(top_k, mutual_counts.items(), key=lambda kv: kv[1])

    def dfs_connected_component(self, user_id: str) -> Set[str]:
        """Returns the full connected friend-network reachable from user_id.
        O(V + E) via iterative DFS. Useful for reachability / "friend of friend chain" checks.
        """
        if user_id not in self.graph:
            return set()
        visited: Set[str] = set()
        stack = [user_id]
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            for neighbour in self.graph.get(node, ()):
                if neighbour not in visited:
                    stack.append(neighbour)
        return visited

    # ---------------- posts & timeline ----------------

    def create_post(self, author_id: str, content: str) -> str:
        """O(1) average hash insert. Invalidates the author's friends' timeline caches."""
        if author_id not in self.users:
            raise KeyError("Author does not exist.")
        post_id = f"p{next(self._id_counter)}"
        self.posts[post_id] = Post(post_id, author_id, content)
        for friend in self.graph.get(author_id, ()):
            self._cache_dirty.add(friend)
        self._cache_dirty.add(author_id)
        return post_id

    def like_post(self, post_id: str) -> None:
        """O(1) hash update."""
        if post_id not in self.posts:
            raise KeyError("Post does not exist.")
        self.posts[post_id].likes += 1

    def get_timeline(self, user_id: str, limit: int = 20) -> List[Post]:
        """A2: Push-model timeline: pre-aggregate posts of the user + friends,
        sorted newest-first with merge_sort, then cache the result.

        Complexity: O(F * P log(F * P)) on a cache miss (F friends, P posts/friend average);
        O(1) amortised on a cache hit (until invalidated by a new post/friendship).
        """
        if user_id in self._timeline_cache and user_id not in self._cache_dirty:
            return self._timeline_cache[user_id][:limit]

        contributor_ids = {user_id} | self.graph.get(user_id, set())
        candidate_posts = [p for p in self.posts.values() if p.author_id in contributor_ids]
        sorted_posts = merge_sort(candidate_posts, key=lambda p: p.created_at, reverse=True)

        self._timeline_cache[user_id] = sorted_posts
        self._cache_dirty.discard(user_id)
        return sorted_posts[:limit]

    def get_trending_posts(self, k: int = 5) -> List[Post]:
        """A3: Top-k trending posts ranked by a recency-weighted score,
        using a min-heap of size k (heapq.nlargest under the hood is O(n log k)).

        score = likes + recency_bonus, where recency_bonus favours newer posts.
        """
        now = time.time()

        def score(p: Post) -> float:
            age_hours = max((now - p.created_at) / 3600.0, 0.0)
            recency_bonus = max(0.0, 24 - age_hours) * 0.1
            return p.likes + recency_bonus

        return heapq.nlargest(k, self.posts.values(), key=score)

    # ---------------- moderation: queue + stack (A4) ----------------

    def flag_post(self, post_id: str, reason: str = "") -> None:
        """Enqueue a post for review. O(1). FIFO ensures oldest reports are handled first."""
        if post_id not in self.posts:
            raise KeyError("Post does not exist.")
        self.posts[post_id].flagged = True
        self.moderation_queue.append((post_id, reason))

    def review_next_flagged(self, remove: bool) -> Optional[ModerationAction]:
        """Dequeue and act on the oldest flagged post (FIFO). O(1).
        Pushes an audit record onto the stack so the action can be undone.
        """
        if not self.moderation_queue:
            return None
        post_id, reason = self.moderation_queue.popleft()
        post = self.posts.get(post_id)
        if post is None:
            return None

        previous_state = {"content": post.content, "flagged": post.flagged}
        if remove:
            post.content = "[removed by moderator]"
        post.flagged = False

        action = ModerationAction(
            action="remove" if remove else "clear_flag",
            post_id=post_id,
            previous_state=previous_state,
        )
        self.audit_log.append(action)
        return action

    def undo_last_moderation(self) -> Optional[ModerationAction]:
        """Pop the most recent audit record (LIFO) and restore prior state. O(1)."""
        if not self.audit_log:
            return None
        action = self.audit_log.pop()
        post = self.posts.get(action.post_id)
        if post is not None:
            post.content = action.previous_state["content"]
            post.flagged = action.previous_state["flagged"]
        return action

    # ---------------- search (A5) ----------------

    def search_users_by_prefix(self, prefix: str, limit: int = 10) -> List[User]:
        """O(P + M): trie prefix walk + collecting up to `limit` matches."""
        matches = self.trie.search_prefix(prefix, limit)
        return [self.users[uid] for _prefix, uid in matches if uid in self.users]
