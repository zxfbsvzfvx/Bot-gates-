
import network
import urequests as requests
import ujson as json
import time
import machine
import onewire
import ds18x20
from machine import Pin, PWM

WIFI_SSID = "ВАШ_WIFI_SSID"
WIFI_PASS = "ВАШ_WIFI_ПАРОЛЬ"
BOT_TOKEN = "ВАШ_ТОКЕН_БОТА"
CHAT_ID = "ВАШ_CHAT_ID"
TELEGRAM_URL = "https://api.telegram.org/bot{}/sendMessage".format(BOT_TOKEN)

TEMP_PIN = 4
RELAY_OPEN = Pin(26, Pin.OUT)
RELAY_CLOSE = Pin(27, Pin.OUT)
RELAY_STOP = Pin(14, Pin.OUT)
RELAY_ENABLE = Pin(12, Pin.OUT)
BUZZER = PWM(Pin(18))
LED_STATUS = Pin(5, Pin.OUT)


last_temp = 0
last_telegram_check = 0
system_overheated = False
temp_sensor_connected = True
operation_start_time = 0


GATE_CLOSED = 0
GATE_OPENING = 1
GATE_OPEN = 2
GATE_CLOSING = 3
GATE_STOPPED = 4
current_state = GATE_CLOSED


ds_pin = Pin(TEMP_PIN)
ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))
roms = []

def setup():
    print("🚪 Умные ворота - MicroPython версия")
    
 
    BUZZER.duty(0)  # Выключить зуммер
    

    RELAY_OPEN.value(0)
    RELAY_CLOSE.value(0)
    RELAY_STOP.value(1)  # HIGH = выключен
    RELAY_ENABLE.value(0)
    LED_STATUS.value(0)
    

    init_temperature_sensor()
 
    connect_wifi()
    
    print("✅ Система готова")
    print("📱 Отправьте команду в Telegram")
    print("📟 Серийные команды: O-открыть, C-закрыть, S-стоп, T-температура")

def init_temperature_sensor():
    global temp_sensor_connected, roms
    try:
        roms = ds_sensor.scan()
        if len(roms) == 0:
            print("⚠️ Датчик температуры НЕ найден!")
            temp_sensor_connected = False
        else:
            print("✅ Датчиков температуры найдено:", len(roms))
            temp_sensor_connected = True
    except Exception as e:
        print("❌ Ошибка инициализации датчика температуры:", e)
        temp_sensor_connected = False

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print("📶 Подключение к WiFi:", WIFI_SSID)
        wlan.connect(WIFI_SSID, WIFI_PASS)
        
        timeout = 30
        while not wlan.isconnected() and timeout > 0:
            time.sleep(0.5)
            print(".", end="")
            timeout -= 1
    
    if wlan.isconnected():
        print("\n✅ WiFi подключен!")
        print("📡 IP:", wlan.ifconfig()[0])
        
      
        welcome_msg = "🚪 Умные ворота подключены!\n"
        welcome_msg += "IP: " + wlan.ifconfig()[0] + "\n"
        welcome_msg += "Датчик температуры: " + ("✅ Подключен" if temp_sensor_connected else "❌ ОТСУТСТВУЕТ")
        send_telegram_message(welcome_msg)
    else:
        print("\n❌ WiFi не подключен. Работа без Telegram")


def main_loop():
    global last_temp, last_telegram_check, system_overheated
    
    last_temp_read = 0
    
    while True:
        current_time = time.ticks_ms()
        
  
        if temp_sensor_connected and time.ticks_diff(current_time, last_temp_read) > 2000:
            try:
                ds_sensor.convert_temp()
                time.sleep_ms(750)
                current_temp = ds_sensor.read_temp(roms[0])
                last_temp_read = current_time
                
 
                if current_temp > 70.0:
                    emergency_stop()
                    msg = "🔥 КРИТИЧЕСКИЙ ПЕРЕГРЕВ! {:.1f}°C".format(current_temp)
                    send_telegram_message(msg)
                    system_overheated = True
                
    
                if abs(current_temp - last_temp) > 5.0 and is_wifi_connected():
                    temp_msg = "🌡️ Температура: {:.1f}°C".format(current_temp)
                    send_telegram_message(temp_msg)
                    last_temp = current_temp
                    
            except Exception as e:
                print("⚠️ Ошибка чтения датчика температуры:", e)
                temp_sensor_connected = False
                if is_wifi_connected():
                    send_telegram_message("⚠️ ОШИБКА: Датчик температуры не отвежает!")
        
    
        check_buttons()
        check_sensors()
        
    
        update_gate_state()
        
    
        if is_wifi_connected() and time.ticks_diff(current_time, last_telegram_check) > 1000:
            check_telegram_commands()
            last_telegram_check = current_time
        
      
        update_status_led()
        
    
        check_serial_commands()
        
        time.sleep_ms(100)


