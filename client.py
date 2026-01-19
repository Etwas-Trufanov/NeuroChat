import tkinter as tk
from tkinter import messagebox, simpledialog, scrolledtext
import socket
import threading
import json
from datetime import datetime

class ChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Простой мессенджер")
        self.root.geometry("500x600")
        
        self.server_socket = None
        self.username = None
        self.server_host = None
        self.server_port = None
        
        self.create_login_screen()
        
        # Поток для получения сообщений
        self.receive_thread = None
        self.running = True
    
    def find_server(self):
        """Ищет сервер в локальной сети"""
        try:
            discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            discovery_socket.settimeout(10)
            
            print("[CLIENT] Отправляю запрос поиска сервера...")
            # Отправляем broadcast запрос
            discovery_socket.sendto(b"DISCOVER_SERVER", ('<broadcast>', 12345))
            
            # Ждем ответа
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
    
    def send_to_server(self, message):
        """Отправляет сообщение на сервер"""
        try:
            print(f"[CLIENT] Отправляю: {message}")
            self.server_socket.send(json.dumps(message).encode())
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
        
        tk.Label(frame, text="Простой мессенджер", font=("Arial", 16, "bold")).pack(pady=10)
        
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
            })
            
            if response:
                data = json.loads(response)
                if data.get("status") == "success":
                    self.username = username
                    self.create_chat_screen()
                    self.start_receive_thread()
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
            })
            
            if response:
                data = json.loads(response)
                if data.get("status") == "success":
                    messagebox.showinfo("Успех", "Регистрация успешна! Входим в аккаунт...")
                    # Закрываем соединение и переподключаемся для входа
                    self.server_socket.close()
                    self.server_socket = None
                    # Автоматический вход после регистрации
                    perform_login(username, password)
                else:
                    messagebox.showerror("Ошибка регистрации", data.get("message", "Неизвестная ошибка"))
        
        button_frame = tk.Frame(frame)
        button_frame.pack(pady=10)
        
        tk.Button(button_frame, text="Вход", command=login, width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Регистрация", command=register, width=15).pack(side=tk.LEFT, padx=5)
    
    def create_chat_screen(self):
        """Создает экран чата"""
        self.clear_window()
        
        # Заголовок
        tk.Label(self.root, text=f"Чат (Пользователь: {self.username})", 
                 font=("Arial", 12, "bold")).pack(pady=10)
        
        # Чат
        self.chat_display = scrolledtext.ScrolledText(self.root, height=20, width=60, state=tk.DISABLED)
        self.chat_display.pack(padx=10, pady=5)
        
        # Поле для ввода сообщения
        input_frame = tk.Frame(self.root)
        input_frame.pack(padx=10, pady=5, fill=tk.X)
        
        tk.Label(input_frame, text="Кому:").pack(side=tk.LEFT)
        self.recipient_entry = tk.Entry(input_frame, width=15)
        self.recipient_entry.pack(side=tk.LEFT, padx=5)
        
        tk.Button(input_frame, text="Список пользователей", 
                 command=self.show_users_list).pack(side=tk.LEFT, padx=5)
        
        # Сообщение
        tk.Label(self.root, text="Сообщение:").pack(anchor=tk.W, padx=10)
        self.message_entry = scrolledtext.ScrolledText(self.root, height=4, width=60)
        self.message_entry.pack(padx=10, pady=5)
        
        # Кнопки
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)
        
        tk.Button(button_frame, text="Отправить", 
                 command=self.send_message, width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Выход", 
                 command=self.logout, width=15).pack(side=tk.LEFT, padx=5)
    
    def show_users_list(self):
        """Показывает список пользователей"""
        try:
            response = self.send_to_server({"action": "get_users"})
            if response:
                data = json.loads(response)
                users = data.get("users", [])
                # Убираем самого себя из списка
                users = [u for u in users if u != self.username]
                
                if users:
                    users_text = "\n".join(users)
                    messagebox.showinfo("Пользователи онлайн", users_text)
                else:
                    messagebox.showinfo("Пользователи", "Других пользователей нет")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
    
    def send_message(self):
        """Отправляет сообщение"""
        recipient = self.recipient_entry.get()
        text = self.message_entry.get("1.0", tk.END).strip()
        
        if not recipient or not text:
            messagebox.showwarning("Внимание", "Заполните все поля!")
            return
        
        try:
            response = self.send_to_server({
                "action": "send_message",
                "recipient": recipient,
                "text": text
            })
            
            if response:
                data = json.loads(response)
                if data.get("status") == "success":
                    self.add_to_chat(f"[{datetime.now().strftime('%H:%M:%S')}] Вы -> {recipient}: {text}", "sent")
                    self.message_entry.delete("1.0", tk.END)
                else:
                    messagebox.showerror("Ошибка", data.get("message", ""))
        except Exception as e:
            messagebox.showerror("Ошибка отправки", str(e))
    
    def add_to_chat(self, message, message_type="received"):
        """Добавляет сообщение в окно чата"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, message + "\n")
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)
    
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
                    self.add_to_chat(f"[{timestamp}] {sender}: {text}", "received")
            
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
        self.create_login_screen()
    
    def clear_window(self):
        """Очищает окно"""
        for widget in self.root.winfo_children():
            widget.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatClient(root)
    root.mainloop()
