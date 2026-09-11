"""Pluggable policy contract; only action/response history is visible."""
from typing import Protocol


class Policy(Protocol):
    def choose(self, public_history):
        """Return (path, position_or_None, channel_or_None)."""
        ...


def run(policy, client, max_actions=1000):
    for _ in range(max_actions):
        path, position, channel = policy.choose(client.actor_input())
        status, body = client.act(path, position, channel)
        if status != 200 or not body['accepted'] or path == '/exit':
            return client.history()
    return client.history()  # action cap is an external truncation, not success.
