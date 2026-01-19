import socket
import threading
import json
from datetime import datetime

# Глобальные переменные
users = {}  # {username: password}
user_connections = {}  # {username: (socket, address)}
message_queue = {}  # {username: [messages]}

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
            if not data:
                break
            
            message = json.loads(data)
            action = message.get("action")
            
            # Регистрация
            if action == "register":
                username = message.get("username")
                password = message.get("password")
                
                if username in users:
                    conn.send(json.dumps({"status": "error", "message": "Пользователь уже существует"}).encode())
                else:
                    users[username] = password
                    message_queue[username] = []
                    conn.send(json.dumps({"status": "success", "message": "Регистрация успешна"}).encode())
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
                    conn.send(json.dumps({"status": "success", "message": "Вход успешен"}).encode())
                    print(f"[LOGIN] Пользователь {username} вошел")
            
            # Отправка сообщения
            elif action == "send_message":
                recipient = message.get("recipient")
                text = message.get("text")
                
                if recipient not in users:
                    conn.send(json.dumps({"status": "error", "message": "Получатель не найден"}).encode())
                else:
                    msg_data = {
                        "sender": username,
                        "text": text,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    }
                    message_queue[recipient].append(msg_data)
                    
                    # Если получатель онлайн, отправить напрямую
                    if recipient in user_connections:
                        try:
                            recipient_conn = user_connections[recipient][0]
                            recipient_conn.send(json.dumps({
                                "action": "receive_message",
                                "sender": username,
                                "text": text,
                                "timestamp": msg_data["timestamp"]
                            }).encode())
                        except:
                            pass
                    
                    conn.send(json.dumps({"status": "success", "message": "Сообщение отправлено"}).encode())
                    print(f"[MESSAGE] {username} -> {recipient}: {text}")
            
            # Получение сохраненных сообщений
            elif action == "get_messages":
                messages = message_queue.get(username, [])
                conn.send(json.dumps({
                    "action": "messages",
                    "messages": messages
                }).encode())
                message_queue[username] = []
            
            # Получение списка пользователей
            elif action == "get_users":
                user_list = list(users.keys())
                conn.send(json.dumps({
                    "action": "users_list",
                    "users": user_list
                }).encode())
    
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
