"""
cli.py
Menu-driven command-line demo for the Social-Network-Lite system.
Run with:  python cli.py
"""

from core import SocialNetwork


def seed_demo_data(net: SocialNetwork) -> dict:
    """Creates a small demo network so the menu has something to show immediately."""
    ids = {}
    for name in ["alice", "bob", "carol", "dave", "erin", "frank"]:
        ids[name] = net.add_user(name)

    net.add_friendship(ids["alice"], ids["bob"])
    net.add_friendship(ids["alice"], ids["carol"])
    net.add_friendship(ids["bob"], ids["dave"])
    net.add_friendship(ids["carol"], ids["dave"])
    net.add_friendship(ids["dave"], ids["erin"])

    p1 = net.create_post(ids["bob"], "Just shipped my DSA project!")
    p2 = net.create_post(ids["carol"], "Studying graphs all night.")
    p3 = net.create_post(ids["alice"], "Coffee first, code later.")
    for _ in range(5):
        net.like_post(p1)
    for _ in range(2):
        net.like_post(p2)
    net.flag_post(p3, reason="spam report")

    return ids


def print_menu():
    print("\n=== Social-Network-Lite ===")
    print(" 1. Add user")
    print(" 2. Add friendship")
    print(" 3. Suggest mutual friends (BFS)")
    print(" 4. Show friend network (DFS component)")
    print(" 5. Create post")
    print(" 6. Like post")
    print(" 7. View timeline (merge-sorted, cached)")
    print(" 8. View trending posts (heap top-k)")
    print(" 9. Search users by prefix (trie)")
    print("10. Review next flagged post (queue)")
    print("11. Undo last moderation action (stack)")
    print(" 0. Exit")


def main():
    net = SocialNetwork()
    ids = seed_demo_data(net)
    print("Demo data loaded: alice, bob, carol, dave, erin, frank")
    print("(alice-bob, alice-carol, bob-dave, carol-dave, dave-erin are friends)")

    while True:
        print_menu()
        choice = input("Choose an option: ").strip()

        if choice == "1":
            name = input("Username: ").strip()
            uid = net.add_user(name)
            print(f"Created user {name} with id {uid}")

        elif choice == "2":
            a = input("User A id: ").strip()
            b = input("User B id: ").strip()
            try:
                net.add_friendship(a, b)
                print("Friendship added.")
            except (KeyError, ValueError) as e:
                print(f"Error: {e}")

        elif choice == "3":
            uid = input("User id: ").strip()
            suggestions = net.bfs_mutual_friend_suggestions(uid)
            if not suggestions:
                print("No suggestions found.")
            for candidate_id, mutual_count in suggestions:
                uname = net.users[candidate_id].username
                print(f"  {uname} ({candidate_id}) - {mutual_count} mutual friend(s)")

        elif choice == "4":
            uid = input("User id: ").strip()
            component = net.dfs_connected_component(uid)
            names = [net.users[u].username for u in component if u in net.users]
            print(f"Connected network ({len(names)} people): {', '.join(names)}")

        elif choice == "5":
            uid = input("Author user id: ").strip()
            content = input("Post content: ").strip()
            try:
                pid = net.create_post(uid, content)
                print(f"Created post {pid}")
            except KeyError as e:
                print(f"Error: {e}")

        elif choice == "6":
            pid = input("Post id: ").strip()
            try:
                net.like_post(pid)
                print("Liked.")
            except KeyError as e:
                print(f"Error: {e}")

        elif choice == "7":
            uid = input("User id: ").strip()
            timeline = net.get_timeline(uid)
            if not timeline:
                print("Timeline is empty.")
            for post in timeline:
                author = net.users[post.author_id].username
                print(f"  [{post.post_id}] {author}: {post.content} (likes={post.likes})")

        elif choice == "8":
            trending = net.get_trending_posts(k=5)
            for post in trending:
                author = net.users[post.author_id].username
                print(f"  [{post.post_id}] {author}: {post.content} (likes={post.likes})")

        elif choice == "9":
            prefix = input("Search prefix: ").strip()
            results = net.search_users_by_prefix(prefix)
            if not results:
                print("No matches.")
            for user in results:
                print(f"  {user.username} ({user.user_id})")

        elif choice == "10":
            remove_input = input("Remove content? (y/n): ").strip().lower()
            action = net.review_next_flagged(remove=(remove_input == "y"))
            if action is None:
                print("No flagged posts in queue.")
            else:
                print(f"Reviewed post {action.post_id}: action={action.action}")

        elif choice == "11":
            action = net.undo_last_moderation()
            if action is None:
                print("Nothing to undo.")
            else:
                print(f"Undid action '{action.action}' on post {action.post_id}")

        elif choice == "0":
            print("Goodbye.")
            break

        else:
            print("Invalid option, try again.")


if __name__ == "__main__":
    main()
