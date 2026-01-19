"""
Client model (MVC) — stores app state and handles networking.
This is a lightweight scaffold extracted from the monolithic client.
Extend `ChatModel` with networking and persistence as needed.
"""
import threading
import socket
import json
from queue import Queue, Empty
from datetime import datetime

class ChatModel:
    def __init__(self):
        # Public state
        self.username = None
        self.server_host = None
        self.server_port = None
        self.chats = {}  # {user: [messages]}
        self.all_users = []
        self.unread = set()

        # Networking
        self.server_socket = None
        self.send_queue = Queue()
        self.running = False

        # Callbacks (set by controller)
        self.on_receive = None    # called with message dict
        self.on_users = None      # called with users list
        self.on_history = None    # called with (other_user, messages)

    # --- Networking helpers (simple scaffolding) ---
    def send_to_server(self, message):
        """Place message into outgoing queue. Sender thread should send."""
        self.send_queue.put(message)

    def start(self):
        self.running = True
        # start sender and receiver threads
        self._sender_thread = threading.Thread(target=self._sender_worker, daemon=True)
        self._sender_thread.start()
        self._receiver_thread = threading.Thread(target=self._receiver_worker, daemon=True)
        self._receiver_thread.start()

    def stop(self):
        self.running = False
        try:
            if self.server_socket:
                self.server_socket.close()
        except Exception:
            pass

    def _sender_worker(self):
        while self.running:
            try:
                msg = self.send_queue.get(timeout=1)
                if self.server_socket:
                    try:
                        self.server_socket.sendall(json.dumps(msg).encode())
                    except Exception:
                        # ignore send errors for now
                        pass
            except Empty:
                continue

    def _receiver_worker(self):
        import time
        while self.running:
            try:
                if not self.server_socket:
                    time.sleep(0.2)
                    continue
                data = self.server_socket.recv(4096).decode()
                if not data:
                    # connection closed
                    self.running = False
                    break
                msg = json.loads(data)
                action = msg.get('action')
                if action == 'receive_message':
                    sender = msg.get('sender')
                    text = msg.get('text')
                    ts = msg.get('timestamp')
                    m = {'sender': sender, 'text': text, 'timestamp': ts}
                    if sender not in self.chats:
                        self.chats[sender] = []
                    self.chats[sender].append(m)
                    if self.on_receive:
                        self.on_receive(m)
                elif action == 'chat_history':
                    other = msg.get('other_user')
                    hist = msg.get('messages', [])
                    self.chats[other] = hist
                    if self.on_history:
                        self.on_history(other, hist)
                elif action == 'users_list' or action == 'users':
                    users = msg.get('users', [])
                    self.all_users = users
                    if self.on_users:
                        self.on_users(users)
            except Exception:
                time.sleep(0.2)
                continue

    # --- High level actions ---
    def find_server(self):
        try:
            discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            discovery_socket.settimeout(5)
            discovery_socket.sendto(b"DISCOVER_SERVER", ('<broadcast>', 12345))
            response, addr = discovery_socket.recvfrom(1024)
            data = json.loads(response.decode())
            self.server_host = data.get('server_ip')
            self.server_port = data.get('server_port')
            discovery_socket.close()
            return True
        except Exception:
            return False

    def connect_to_server(self):
        try:
            if not self.server_host or not self.server_port:
                if not self.find_server():
                    return False
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.connect((self.server_host, self.server_port))
            return True
        except Exception:
            return False

    def login(self, username, password):
        # Connect and perform login; returns response dict
        if not self.connect_to_server():
            return {'status': 'error', 'message': 'server not found'}
        try:
            self.server_socket.sendall(json.dumps({
                'action': 'login', 'username': username, 'password': password
            }).encode())
            resp = self.server_socket.recv(4096).decode()
            data = json.loads(resp)
            if data.get('status') == 'success':
                self.username = username
                # request users
                self.server_socket.sendall(json.dumps({'action': 'get_users'}).encode())
                users_resp = self.server_socket.recv(4096).decode()
                users_data = json.loads(users_resp)
                self.all_users = users_data.get('users', [])
                # start sender/receiver threads
                self.start()
            return data
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

# End of client_model.py