def send_telegram_message(message):
    try:
        data = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(TELEGRAM_URL, json=data)
        response.close()
        return True
    except Exception as e:
        print("❌ Ошибка отправки Telegram:", e)
        return False

def get_telegram_updates():
    try:
        url = "https://api.telegram.org/bot{}/getUpdates".format(BOT_TOKEN)
        response = requests.get(url)
        data = json.loads(response.text)
        response.close()
        return data.get("result", [])
    except:
        return []

def check_telegram_commands():
    updates = get_telegram_updates()
    
    for update in updates:
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "").strip()
        
        if str(chat_id) == CHAT_ID and text:
            print("📱 Получена команда из Telegram:", text)
            handle_telegram_command(text)
        

def handle_telegram_command(command):
    command = command.lower().strip()
    
  
    if command in ["/open", "open", "открыть"]:
        print("Telegram: Команда ОТКРЫТЬ")
        open_gate()

    elif command in ["/close", "close", "закрыть"]:
        print("Telegram: Команда ЗАКРЫТЬ")
        close_gate()

    elif command in ["/stop", "stop", "остановить", "стоп"]:
        print("Telegram: Команда ОСТАНОВИТЬ")
        stop_gate()
    
   
    elif command in ["/temp", "temp", "температура", "т"]:
        print("Telegram: Запрос температуры")
        
        if not temp_sensor_connected:
            msg = """❌ ОШИБКА: Датчик температуры не подключен!


            send_telegram_message(msg)
        else:
            try:
                ds_sensor.convert_temp()
                time.sleep_ms(750)
                temp = ds_sensor.read_temp(roms[0])
                
                temp_msg = "🌡️ ТЕМПЕРАТУРА: {:.1f}°C\n".format(temp)
                
                if temp > 80.0:
                    temp_msg += "🔴 КРИТИЧЕСКАЯ ТЕМПЕРАТУРА!"
                elif temp > 60.0:
                    temp_msg += "🟡 ВНИМАНИЕ: Высокая температура"
                elif temp > 40.0:
                    temp_msg += "🟢 Нормальная температура"
                else:
                    temp_msg += "🔵 Низкая температура"
                
                send_telegram_message(temp_msg)
            except Exception as e:
                send_telegram_message("⚠️ ОШИБКА: Не удалось получить данные с датчика")
    
 
    elif command in ["/status", "status", "статус"]:
        print("Telegram: Запрос статуса")
        
        status = "📊 СТАТУС СИСТЕМЫ:\n"
        status += "🚪 Состояние ворот: " + get_state_string() + "\n"
        status += "🔥 Перегрев: " + ("ДА ⚠️" if system_overheated else "НЕТ ✅") + "\n"
        
        if temp_sensor_connected:
            try:
                ds_sensor.convert_temp()
                time.sleep_ms(750)
                temp = ds_sensor.read_temp(roms[0])
                status += "🌡️ Температура: {:.1f}°C\n".format(temp)
            except:
                status += "🌡️ Температура: ОШИБКА ДАТЧИКА ❌\n"
        else:
            status += "🌡️ Температура: ДАТЧИК НЕ ПОДКЛЮЧЕН ❌\n"
        
      
        wlan = network.WLAN(network.STA_IF)
        if wlan.isconnected():
            status += "📶 WiFi: Подключен\n"
        else:
            status += "📶 WiFi: Нет подключения\n"
        
        status += "⏱️ Время работы: {:.0f} мин".format(time.ticks_ms() / 60000)
        
        send_telegram_message(status)
    
 
    elif command in ["/start", "start", "/help", "help", "помощь"]:
        help_text = """🚪 УПРАВЛЕНИЕ ВОРОТАМИ


        send_telegram_message(help_text)
    
    
    elif command in ["/test", "test", "тест"]:
        send_telegram_message("🧪 ТЕСТ СИСТЕМЫ...")
        
        
        send_telegram_message("1. Тест реле...")
        RELAY_OPEN.value(1)
        time.sleep(0.3)
        RELAY_OPEN.value(0)
        time.sleep(0.3)
        RELAY_CLOSE.value(1)
        time.sleep(0.3)
        RELAY_CLOSE.value(0)
        
       
        if temp_sensor_connected:
            try:
                ds_sensor.convert_temp()
                time.sleep_ms(750)
                temp = ds_sensor.read_temp(roms[0])
                send_telegram_message("2. Температура: {:.1f}°C ✅".format(temp))
            except:
                send_telegram_message("2. Температура: ОШИБКА ❌")
        else:
            send_telegram_message("2. Температура: ДАТЧИК ОТСУТСТВУЕТ ❌")
        
      
        send_telegram_message("3. Состояние системы: " + get_state_string())
        
        send_telegram_message("✅ ТЕСТ ЗАВЕРШЕН")
    
   
    elif command in ["/reset", "reset", "сброс"]:
        global system_overheated
        system_overheated = False
        send_telegram_message("🔄 Сброс системы перегрева выполнен")
        print("Сброс системы перегрева")
    
    
    else:
        send_telegram_message("❌ Неизвестная команда\nИспользуйте: открыть, закрыть, остановить, температура, статус")


