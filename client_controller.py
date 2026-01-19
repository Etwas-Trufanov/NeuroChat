"""
Client controller (MVC) — simple launcher that composes model + view.
Currently it creates `ChatModel` and `ChatView` and wires them minimally.
Extend controller callbacks to forward events between view and model.
"""
from client_model import ChatModel
from client_view import ChatView
import tkinter as tk

class ChatController:
    def __init__(self):
        self.model = ChatModel()
        self.view = ChatView()

        # Wire model to view and preserve view handlers by wrapping them
        try:
            # Let the view register its callbacks first
            self.view.set_model(self.model)
            # Keep references to view-registered handlers (if any)
            view_on_receive = getattr(self.model, 'on_receive', None)
            view_on_users = getattr(self.model, 'on_users', None)
            view_on_history = getattr(self.model, 'on_history', None)

            # Define wrappers that call the view handler first, then controller handler
            def wrapped_on_receive(msg):
                try:
                    if view_on_receive:
                        view_on_receive(msg)
                except Exception:
                    pass
                try:
                    self._on_model_receive(msg)
                except Exception:
                    pass

            def wrapped_on_users(users):
                try:
                    if view_on_users:
                        view_on_users(users)
                except Exception:
                    pass
                try:
                    self._on_model_users(users)
                except Exception:
                    pass

            def wrapped_on_history(other_user, messages):
                try:
                    if view_on_history:
                        view_on_history(other_user, messages)
                except Exception:
                    pass
                try:
                    self._on_model_history(other_user, messages)
                except Exception:
                    pass

            # Install the wrapped handlers on the model
            self.model.on_receive = wrapped_on_receive
            self.model.on_users = wrapped_on_users
            self.model.on_history = wrapped_on_history
        except Exception:
            # Fallback: ensure controller handlers are present
            try:
                self.model.on_receive = self._on_model_receive
                self.model.on_users = self._on_model_users
                self.model.on_history = self._on_model_history
            except Exception:
                pass

    def run(self):
        # Expose a login handler so UI delegates login to model
        try:
            def external_login(username, password):
                resp = self.model.login(username, password)
                if resp.get('status') == 'success':
                    # update UI state
                    try:
                        self.view.ui.username = username
                        with self.view.ui.users_lock:
                            self.view.ui.all_users = self.model.all_users
                    except Exception:
                        pass
                    # show chat screen
                    try:
                        self.view.ui.create_chat_screen()
                    except Exception:
                        pass
                    # Request chat history for known users (helps restore chats after reconnect)
                    try:
                        # avoid spamming large lists; request for users except self
                        for u in list(self.model.all_users):
                            if u and u != username:
                                try:
                                    self.model.send_to_server({"action": "get_chat_history", "other_user": u})
                                except Exception:
                                    pass
                    except Exception:
                        pass
                else:
                    # show error via messagebox in UI thread
                    try:
                        import tkinter.messagebox as mb
                        mb.showerror("Ошибка", resp.get('message', ''))
                    except Exception:
                        pass
                return resp

            self.view.ui.external_login_handler = external_login
        except Exception:
            pass

        # Run UI mainloop
        self.view.mainloop()

    # Model -> Controller handlers
    def _on_model_receive(self, msg):
        # Called when model receives a new message
        # TODO: update view accordingly (display, notifications)
        pass

    def _on_model_users(self, users):
        # Called when model receives new users list
        pass

    def _on_model_history(self, other_user, messages):
        # Called when model receives chat history
        pass

if __name__ == '__main__':
    c = ChatController()
    c.run()
