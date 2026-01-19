"""
Client view (MVC) — thin wrapper around the existing ChatClient UI.
This file provides a `ChatView` class that instantiates the UI from `client.py`
and exposes a small API to the controller.
"""
from client import ChatClient as _RawChatClient
import tkinter as tk

class ChatView:
    def __init__(self, root=None):
        self._own_root = False
        if root is None:
            root = tk.Tk()
            self._own_root = True
        self.root = root
        # instantiate the existing ChatClient UI (keeps current behaviour)
        self.ui = _RawChatClient(self.root)

    def mainloop(self):
        if self._own_root:
            self.root.mainloop()

    # Convenience proxies (extend as needed)
    def set_title(self, text):
        self.root.title(text)

    def destroy(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def set_model(self, model):
        """Wire a ChatModel to the existing UI instance.
        This replaces the UI's send method to use model.send_to_server
        and registers model callbacks to update the UI state."""
        self.model = model

        # Replace UI send_to_server with model's implementation
        try:
            self.ui.send_to_server = self.model.send_to_server
        except Exception:
            pass

        # Register callbacks
        def on_receive(m):
            # m: {sender,text,timestamp}
            sender = m.get('sender')
            # append to ui.chats
            try:
                with self.ui.chats_lock:
                    if sender not in self.ui.chats:
                        self.ui.chats[sender] = []
                    # simple dedupe: skip if identical to last message
                    last = self.ui.chats[sender][-1] if self.ui.chats[sender] else None
                    if not last or not (last.get('sender') == m.get('sender') and last.get('text') == m.get('text') and last.get('timestamp') == m.get('timestamp')):
                        self.ui.chats[sender].append(m)
            except Exception:
                pass
            # mark unread unless current chat
            try:
                if self.ui.current_chat != sender:
                    # model may track unread separately
                    try:
                        self.model.unread.add(sender)
                    except Exception:
                        pass
                # trigger UI update
                self.ui.event_queue.put(("update_chats_list", None))
                if self.ui.current_chat == sender:
                    self.ui.event_queue.put(("display_chat", None))
            except Exception:
                pass

        def on_users(users):
            try:
                with self.ui.users_lock:
                    self.ui.all_users = users
            except Exception:
                pass

        def on_history(other, messages):
            try:
                with self.ui.chats_lock:
                    self.ui.chats[other] = messages
                if self.ui.current_chat == other:
                    self.ui.event_queue.put(("display_chat", None))
            except Exception:
                pass

        self.model.on_receive = on_receive
        self.model.on_users = on_users
        self.model.on_history = on_history

# End of client_view.py
