import tkinter as tk
from tkinter import messagebox, scrolledtext
try:
    import customtkinter as ctk
    USE_CTK = True
    # Follow system theme dynamically
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
except Exception:
    ctk = None
    USE_CTK = False

# Widget aliases: prefer customtkinter widgets when available, fallback to tkinter
if USE_CTK:
    FrameWidget = ctk.CTkFrame
    LabelWidget = ctk.CTkLabel
    ButtonWidget = ctk.CTkButton
    EntryWidget = ctk.CTkEntry
    TextWidget = ctk.CTkTextbox
else:
    FrameWidget = tk.Frame
    LabelWidget = tk.Label
    ButtonWidget = tk.Button
    EntryWidget = tk.Entry
    TextWidget = scrolledtext.ScrolledText
import socket
import threading
import json
from datetime import datetime
from queue import Queue, Empty
import tkinter.font as tkfont
import sys
try:
    from plyer import notification as plyer_notify
except Exception:
    plyer_notify = None

class ChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title("NeuroChat - Мессенджер")
        self.root.geometry("900x600")
        # Apply theme-based menu colors early
        self.apply_theme_to_root()
        # External login hook for MVC controller integration
        self.external_login_handler = None
        
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

        # Unread chats set
        self.unread_chats = set()
        # Theme tracking
        self.current_theme = None
        # Fonts
        preferred = "Segoe UI" if sys.platform.startswith("win") else "Helvetica"
        self.font_header = tkfont.Font(family=preferred, size=18, weight="bold")
        self.font_list = tkfont.Font(family=preferred, size=12)
        self.font_message = tkfont.Font(family=preferred, size=11)
        self.font_entry = tkfont.Font(family=preferred, size=12)

        self.start_theme_monitor()
        
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

    def get_theme_colors(self):
        # Returns (bg, fg, selectbg) for listbox/chat depending on theme
        if USE_CTK:
            mode = ctk.get_appearance_mode()
            if mode == "Dark":
                return ("#1f1f1f", "#ffffff", "#3a7bd5")
            else:
                return ("#ffffff", "#000000", "#82aaff")
        else:
            # Default tkinter light colors
            return ("#ffffff", "#000000", "#cce6ff")

    def start_theme_monitor(self, interval=1000):
        # Start polling for theme changes
        def poll():
            try:
                theme = None
                if USE_CTK:
                    theme = ctk.get_appearance_mode()
                else:
                    theme = 'Light'
                if theme != self.current_theme:
                    self.current_theme = theme
                    self.update_theme()
            except Exception:
                pass
            if self.running:
                try:
                    self.root.after(interval, poll)
                except Exception:
                    pass
        poll()

    def update_theme(self):
        bg, fg, selbg = self.get_theme_colors()
        # Apply to chat display
        try:
            self.chat_display.config(bg=bg, fg=fg)
        except Exception:
            pass
        # Apply to input
        try:
            self.message_entry.config(bg=bg, fg=fg, insertbackground=fg)
        except Exception:
            pass
        # Apply to listbox
        try:
            self.chats_listbox.config(bg=bg, fg=fg, selectbackground=selbg)
            # Re-render list to apply styling markers
            self.update_chats_listbox()
        except Exception:
            pass
        # Apply menu/theme options
        try:
            self.apply_theme_to_root()
        except Exception:
            pass
        # Also try to recolor existing menu
        try:
            mname = self.root.cget('menu')
            if mname:
                try:
                    menu_widget = self.root.nametowidget(mname)
                    menu_widget.config(bg=bg, fg=fg, activebackground=selbg, activeforeground=fg)
                except Exception:
                    pass
        except Exception:
            pass
        # Style send button if present
        try:
            if hasattr(self, 'send_btn'):
                if USE_CTK:
                    # CTkButton uses fg_color
                    try:
                        mode = ctk.get_appearance_mode()
                        if mode == 'Dark':
                            self.send_btn.configure(fg_color="#2b7bd3", text_color="#ffffff")
                        else:
                            self.send_btn.configure(fg_color="#1976d2", text_color="#ffffff")
                    except Exception:
                        pass
                else:
                    # Tk Button
                    try:
                        self.send_btn.configure(bg=selbg, fg=fg)
                    except Exception:
                        pass
        except Exception:
            pass

    def apply_theme_to_root(self):
        # Apply menu colors and other global settings based on current theme
        try:
            bg, fg, selbg = self.get_theme_colors()
            # Menu colors
            self.root.option_add("*Menu.background", bg)
            self.root.option_add("*Menu.foreground", fg)
            self.root.option_add("*Menu.activeBackground", selbg)
            self.root.option_add("*Menu.activeForeground", fg)
        except Exception:
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
        frame = FrameWidget(self.root)
        frame.pack(expand=True, padx=20, pady=20)
        LabelWidget(frame, text="NeuroChat").pack(pady=20)
        try:
            LabelWidget(frame, text="NeuroChat").config(font=self.font_header)
        except Exception:
            pass
        LabelWidget(frame, text="Имя:").pack(anchor=tk.W)
        username_entry = EntryWidget(frame)
        try:
            username_entry.configure(font=self.font_entry)
        except Exception:
            pass
        username_entry.pack(pady=5, fill=tk.X)
        LabelWidget(frame, text="Пароль:").pack(anchor=tk.W)
        password_entry = EntryWidget(frame, show="*")
        try:
            password_entry.configure(font=self.font_entry)
        except Exception:
            pass
        password_entry.pack(pady=5, fill=tk.X)
        
        def perform_login(username, password):
            if not username or not password:
                messagebox.showwarning("Внимание", "Заполните все поля!")
                return
            # If an external login handler is provided (MVC controller), delegate
            if hasattr(self, 'external_login_handler') and self.external_login_handler:
                try:
                    self.external_login_handler(username, password)
                except Exception as e:
                    messagebox.showerror("Ошибка", str(e))
                return
            if not self.connect_to_server():
                return
            try:
                print(f"[LOGIN] Отправляю login для {username}")
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
                    
                    self.server_socket.send(json.dumps({"action": "get_users"}).encode())
                    print(f"[LOGIN] Отправлен get_users запрос, жду ответ...")
                    users_resp = self.server_socket.recv(1024).decode()
                    print(f"[LOGIN] Получен users response: {users_resp}")
                    
                    with self.users_lock:
                        self.all_users = json.loads(users_resp).get("users", [])
                    
                    # Запросить список чатов, где есть переписка, и загрузить их историю
                    try:
                        self.server_socket.send(json.dumps({"action": "get_my_chats"}).encode())
                        mych_resp = self.server_socket.recv(4096).decode()
                        mych_data = json.loads(mych_resp)
                        chats = mych_data.get('chats', [])
                        for other in chats:
                            try:
                                self.server_socket.send(json.dumps({"action": "get_chat_history", "other_user": other}).encode())
                                hist_resp = self.server_socket.recv(8192).decode()
                                hist_data = json.loads(hist_resp)
                                hist = hist_data.get('messages', [])
                                with self.chats_lock:
                                    self.chats[other] = hist
                                if self.current_chat == other:
                                    self.event_queue.put(("display_chat", None))
                            except Exception:
                                continue
                    except Exception:
                        pass

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
        
        button_frame = FrameWidget(frame)
        button_frame.pack(pady=10)
        ButtonWidget(button_frame, text="Вход", command=login, width=120).pack(side=tk.LEFT, padx=5)
        ButtonWidget(button_frame, text="Регистрация", command=register, width=120).pack(side=tk.LEFT, padx=5)
    
    def create_chat_screen(self):
        self.clear_window()
        
        # МЕНЮ
        # Re-apply theme for menus before creating them
        self.apply_theme_to_root()
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Выход", command=self.logout)
        
        main_frame = FrameWidget(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        left_frame = FrameWidget(main_frame, width=260)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=8, pady=8)
        left_frame.pack_propagate(False)

        LabelWidget(left_frame, text="Чаты", font=("Arial", 14, "bold")).pack(pady=10)
        ButtonWidget(left_frame, text="+ Новый", command=self.add_new_chat, width=150).pack(pady=6)

        self.chats_listbox = tk.Listbox(left_frame, height=30, width=30, font=self.font_list)
        self.chats_listbox.pack(pady=5, padx=5, fill=tk.BOTH, expand=True)
        self.chats_listbox.bind('<<ListboxSelect>>', self.on_chat_selected)
        # Style listbox according to theme
        bg, fg, selbg = self.get_theme_colors()
        try:
            self.chats_listbox.config(bg=bg, fg=fg, selectbackground=selbg)
        except Exception:
            pass

        right_frame = FrameWidget(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.chat_header = LabelWidget(right_frame, text="Выберите чат")
        try:
            self.chat_header.configure(font=self.font_header)
        except Exception:
            pass
        self.chat_header.pack(pady=10)

        # Use TextWidget (CTkTextbox or ScrolledText)
        # Use ScrolledText for reliable behavior and style it
        chat_bg, chat_fg, _ = self.get_theme_colors()
        self.chat_display = scrolledtext.ScrolledText(right_frame, height=12, width=60, bg=chat_bg, fg=chat_fg, wrap=tk.WORD, font=self.font_message)
        try:
            # CTkTextbox doesn't support state via constructor
            self.chat_display.configure(state=tk.DISABLED)
        except Exception:
            pass
        self.chat_display.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        input_frame = FrameWidget(right_frame)
        input_frame.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        LabelWidget(input_frame, text="Сообщение:").pack(anchor=tk.W)

        # Многострочное поле ввода
        entry_bg, entry_fg, _ = self.get_theme_colors()
        self.message_entry = scrolledtext.ScrolledText(input_frame, height=4, width=60, bg=entry_bg, fg=entry_fg, wrap=tk.WORD, insertbackground=entry_fg, font=self.font_entry)
        self.message_entry.pack(side=tk.LEFT, pady=5, padx=(0, 5), fill=tk.BOTH, expand=True)

        # Кнопка отправить справа
        self.send_btn = ButtonWidget(input_frame, text="Отправить", command=self.send_message, width=120)
        try:
            self.send_btn.configure(font=self.font_entry)
        except Exception:
            pass
        self.send_btn.pack(side=tk.LEFT, padx=5)
        
        # Bind Enter и Shift+Enter
        self.message_entry.bind('<Return>', self.on_message_key)
        self.message_entry.bind('<Shift-Return>', self.insert_newline)
    
    def on_message_key(self, event):
        """Обработка Enter/Shift+Enter в поле ввода"""
        # Enter без Shift - отправить
        self.send_message()
        return "break"  # Отменить стандартное поведение Enter

    def insert_newline(self, event):
        # Вставляем перенос строки при Shift+Enter
        self.message_entry.insert(tk.INSERT, "\n")
        return "break"
    
    def add_new_chat(self):
        # Отправляем запрос асинхронно, не блокируя основной поток
        print("[ADD_CHAT] Запрашиваю обновленный список пользователей асинхронно")
        self.send_to_server({"action": "get_users"})
        dialog = tk.Toplevel(self.root)
        dialog.title("Новый чат")
        dialog.geometry("320x360")
        dialog.transient(self.root)

        tk.Label(dialog, text="Выберите пользователя:").pack(pady=6)

        # Список с прокруткой — помещается в диалог лучше, чем OptionMenu
        list_frame = tk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        list_scroll = tk.Scrollbar(list_frame)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        users_listbox = tk.Listbox(list_frame, yscrollcommand=list_scroll.set, selectmode=tk.SINGLE)
        users_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.config(command=users_listbox.yview)

        def populate_listbox():
            users_listbox.delete(0, tk.END)
            with self.users_lock:
                candidates = [u for u in self.all_users if u != self.username]
            for u in sorted(candidates):
                users_listbox.insert(tk.END, u)
            return len(candidates) > 0

        def add_chat_from_selection(event=None):
            sel = users_listbox.curselection()
            if not sel:
                return
            recipient = users_listbox.get(sel[0])
            dialog.destroy()
            with self.chats_lock:
                if recipient not in self.chats:
                    self.chats[recipient] = []
                self.current_chat = recipient
            # clear unread for this chat
            if recipient in self.unread_chats:
                self.unread_chats.discard(recipient)
            self.update_chats_listbox()
            self.display_current_chat()
            self.send_to_server({"action": "get_chat_history", "other_user": recipient})

        users_listbox.bind('<Double-Button-1>', add_chat_from_selection)

        add_button = tk.Button(dialog, text="Добавить", command=add_chat_from_selection, width=15)
        add_button.pack(pady=8)

        # Периодически обновляем список из кеша (и запрос уже отправлен выше)
        def refresh_until_found(retries=20, delay=200):
            present = populate_listbox()
            if present:
                add_button.config(state=tk.NORMAL)
                return
            else:
                add_button.config(state=tk.DISABLED)
            if retries > 0:
                dialog.after(delay, lambda: refresh_until_found(retries-1, delay))
            else:
                add_button.config(state=tk.DISABLED)

        # Инициализация
        populate_listbox()
        dialog.after(150, refresh_until_found)
    
    def on_chat_selected(self, event):
        selection = self.chats_listbox.curselection()
        if selection:
            sel_text = self.chats_listbox.get(selection[0])
            # remove unread marker if present
            if sel_text.startswith("🔴 "):
                sel_text = sel_text[2:]
            self.current_chat = sel_text
            self.chat_header.config(text=f"Чат с {self.current_chat}")
            # clear unread
            if self.current_chat in self.unread_chats:
                self.unread_chats.discard(self.current_chat)
            self.update_chats_listbox()
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
                label = user
                if user in self.unread_chats:
                    # prepend red dot indicator
                    label = "🔴 " + label
                self.chats_listbox.insert(tk.END, label)
        # Try to color unread items red if supported
        try:
            for idx in range(self.chats_listbox.size()):
                text = self.chats_listbox.get(idx)
                if text.startswith("🔴 "):
                    try:
                        self.chats_listbox.itemconfig(idx, fg="#ff4d4d")
                    except Exception:
                        pass
        except Exception:
            pass
    
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
                        # dedupe: avoid inserting exact duplicate of last message
                        last = self.chats[sender][-1] if self.chats[sender] else None
                        if not last or not (last.get('sender') == msg_data.get('sender') and last.get('text') == msg_data.get('text') and last.get('timestamp') == msg_data.get('timestamp')):
                            self.chats[sender].append(msg_data)
                    # Mark unread if not viewing this chat or app not focused
                    focused = (self.root.focus_displayof() is not None)
                    minimized = False
                    try:
                        minimized = (str(self.root.state()) == 'iconic')
                    except Exception:
                        minimized = False
                    if self.current_chat != sender or (not focused) or minimized:
                        self.unread_chats.add(sender)
                        # send desktop notification if possible
                        try:
                            if plyer_notify:
                                plyer_notify.notify(title=f"New message from {sender}", message=text, timeout=5)
                        except Exception:
                            pass
                    # Update UI
                    self.event_queue.put(("update_chats_list", None))
                    if self.current_chat == sender:
                        # If currently viewing, clear unread mark
                        if sender in self.unread_chats:
                            self.unread_chats.discard(sender)
                        self.event_queue.put(("display_chat", None))
                
                elif msg.get("action") == "chat_history":
                    other = msg.get("other_user")
                    hist = msg.get("messages", [])
                    with self.chats_lock:
                        self.chats[other] = hist
                        if self.current_chat == other:
                            self.event_queue.put(("display_chat", None))
                elif msg.get("action") == "users_list":
                    users = msg.get("users", [])
                    with self.users_lock:
                        self.all_users = users
                    print(f"[RECEIVE] Обновлён список пользователей: {self.all_users}")
                    # UI dialogs check the cache periodically; also signal update if needed
                    self.event_queue.put(("update_chats_list", None))
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
    # Backwards-compatible entrypoint: run controller that composes model+view
    try:
        from client_controller import ChatController
        ChatController().run()
    except Exception:
        # Fallback: run the legacy UI directly
        if USE_CTK:
            root = ctk.CTk()
        else:
            root = tk.Tk()
        app = ChatClient(root)
        root.mainloop()
