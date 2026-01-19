import tkinter as tk
from tkinter import messagebox, scrolledtext
import socket
import threading
import json
from datetime import datetime
from queue import Queue, Empty

class ChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title("NeuroChat - Мессенджер")
        self.root.geometry("900x600")
        
        self.server_socket = None
        self.username = None
        self.server_host = None
        self.server_port = None
        self.current_chat = None
        
        self.chats = {}
        self.chats_lock = threading.Lock()
        self.all_users = []
        self.users_lock = threading.Lock()
        
        self.event_queue = Queue()
        
        self.receive_thread = None
        self.send_thread = None
        self.ui_update_thread = None
        self.running = True
        
        self.send_queue = Queue()
        self.socket_lock = threading.Lock()  # Блокировка для синхронного доступа к сокету
        
        self.create_login_screen()
        self.start_ui_update_thread()
    
    def start_ui_update_thread(self):
        self.ui_update_thread = threading.Thread(target=self.process_events, daemon=True)
        self.ui_update_thread.start()
    
    def process_events(self):
        while self.running:
            try:
                event_type, data = self.event_queue.get(timeout=0.1)
                if event_type == "update_chats_list":
                    self.update_chats_listbox()
                elif event_type == "display_chat":
                    self.display_current_chat()
            except Empty:
                pass
    
    def find_server(self):
        try:
            discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            discovery_socket.settimeout(10)
            print("[CLIENT] Ищу сервер...")
            discovery_socket.sendto(b"DISCOVER_SERVER", ('<broadcast>', 12345))
            response, addr = discovery_socket.recvfrom(1024)
            data = json.loads(response.decode())
            self.server_host = data['server_ip']
            self.server_port = data['server_port']
            discovery_socket.close()
            return True
        except:
            return False
    
    def connect_to_server(self):
        try:
            if not self.server_host or not self.server_port:
                if not self.find_server():
                    messagebox.showerror("Ошибка", "Сервер не найден!")
                    return False
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.connect((self.server_host, self.server_port))
            return True
        except Exception as e:
            messagebox.showerror("Ошибка подключения", str(e))
            return False
    
    def send_to_server(self, message):
        print(f"[SEND_TO_QUEUE] Добавляю в очередь: {message}")
        self.send_queue.put(message)
        print(f"[SEND_TO_QUEUE] Размер очереди: {self.send_queue.qsize()}")
    
    def sender_thread_worker(self):
        print("[SENDER_THREAD] Поток отправки запущен")
        while self.running and self.server_socket:
            try:
                message = self.send_queue.get(timeout=1)
                print(f"[SENDER_THREAD] Получил из очереди: {message}")
                try:
                    self.server_socket.send(json.dumps(message).encode())
                    print(f"[SENDER_THREAD] Успешно отправлено: {message}")
                except Exception as e:
                    print(f"[SENDER_THREAD] Ошибка отправки: {e}")
            except Empty:
                pass
        print("[SENDER_THREAD] Поток отправки завершен")
    
    def create_login_screen(self):
        self.clear_window()
        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack(expand=True)
        tk.Label(frame, text="NeuroChat", font=("Arial", 24, "bold")).pack(pady=20)
        tk.Label(frame, text="Имя:").pack(anchor=tk.W)
        username_entry = tk.Entry(frame, width=30)
        username_entry.pack(pady=5)
        tk.Label(frame, text="Пароль:").pack(anchor=tk.W)
        password_entry = tk.Entry(frame, width=30, show="*")
        password_entry.pack(pady=5)
        
        def perform_login(username, password):
            if not username or not password:
                messagebox.showwarning("Внимание", "Заполните все поля!")
                return
            if not self.connect_to_server():
                return
            try:
                print(f"[LOGIN] Отправляю login для {username}")
                with self.socket_lock:
                    self.server_socket.send(json.dumps({
                        "action": "login",
                        "username": username,
                        "password": password
                    }).encode())
                    response = self.server_socket.recv(1024).decode()
                print(f"[LOGIN] Получен response: {response}")
                data = json.loads(response)
                if data.get("status") == "success":
                    self.username = username
                    print(f"[LOGIN] Логин успешен, запрашиваю список пользователей")
                    
                    with self.socket_lock:
                        self.server_socket.send(json.dumps({"action": "get_users"}).encode())
                        print(f"[LOGIN] Отправлен get_users запрос, жду ответ...")
                        users_resp = self.server_socket.recv(1024).decode()
                    print(f"[LOGIN] Получен users response: {users_resp}")
                    
                    with self.users_lock:
                        self.all_users = json.loads(users_resp).get("users", [])
                    
                    print(f"[LOGIN] Загруженные пользователи: {self.all_users}")
                    self.create_chat_screen()
                    self.start_receive_thread()
                    self.start_sender_thread()
                else:
                    messagebox.showerror("Ошибка", data.get("message", ""))
                    self.server_socket.close()
                    self.server_socket = None
            except Exception as e:
                print(f"[LOGIN] Ошибка: {e}")
                import traceback
                traceback.print_exc()
                messagebox.showerror("Ошибка", str(e))
        
        def login():
            perform_login(username_entry.get(), password_entry.get())
        
        def register():
            username = username_entry.get()
            password = password_entry.get()
            if not username or not password:
                messagebox.showwarning("Внимание", "Заполните все поля!")
                return
            if not self.connect_to_server():
                return
            try:
                self.server_socket.send(json.dumps({
                    "action": "register",
                    "username": username,
                    "password": password
                }).encode())
                response = self.server_socket.recv(1024).decode()
                data = json.loads(response)
                if data.get("status") == "success":
                    messagebox.showinfo("Успех", "Регистрация успешна!")
                    self.server_socket.close()
                    self.server_socket = None
                    perform_login(username, password)
                else:
                    messagebox.showerror("Ошибка", data.get("message", ""))
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))
        
        button_frame = tk.Frame(frame)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="Вход", command=login, width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Регистрация", command=register, width=15).pack(side=tk.LEFT, padx=5)
    
    def create_chat_screen(self):
        self.clear_window()
        
        # МЕНЮ
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Выход", command=self.logout)
        
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        left_frame = tk.Frame(main_frame, width=250, bg="#f0f0f0")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=5, pady=5)
        left_frame.pack_propagate(False)
        
        tk.Label(left_frame, text="Чаты", font=("Arial", 14, "bold"), bg="#f0f0f0").pack(pady=10)
        tk.Button(left_frame, text="+ Новый", command=self.add_new_chat, width=20, bg="#4CAF50", fg="white").pack(pady=5)
        
        self.chats_listbox = tk.Listbox(left_frame, height=30, width=30)
        self.chats_listbox.pack(pady=5, padx=5, fill=tk.BOTH, expand=True)
        self.chats_listbox.bind('<<ListboxSelect>>', self.on_chat_selected)
        
        right_frame = tk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.chat_header = tk.Label(right_frame, text="Выберите чат", font=("Arial", 12, "bold"))
        self.chat_header.pack(pady=10)
        
        self.chat_display = scrolledtext.ScrolledText(right_frame, height=20, width=60, state=tk.DISABLED)
        self.chat_display.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        
        input_frame = tk.Frame(right_frame)
        input_frame.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        
        tk.Label(input_frame, text="Сообщение:").pack(anchor=tk.W)
        
        # Многострочное поле ввода
        self.message_entry = scrolledtext.ScrolledText(input_frame, height=4, width=60, wrap=tk.WORD)
        self.message_entry.pack(side=tk.LEFT, pady=5, padx=(0, 5), fill=tk.BOTH, expand=True)
        
        # Кнопка отправить справа
        send_btn = tk.Button(input_frame, text="Отправить", command=self.send_message, width=10, bg="#2196F3", fg="white")
        send_btn.pack(side=tk.LEFT, padx=5)
        
        # Bind Enter и Shift+Enter
        self.message_entry.bind('<Return>', self.on_message_key)
    
    def on_message_key(self, event):
        """Обработка Enter/Shift+Enter в поле ввода"""
        if event.state & 0x1:  # Shift нажат
            # Разрешаем новую строку
            return "break"  # Не обрабатывать дальше, но вставить символ
        else:
            # Enter без Shift - отправить
            self.send_message()
            return "break"  # Отменить стандартное поведение Enter
    
    def add_new_chat(self):
        # Запрашиваем свежий список пользователей синхронно перед открытием диалога
        try:
            print("[ADD_CHAT] Запрашиваю обновленный список пользователей")
            with self.socket_lock:
                self.server_socket.send(json.dumps({"action": "get_users"}).encode())
                users_resp = self.server_socket.recv(1024).decode()
            print(f"[ADD_CHAT] Получен обновленный список: {users_resp}")
            with self.users_lock:
                self.all_users = json.loads(users_resp).get("users", [])
        except Exception as e:
            print(f"[ADD_CHAT] Ошибка при запросе списка: {e}")
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Новый чат")
        dialog.geometry("300x120")
        dialog.transient(self.root)
        
        tk.Label(dialog, text="Выберите пользователя:").pack(pady=10)
        
        choice_var = tk.StringVar(dialog)
        with self.users_lock:
            candidates = [u for u in self.all_users if u != self.username]
        
        if not candidates:
            tk.Label(dialog, text="Нет пользователей").pack()
            tk.Button(dialog, text="Закрыть", command=dialog.destroy).pack()
            return
        
        choice_var.set(candidates[0])
        menu = tk.OptionMenu(dialog, choice_var, *sorted(candidates))
        menu.config(width=28)
        menu.pack(pady=5)
        
        def add_chat():
            recipient = choice_var.get()
            if not recipient:
                return
            dialog.destroy()
            with self.chats_lock:
                if recipient not in self.chats:
                    self.chats[recipient] = []
                self.current_chat = recipient
            self.update_chats_listbox()
            self.display_current_chat()
            self.send_to_server({"action": "get_chat_history", "other_user": recipient})
        
        tk.Button(dialog, text="Добавить", command=add_chat, width=15).pack(pady=10)
    
    def on_chat_selected(self, event):
        selection = self.chats_listbox.curselection()
        if selection:
            self.current_chat = self.chats_listbox.get(selection[0])
            self.chat_header.config(text=f"Чат с {self.current_chat}")
            self.display_current_chat()
            self.send_to_server({"action": "get_chat_history", "other_user": self.current_chat})
    
    def display_current_chat(self):
        if not self.current_chat:
            return
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)
        with self.chats_lock:
            messages = self.chats.get(self.current_chat, [])
            for msg in messages:
                sender = msg.get("sender")
                text = msg.get("text")
                ts = msg.get("timestamp")
                prefix = "Вы" if sender == self.username else sender
                self.chat_display.insert(tk.END, f"[{ts}] {prefix}: {text}\n")
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)
    
    def send_message(self):
        if not self.current_chat:
            messagebox.showwarning("Внимание", "Выберите чат!")
            return
        text = self.message_entry.get("1.0", tk.END).strip()
        if not text:
            return
        self.send_to_server({"action": "send_message", "recipient": self.current_chat, "text": text})
        msg = {"sender": self.username, "text": text, "timestamp": datetime.now().strftime("%H:%M:%S")}
        with self.chats_lock:
            if self.current_chat not in self.chats:
                self.chats[self.current_chat] = []
            self.chats[self.current_chat].append(msg)
        self.display_current_chat()
        self.message_entry.delete("1.0", tk.END)
    
    def update_chats_listbox(self):
        self.chats_listbox.delete(0, tk.END)
        with self.chats_lock:
            for user in sorted(self.chats.keys()):
                self.chats_listbox.insert(tk.END, user)
    
    def start_receive_thread(self):
        self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        self.receive_thread.start()
    
    def start_sender_thread(self):
        self.send_thread = threading.Thread(target=self.sender_thread_worker, daemon=True)
        self.send_thread.start()
    
    def receive_messages(self):
        while self.running and self.server_socket:
            try:
                # БЕЗ блокировки - recv() сам по себе атомарный на уровне ОС
                data = self.server_socket.recv(1024).decode()
                if not data:
                    break
                msg = json.loads(data)
                
                if msg.get("action") == "receive_message":
                    sender = msg.get("sender")
                    text = msg.get("text")
                    ts = msg.get("timestamp")
                    msg_data = {"sender": sender, "text": text, "timestamp": ts}
                    with self.chats_lock:
                        if sender not in self.chats:
                            self.chats[sender] = []
                        self.chats[sender].append(msg_data)
                    self.event_queue.put(("update_chats_list", None))
                    if self.current_chat == sender:
                        self.event_queue.put(("display_chat", None))
                
                elif msg.get("action") == "chat_history":
                    other = msg.get("other_user")
                    hist = msg.get("messages", [])
                    with self.chats_lock:
                        self.chats[other] = hist
                        if self.current_chat == other:
                            self.event_queue.put(("display_chat", None))
            except Exception as e:
                if self.running:
                    print(f"[RECEIVE] {e}")
                break
    
    def logout(self):
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        self.username = None
        self.server_socket = None
        self.current_chat = None
        self.chats = {}
        self.all_users = []
        self.create_login_screen()
    
    def clear_window(self):
        for w in self.root.winfo_children():
            w.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatClient(root)
    root.mainloop()
