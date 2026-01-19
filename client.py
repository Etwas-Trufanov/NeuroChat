import tkinter as tk
from tkinter import messagebox, scrolledtext
import socket
import threading
import json
from datetime import datetime

class ChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title("NeuroChat - Мессенджер")
        self.root.geometry("900x600")
        
        self.server_socket = None
        self.username = None
        self.server_host = None
        self.server_port = None
        self.current_chat = None  # Текущий активный чат
        self.chats = {}  # {username: [messages]}
        self.chats_lock = threading.Lock()
        
        self.create_login_screen()
        
        self.receive_thread = None
        self.running = True
    
    def find_server(self):
        """Ищет сервер в локальной сети"""
        try:
            discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            discovery_socket.settimeout(10)
            
            print("[CLIENT] Отправляю запрос поиска сервера...")
            discovery_socket.sendto(b"DISCOVER_SERVER", ('<broadcast>', 12345))
            
            try:
                response, addr = discovery_socket.recvfrom(1024)
                print(f"[CLIENT] Получен ответ: {response.decode()} от {addr}")
                data = json.loads(response.decode())
                self.server_host = data['server_ip']
                self.server_port = data['server_port']
                print(f"[CLIENT] Найден сервер на {self.server_host}:{self.server_port}")
                discovery_socket.close()
                return True
            except socket.timeout:
                print("[CLIENT] Timeout при ожидании ответа")
                discovery_socket.close()
                return False
        except Exception as e:
            print(f"[CLIENT] Ошибка поиска: {e}")
            return False
    
    def connect_to_server(self):
        """Подключается к серверу"""
        try:
            if not self.server_host or not self.server_port:
                print("[CLIENT] Ищу сервер...")
                if not self.find_server():
                    messagebox.showerror("Ошибка", "Сервер не найден в сети!")
                    return False
            
            print(f"[CLIENT] Подключаюсь к {self.server_host}:{self.server_port}...")
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.connect((self.server_host, self.server_port))
            print("[CLIENT] Подключение успешно")
            return True
        except Exception as e:
            print(f"[CLIENT] Ошибка подключения: {e}")
            messagebox.showerror("Ошибка подключения", str(e))
            return False
    
    def send_to_server(self, message, wait_response=False):
        """Отправляет сообщение на сервер"""
        try:
            print(f"[CLIENT] Отправляю: {message}")
            self.server_socket.send(json.dumps(message).encode())
            if not wait_response:
                return None
            response = self.server_socket.recv(1024).decode()
            print(f"[CLIENT] Получен ответ: {response}")
            return response
        except Exception as e:
            print(f"[CLIENT] Ошибка отправки: {e}")
            messagebox.showerror("Ошибка", f"Ошибка отправки: {e}")
            return None
    
    def create_login_screen(self):
        """Создает экран входа/регистрации"""
        self.clear_window()
        
        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack(expand=True)
        
        tk.Label(frame, text="NeuroChat", font=("Arial", 24, "bold")).pack(pady=20)
        tk.Label(frame, text="Мессенджер", font=("Arial", 12)).pack(pady=(0, 20))
        
        tk.Label(frame, text="Имя пользователя:").pack(anchor=tk.W, pady=(10, 0))
        username_entry = tk.Entry(frame, width=30)
        username_entry.pack(pady=(0, 10))
        
        tk.Label(frame, text="Пароль:").pack(anchor=tk.W, pady=(10, 0))
        password_entry = tk.Entry(frame, width=30, show="*")
        password_entry.pack(pady=(0, 20))
        
        def perform_login(username, password):
            """Вспомогательная функция для входа"""
            if not username or not password:
                messagebox.showwarning("Внимание", "Заполните все поля!")
                return
            
            if not self.connect_to_server():
                return
            
            response = self.send_to_server({
                "action": "login",
                "username": username,
                "password": password
            }, wait_response=True)
            
            if response:
                data = json.loads(response)
                if data.get("status") == "success":
                    self.username = username
                    self.create_chat_screen()
                    self.start_receive_thread()
                    self.request_chats_list()
                else:
                    messagebox.showerror("Ошибка входа", data.get("message", "Неизвестная ошибка"))
        
        def login():
            username = username_entry.get()
            password = password_entry.get()
            perform_login(username, password)
        
        def register():
            username = username_entry.get()
            password = password_entry.get()
            
            if not username or not password:
                messagebox.showwarning("Внимание", "Заполните все поля!")
                return
            
            if not self.connect_to_server():
                return
            
            response = self.send_to_server({
                "action": "register",
                "username": username,
                "password": password
            }, wait_response=True)
            
            if response:
                data = json.loads(response)
                if data.get("status") == "success":
                    messagebox.showinfo("Успех", "Регистрация успешна! Входим в аккаунт...")
                    self.server_socket.close()
                    self.server_socket = None
                    perform_login(username, password)
                else:
                    messagebox.showerror("Ошибка регистрации", data.get("message", "Неизвестная ошибка"))
        
        button_frame = tk.Frame(frame)
        button_frame.pack(pady=10)
        
        tk.Button(button_frame, text="Вход", command=login, width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Регистрация", command=register, width=15).pack(side=tk.LEFT, padx=5)
    
    def create_chat_screen(self):
        """Создает экран чата с двумя панелями (Telegram-style)"""
        self.clear_window()
        
        # Основной контейнер
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ========== ЛЕВАЯ ПАНЕЛЬ (Список чатов) ==========
        left_frame = tk.Frame(main_frame, width=250, bg="#f0f0f0")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=5, pady=5)
        left_frame.pack_propagate(False)
        
        tk.Label(left_frame, text=f"Чаты", font=("Arial", 14, "bold"), bg="#f0f0f0").pack(pady=10)
        
        # Кнопка добавить новый чат
        tk.Button(left_frame, text="+ Новый чат", command=self.add_new_chat, 
                 width=25, bg="#4CAF50", fg="white").pack(pady=5, padx=5)
        
        # Список чатов
        self.chats_listbox = tk.Listbox(left_frame, height=30, width=30, font=("Arial", 10))
        self.chats_listbox.pack(pady=5, padx=5, fill=tk.BOTH, expand=True)
        self.chats_listbox.bind('<<ListboxSelect>>', self.on_chat_selected)
        
        # Кнопка выхода
        tk.Button(left_frame, text="Выход", command=self.logout, 
                 width=25, bg="#f44336", fg="white").pack(pady=5, padx=5)
        
        # ========== ПРАВАЯ ПАНЕЛЬ (Сообщения и ввод) ==========
        right_frame = tk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Заголовок с именем пользователя
        self.chat_header = tk.Label(right_frame, text="Выберите чат", 
                                    font=("Arial", 14, "bold"))
        self.chat_header.pack(pady=10)
        
        # Дисплей сообщений
        self.chat_display = scrolledtext.ScrolledText(right_frame, height=20, width=60, 
                                                      state=tk.DISABLED, wrap=tk.WORD)
        self.chat_display.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        
        # Поле для ввода сообщения
        input_frame = tk.Frame(right_frame)
        input_frame.pack(padx=5, pady=5, fill=tk.X)
        
        tk.Label(input_frame, text="Сообщение:").pack(anchor=tk.W)
        self.message_entry = tk.Entry(input_frame, width=60)
        self.message_entry.pack(pady=5, fill=tk.X)
        self.message_entry.bind('<Return>', lambda e: self.send_message())
        
        # Кнопка отправить
        tk.Button(input_frame, text="Отправить", command=self.send_message, 
                 width=20, bg="#2196F3", fg="white").pack(pady=5)
    
    def request_chats_list(self):
        """Запрашивает список пользователей для начала чата"""
        def request_users():
            try:
                self.server_socket.send(json.dumps({"action": "get_users"}).encode())
            except:
                pass
        
        thread = threading.Thread(target=request_users, daemon=True)
        thread.start()
    
    def add_new_chat(self):
        """Диалог для добавления нового чата"""
        # Запрашиваем актуальный список пользователей у сервера ДО создания диалога
        self.request_chats_list()
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Новый чат")
        dialog.geometry("300x150")
        dialog.transient(self.root)

        tk.Label(dialog, text="Выберите пользователя:").pack(pady=10)

        choice_var = tk.StringVar(dialog)
        choice_var.set("Загрузка...")

        option_menu = tk.OptionMenu(dialog, choice_var, "Загрузка...")
        option_menu.config(width=28)
        option_menu.pack(pady=5)

        info_label = tk.Label(dialog, text="(список обновится автоматически)")
        info_label.pack(pady=(0, 5))

        add_btn = tk.Button(dialog, text="Добавить", width=15)
        add_btn.pack(pady=10)

        # Обновление опций асинхронно (чтобы UI не зависал)
        def update_options(attempts_left=25):
            # Собираем кандидатов из self.chats (они наполняются receive_messages)
            with self.chats_lock:
                candidates = [u for u in self.chats.keys() if u != self.username]

            # Исключаем уже добавленные (если уже есть чат, можно выбрать его тоже)
            if candidates:
                menu = option_menu['menu']
                menu.delete(0, 'end')
                for user in sorted(candidates):
                    menu.add_command(label=user, command=lambda v=user: choice_var.set(v))
                choice_var.set(sorted(candidates)[0])
                add_btn.config(state=tk.NORMAL)
            else:
                # Пока нет данных — пробуем через 200ms
                if attempts_left > 0:
                    dialog.after(200, lambda: update_options(attempts_left-1))
                else:
                    # Ничего не найдено
                    menu = option_menu['menu']
                    menu.delete(0, 'end')
                    menu.add_command(label='Нет доступных пользователей', command=lambda: None)
                    choice_var.set('Нет доступных пользователей')
                    add_btn.config(state=tk.DISABLED)

        def add_chat_from_choice():
            recipient = choice_var.get()
            if not recipient or recipient in ("Загрузка...", 'Нет доступных пользователей'):
                messagebox.showwarning("Внимание", "Выберите пользователя из списка!")
                return
            if recipient == self.username:
                messagebox.showwarning("Внимание", "Нельзя написать самому себе!")
                return
            with self.chats_lock:
                if recipient not in self.chats:
                    self.chats[recipient] = []
                self.current_chat = recipient
                self.update_chats_listbox()
            dialog.destroy()

        add_btn.config(command=add_chat_from_choice)
        add_btn.config(state=tk.DISABLED)

        # Запускаем цикл обновления опций
        update_options()
    
    def on_chat_selected(self, event):
        """При выборе чата из списка"""
        selection = self.chats_listbox.curselection()
        if selection:
            self.current_chat = self.chats_listbox.get(selection[0])
            self.chat_header.config(text=f"Чат с {self.current_chat}")
            self.load_chat_history()
            self.display_current_chat()
    
    def load_chat_history(self):
        """Загружает историю чата с сервера"""
        if not self.current_chat:
            return
        
        def request_history():
            try:
                self.server_socket.send(json.dumps({
                    "action": "get_chat_history",
                    "other_user": self.current_chat
                }).encode())
            except:
                pass
        
        thread = threading.Thread(target=request_history, daemon=True)
        thread.start()
    
    def display_current_chat(self):
        """Отображает текущий чат"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)
        
        with self.chats_lock:
            messages = self.chats.get(self.current_chat, [])
            for msg in messages:
                sender = msg.get("sender")
                text = msg.get("text")
                timestamp = msg.get("timestamp")
                
                if sender == self.username:
                    display_text = f"[{timestamp}] Вы: {text}\n"
                else:
                    display_text = f"[{timestamp}] {sender}: {text}\n"
                
                self.chat_display.insert(tk.END, display_text)
        
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)
    
    def send_message(self):
        """Отправляет сообщение"""
        if not self.current_chat:
            messagebox.showwarning("Внимание", "Выберите чат!")
            return
        
        text = self.message_entry.get().strip()
        if not text:
            return
        
        try:
            self.server_socket.send(json.dumps({
                "action": "send_message",
                "recipient": self.current_chat,
                "text": text
            }).encode())
            
            # Добавляем сообщение локально
            msg_data = {
                "sender": self.username,
                "text": text,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
            
            with self.chats_lock:
                if self.current_chat not in self.chats:
                    self.chats[self.current_chat] = []
                self.chats[self.current_chat].append(msg_data)
            
            self.display_current_chat()
            self.message_entry.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("Ошибка отправки", str(e))
    
    def update_chats_listbox(self):
        """Обновляет список чатов в левой панели"""
        self.chats_listbox.delete(0, tk.END)
        with self.chats_lock:
            for username in sorted(self.chats.keys()):
                self.chats_listbox.insert(tk.END, username)
    
    def start_receive_thread(self):
        """Запускает поток получения сообщений"""
        self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        self.receive_thread.start()
    
    def receive_messages(self):
        """Получает входящие сообщения"""
        while self.running and self.server_socket:
            try:
                data = self.server_socket.recv(1024).decode()
                if not data:
                    break
                
                message = json.loads(data)
                
                if message.get("action") == "receive_message":
                    sender = message.get("sender")
                    text = message.get("text")
                    timestamp = message.get("timestamp")
                    
                    msg_data = {
                        "sender": sender,
                        "text": text,
                        "timestamp": timestamp
                    }
                    
                    with self.chats_lock:
                        if sender not in self.chats:
                            self.chats[sender] = []
                        self.chats[sender].append(msg_data)
                        
                        # Обновляем список чатов
                        self.update_chats_listbox()
                        
                        # Если это текущий активный чат, обновляем дисплей
                        if self.current_chat == sender:
                            self.display_current_chat()
                
                elif message.get("action") == "users_list":
                    users = message.get("users", [])
                    with self.chats_lock:
                        for user in users:
                            if user != self.username and user not in self.chats:
                                self.chats[user] = []
                        self.update_chats_listbox()
                
                elif message.get("action") == "chat_history":
                    other_user = message.get("other_user")
                    history = message.get("messages", [])
                    
                    with self.chats_lock:
                        self.chats[other_user] = history
                        if self.current_chat == other_user:
                            self.display_current_chat()
            
            except Exception as e:
                if self.running:
                    print(f"Ошибка получения: {e}")
                break
    
    def logout(self):
        """Выходит из аккаунта"""
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
        self.create_login_screen()
    
    def clear_window(self):
        """Очищает окно"""
        for widget in self.root.winfo_children():
            widget.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatClient(root)
    root.mainloop()
