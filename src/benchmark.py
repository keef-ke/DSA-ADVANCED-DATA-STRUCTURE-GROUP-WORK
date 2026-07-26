"""
benchmark.py
Measures wall-clock time of the required operations at increasing scale,
to support the complexity-analysis section of the design report.

Run with:  python benchmark.py
"""

import random
import string
import time

from core import SocialNetwork, merge_sort, binary_search_by_key


def random_username(n=8):
    return "".join(random.choices(string.ascii_lowercase, k=n))


def build_network(num_users: int, avg_friends: int, num_posts: int) -> SocialNetwork:
    net = SocialNetwork()
    ids = [net.add_user(f"{random_username()}{i}") for i in range(num_users)]

    for uid in ids:
        friends = random.sample(ids, min(avg_friends, num_users - 1))
        for f in friends:
            if f != uid:
                try:
                    net.add_friendship(uid, f)
                except ValueError:
                    pass

    for _ in range(num_posts):
        author = random.choice(ids)
        net.create_post(author, "benchmark post")

    return net, ids


def time_it(fn, *args, repeats: int = 1, **kwargs):
    start = time.perf_counter()
    for _ in range(repeats):
        fn(*args, **kwargs)
    elapsed = time.perf_counter() - start
    return elapsed / repeats


def run_benchmark(num_users: int, avg_friends: int, num_posts: int):
    net, ids = build_network(num_users, avg_friends, num_posts)
    sample_user = random.choice(ids)

    hash_lookup_time = time_it(lambda: net.users.get(sample_user), repeats=10000)
    bfs_time = time_it(net.bfs_mutual_friend_suggestions, sample_user, repeats=50)
    trending_time = time_it(net.get_trending_posts, 5, repeats=50)

    posts_list = list(net.posts.values())
    merge_sort_time = time_it(merge_sort, posts_list, key=lambda p: p.created_at, repeats=20)
    builtin_sort_time = time_it(
        lambda: sorted(posts_list, key=lambda p: p.created_at), repeats=20
    )

    timestamps = sorted(p.created_at for p in posts_list)
    target = timestamps[len(timestamps) // 2] if timestamps else 0
    binary_search_time = time_it(
        binary_search_by_key, timestamps, target, repeats=10000
    )
    linear_search_time = time_it(
        lambda: (target in timestamps), repeats=10000
    )

    print(f"\n--- users={num_users}, avg_friends={avg_friends}, posts={num_posts} ---")
    print(f"  hash lookup (user by id):      {hash_lookup_time * 1e6:8.3f} microseconds")
    print(f"  BFS mutual-friend suggestion:  {bfs_time * 1e6:8.3f} microseconds")
    print(f"  heap top-k trending (k=5):     {trending_time * 1e6:8.3f} microseconds")
    print(f"  merge_sort (custom, O(n log n)): {merge_sort_time * 1e6:8.3f} microseconds")
    print(f"  sorted()  (builtin, Timsort):    {builtin_sort_time * 1e6:8.3f} microseconds")
    print(f"  binary_search_by_key:           {binary_search_time * 1e6:8.3f} microseconds")
    print(f"  linear 'in' search:             {linear_search_time * 1e6:8.3f} microseconds")


if __name__ == "__main__":
    random.seed(42)
    for n in [500, 2000, 10000]:
        run_benchmark(num_users=n, avg_friends=15, num_posts=n // 2)