def emergency_stop():
    RELAY_OPEN.value(0)
    RELAY_CLOSE.value(0)
    RELAY_STOP.value(1)
    RELAY_ENABLE.value(0)
    global current_state
    current_state = GATE_STOPPED
    
    if is_wifi_connected():
        send_telegram_message("🛑 АВАРИЙНАЯ ОСТАНОВКА!")

def open_gate():
    if system_overheated:
        msg = "❌ ОТКРЫТИЕ НЕВОЗМОЖНО: Система перегрета!"
        print(msg)
        if is_wifi_connected():
            send_telegram_message(msg)
        return
    
    print("Открытие ворот...")
    RELAY_ENABLE.value(1)
    time.sleep(0.1)
    RELAY_STOP.value(0)
    time.sleep(0.05)
    RELAY_OPEN.value(1)
    global current_state, operation_start_time
    current_state = GATE_OPENING
    operation_start_time = time.ticks_ms()
    
    if is_wifi_connected():
        send_telegram_message("✅ ВОРОТА ОТКРЫВАЮТСЯ...")

def close_gate():
    if system_overheated:
        msg = "❌ ЗАКРЫТИЕ НЕВОЗМОЖНО: Система перегрета!"
        print(msg)
        if is_wifi_connected():
            send_telegram_message(msg)
        return
    
    print("Закрытие ворот...")
    RELAY_ENABLE.value(1)
    time.sleep(0.1)
    RELAY_STOP.value(0)
    time.sleep(0.05)
    RELAY_CLOSE.value(1)
    global current_state, operation_start_time
    current_state = GATE_CLOSING
    operation_start_time = time.ticks_ms()
    
    if is_wifi_connected():
        send_telegram_message("✅ ВОРОТА ЗАКРЫВАЮТСЯ...")

def stop_gate():
    print("Остановка ворот...")
    RELAY_OPEN.value(0)
    RELAY_CLOSE.value(0)
    RELAY_STOP.value(1)
    time.sleep(0.2)
    RELAY_ENABLE.value(0)
    global current_state
    current_state = GATE_STOPPED
    
    if is_wifi_connected():
        send_telegram_message("⏹️ ВОРОТА ОСТАНОВЛЕНЫ")


def check_sensors():
   

def check_buttons():
   

def update_gate_state():
 

def update_status_led():

    led_state = LED_STATUS.value()
    
    if current_state == GATE_CLOSED:
        LED_STATUS.value(0)
    elif current_state == GATE_OPEN:
        LED_STATUS.value(1)
    elif current_state in [GATE_OPENING, GATE_CLOSING]:
      
        LED_STATUS.value(not led_state)
        time.sleep_ms(500)  # Пауза в основном цикле
    else:
        LED_STATUS.value(0)


def get_state_string():
    states = {
        GATE_CLOSED: "ЗАКРЫТО",
        GATE_OPEN: "ОТКРЫТО",
        GATE_OPENING: "ОТКРЫВАЕТСЯ",
        GATE_CLOSING: "ЗАКРЫВАЕТСЯ",
        GATE_STOPPED: "ОСТАНОВЛЕНО"
    }
    return states.get(current_state, "НЕИЗВЕСТНО")

def beep(count):
    for i in range(count):
        BUZZER.duty(512)  # 50% заполнение
        BUZZER.freq(1000)  # 1000 Hz
        time.sleep(0.1)
        BUZZER.duty(0)
        if i < count - 1:
            time.sleep(0.1)

def is_wifi_connected():
    wlan = network.WLAN(network.STA_IF)
    return wlan.isconnected()


def check_serial_commands():
   


if __name__ == "__main__":
    setup()
    main_loop()