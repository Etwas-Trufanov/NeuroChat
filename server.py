import socket
import threading
import json
from datetime import datetime

# Глобальные переменные
users = {}  # {username: password}
user_connections = {}  # {username: (socket, address)}
chat_history = {}  # {(user1, user2): [messages]} где user1 < user2 (отсортированы)

def broadcast_discovery(port):
    """Отвечает на поиск сервера в сети"""
    discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    discovery_socket.bind(('', 12345))
    
    print(f"[DISCOVERY] Слушаю на порту 12345...")
    
    while True:
        try:
            data, addr = discovery_socket.recvfrom(1024)
            if data.decode() == "DISCOVER_SERVER":
                print(f"[DISCOVERY] Получен запрос поиска от {addr}")
                # Получаем локальный IP адрес на основе сетевого интерфейса
                try:
                    # Пытаемся получить реальный IP адрес
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect((addr[0], addr[1]))
                    server_ip = s.getsockname()[0]
                    s.close()
                except:
                    server_ip = "127.0.0.1"
                
                response = json.dumps({
                    "server_ip": server_ip,
                    "server_port": port
                })
                print(f"[DISCOVERY] Отправляю ответ: {response} на {addr}")
                discovery_socket.sendto(response.encode(), addr)
        except Exception as e:
            print(f"[DISCOVERY] Ошибка: {e}")

def handle_client(conn, addr, port):
    """Обрабатывает подключение клиента"""
    print(f"[CONNECT] Подключен клиент {addr}")
    username = None
    
    try:
        while True:
            data = conn.recv(1024).decode()
            print(f"[SERVER RECV RAW] From {addr}: {data}")
            if not data:
                break
            
            message = json.loads(data)
            action = message.get("action")
            
            # Регистрация
            if action == "register":
                username = message.get("username")
                password = message.get("password")

                if username in users:
                    conn.sendall(json.dumps({"status": "error", "message": "Пользователь уже существует"}).encode())
                else:
                    users[username] = password
                    conn.sendall(json.dumps({"status": "success", "message": "Регистрация успешна"}).encode())
                    print(f"[REGISTER] Зарегистрирован пользователь {username}")
            
            # Вход
            elif action == "login":
                username = message.get("username")
                password = message.get("password")
                
                if username not in users:
                    conn.send(json.dumps({"status": "error", "message": "Пользователь не найден"}).encode())
                elif users[username] != password:
                    conn.send(json.dumps({"status": "error", "message": "Неверный пароль"}).encode())
                else:
                    user_connections[username] = (conn, addr)
                    conn.sendall(json.dumps({"status": "success", "message": "Вход успешен"}).encode())
                    print(f"[LOGIN] Пользователь {username} вошел")
            
            # Отправка сообщения
            elif action == "send_message":
                sender = username
                recipient = message.get("recipient")
                text = message.get("text")
                
                if recipient not in users:
                    conn.send(json.dumps({"status": "error", "message": "Получатель не найден"}).encode())
                else:
                    # Создаем уникальный ключ чата (сортируем имена)
                    chat_key = tuple(sorted([sender, recipient]))
                    if chat_key not in chat_history:
                        chat_history[chat_key] = []
                    
                    msg_data = {
                        "sender": sender,
                        "text": text,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    }
                    
                    # Сохраняем в историю
                    chat_history[chat_key].append(msg_data)
                    
                    # Если получатель онлайн, отправить напрямую
                    if recipient in user_connections:
                        try:
                            recipient_conn = user_connections[recipient][0]
                            recipient_conn.sendall(json.dumps({
                                "action": "receive_message",
                                "sender": sender,
                                "text": text,
                                "timestamp": msg_data["timestamp"]
                            }).encode())
                        except:
                            pass
                    
                    conn.sendall(json.dumps({"status": "success", "message": "Сообщение отправлено"}).encode())
                    print(f"[MESSAGE] {sender} -> {recipient}: {text}")
            
            # Получение истории чата
            elif action == "get_chat_history":
                other_user = message.get("other_user")
                if other_user and other_user in users:
                    chat_key = tuple(sorted([username, other_user]))
                    history = chat_history.get(chat_key, [])
                    conn.sendall(json.dumps({
                        "action": "chat_history",
                        "other_user": other_user,
                        "messages": history
                    }).encode())
                    print(f"[HISTORY] Отправлена история чата {chat_key}")
            
            # Получение списка пользователей
            elif action == "get_users":
                user_list = list(users.keys())
                conn.sendall(json.dumps({
                    "action": "users_list",
                    "users": user_list
                }).encode())
                print(f"[USERS] Отправлен список пользователей клиенту {addr}")
            # Получение списка чатов, где есть переписка с этим пользователем
            elif action == "get_my_chats":
                # соберём список собеседников, с которыми у username есть история
                chats_for_user = []
                try:
                    for chat_key, msgs in chat_history.items():
                        if not msgs:
                            continue
                        if username in chat_key:
                            other = chat_key[1] if chat_key[0] == username else chat_key[0]
                            chats_for_user.append(other)
                except Exception:
                    chats_for_user = []
                conn.sendall(json.dumps({
                    "action": "my_chats",
                    "chats": chats_for_user
                }).encode())
                print(f"[MY_CHATS] Отправлен список чатов для {username}: {chats_for_user}")
    
    except Exception as e:
        print(f"[ERROR] Ошибка клиента {addr}: {e}")
    
    finally:
        if username and username in user_connections:
            del user_connections[username]
        conn.close()
        print(f"[DISCONNECT] Отключен клиент {addr}")

def start_server(host='0.0.0.0', port=5555):
    """Запускает сервер"""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)
    
    print(f"[SERVER] Запущен на {host}:{port}")
    
    # Запуск потока для обработки поиска сервера
    discovery_thread = threading.Thread(target=broadcast_discovery, args=(port,), daemon=True)
    discovery_thread.start()
    
    try:
        while True:
            conn, addr = server_socket.accept()
            client_thread = threading.Thread(target=handle_client, args=(conn, addr, port))
            client_thread.daemon = True
            client_thread.start()
    
    except KeyboardInterrupt:
        print("\n[SERVER] Выключение...")
    
    finally:
        server_socket.close()

if __name__ == "__main__":
    start_server()
