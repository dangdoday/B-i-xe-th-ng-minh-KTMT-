import RPi.GPIO as GPIO
import cv2
import time
import spidev
import os
import random

# Cấu hình GPIO và các thông số
LCD_PINS = {'RS': 23, 'E': 27, 'D4': 18, 'D5': 17, 'D6': 14, 'D7': 3, 'BL': 2}
BTS = {"BT1": 21, "BT2": 26}
SERVO_PIN = 6
TRIG_PIN = 15
ECHO_PIN = 4
SAVE_PATH = "captured_images"  # Thư mục lưu ảnh
LCD_WIDTH = 16
LCD_CHR = True
LCD_CMD = False
E_PULSE = 0.0005
E_DELAY = 0.0005
LCD_LINE_1 = 0x80
LCD_LINE_2 = 0xC0
# dong co dc
PWM_PIN = 24  # Chân GPIO cho tín hiệu PWM (Điều khiển tốc độ động cơ)
DIR_PIN = 25  # Chân GPIO cho tín hiệu điều khiển hướng động cơ
# Cấu hình các chân relay và cảm biến ánh sáng
RELAY_1 = 12  # Relay 1 điều khiển thiết bị đầu tiên
RELAY_2 = 16  # Relay 2 điều khiển thiết bị thứ hai
LIGHT_SS = 5  # Cảm biến ánh sáng gắn vào chân GPIO 5

# Khởi tạo SPI cho LED matrix
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1000000
spi.mode = 0x00

# Biến toàn cục
parking_lot = [0xFF] * 8
total_slots = 64
car_images = {}  # Lưu thông tin ảnh ứng với vị trí xe
car_positions = {}  # Lưu thông tin xe theo vị trí (vị trí: ID xe)
entered_cars = []  # Lưu thứ tự xe đã vào bãi
available_slots = total_slots  # Số chỗ trống ban đầu
# Khởi tạo GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(BTS["BT1"], GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(BTS["BT2"], GPIO.IN, pull_up_down=GPIO.PUD_UP)
# Cấu hình các chân của cảm biến khoảng cách
GPIO.setup(TRIG_PIN, GPIO.OUT)
GPIO.setup(ECHO_PIN, GPIO.IN)
# cau hinh dong co dc
GPIO.setup(PWM_PIN, GPIO.OUT)
GPIO.setup(DIR_PIN, GPIO.OUT)
# Cấu hình chế độ và trạng thái ban đầu cho các chân relay và cảm biến ánh sáng
GPIO.setup(RELAY_1, GPIO.OUT)  # Cấu hình Relay 1 là đầu ra
GPIO.setup(RELAY_2, GPIO.OUT)  # Cấu hình Relay 2 là đầu ra
GPIO.setup(LIGHT_SS, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Cảm biến ánh sáng là đầu vào, kéo lên mức cao mặc định

# Khởi tạo tín hiệu PWM với tần số 1000Hz
pwm = GPIO.PWM(PWM_PIN, 1000)
pwm.start(0)  # Bắt đầu PWM với độ rộng xung ban đầu là 0%
speed = 50 # Tốc độ động cơ
# Cau hinh cong Servo
GPIO.setup(SERVO_PIN, GPIO.OUT)  # Dong co Servo
servo = GPIO.PWM(SERVO_PIN, 50)  # PWM cho Servo voi tan so 50Hz
servo.start(0)  # Bat dau voi chu ky 0 (cong ban dau dong)
# Đặt trạng thái ban đầu cho chân DIR_PIN
GPIO.output(DIR_PIN, 0)  # Hướng động cơ mặc định (không có tín hiệu)

# Hàm điều khiển động cơ (tốc độ và hướng)
def motor_control(speed, direction):
    GPIO.output(DIR_PIN, direction)  # Điều khiển hướng động cơ
    if direction == 0:  # Nếu hướng là tiến
        speed = speed  # Tốc độ giữ nguyên
    else:  # Nếu hướng là lùi
        speed = 100 - speed  # Đảo ngược tốc độ
    pwm.ChangeDutyCycle(speed)  # Cập nhật độ rộng xung PWM để điều chỉnh tốc độ động cơ

# Tạo thư mục lưu ảnh nếu chưa tồn tại
if not os.path.exists(SAVE_PATH):
    os.makedirs(SAVE_PATH)

# Hàm điều khiển servo
def move_servo(angle):
    duty_cycle = 2 + (angle / 18)
    servo.ChangeDutyCycle(duty_cycle)
    time.sleep(0.5)
    servo.ChangeDutyCycle(0)

# Mở và đóng cổng
def open_gate():
    move_servo(90)

def close_gate():
    move_servo(0)

# Gửi dữ liệu đến LED matrix
def max7219_write(register, data):
    spi.xfer2([register, data])

# Khởi tạo LED matrix
def max7219_init():
    max7219_write(0x0C, 0x01)  # Bật LED
    max7219_write(0x0B, 0x07)  # Giới hạn quét = 8 hàng
    max7219_write(0x09, 0x00)  # Không sử dụng giải mã
    max7219_write(0x0A, 0x0F)  # Độ sáng tối đa
    max7219_write(0x0F, 0x00)  # Thoát chế độ test

# Cập nhật LED matrix
def update_matrix():
    for row in range(8):
        max7219_write(row + 1, parking_lot[row])

# Khoi tao man hinh LCD
def lcd_init():
    for pin in LCD_PINS.values():
        GPIO.setup(pin, GPIO.OUT)
    for byte in [0x33, 0x32, 0x28, 0x0C, 0x06, 0x01]:
        lcd_byte(byte, LCD_CMD)
    GPIO.output(LCD_PINS["BL"], True)

# Ham xoa LCD
def lcd_clear():
    lcd_byte(0x01, LCD_CMD)

# Ham gui byte lenh hoac du lieu den LCD
def lcd_byte(bits, mode):
    GPIO.output(LCD_PINS['RS'], mode)
    for bit_num in range(4):
        GPIO.output(LCD_PINS[f'D{bit_num + 4}'], bits & (1 << (4 + bit_num)) != 0)
    time.sleep(E_DELAY)
    GPIO.output(LCD_PINS['E'], True)
    time.sleep(E_PULSE)
    GPIO.output(LCD_PINS['E'], False)
    time.sleep(E_DELAY)
    for bit_num in range(4):
        GPIO.output(LCD_PINS[f'D{bit_num + 4}'], bits & (1 << bit_num) != 0)
    time.sleep(E_DELAY)
    GPIO.output(LCD_PINS['E'], True)
    time.sleep(E_PULSE)
    GPIO.output(LCD_PINS['E'], False)
    time.sleep(E_DELAY)
# Ham hien thi chuoi len LCD
def lcd_display_string(message, line):
    lcd_byte(LCD_LINE_1 if line == 1 else LCD_LINE_2, LCD_CMD)
    for char in message:
        lcd_byte(ord(char), LCD_CHR)
# Tạo ID ngẫu nhiên cho xe
def generate_car_id():
    return f"CAR-{random.randint(1000, 9999)}"
# Cập nhật LED matrix tại vị trí xe
def update_led_for_slot(row, col, state):
    if state:  # 1: Chỗ trống
        parking_lot[row] |= (1 << (7 - col))
    else:  # 0: Có xe
        parking_lot[row] &= ~(1 << (7 - col))
    update_matrix()
# Ham cap nhat so luong cho trong hien thi tren LCD
def update_lcd(available_slots):
    lcd_clear()
    message = f"Available: {available_slots}"
    lcd_display_string(message, 1)
    if available_slots == 0:
        lcd_display_string("Bai da day", 2)  # Thông báo ở dòng 2 khi hết chỗ
    elif available_slots == 64:
        lcd_display_string("Khong co xe", 2)
    else:
        lcd_display_string("Bai con cho", 2)  # Xóa dòng 2 nếu còn chỗ trống

# Đo khoảng cách từ cảm biến siêu âm
def measure_distance():
    GPIO.output(TRIG_PIN, False)
    time.sleep(0.2)
    GPIO.output(TRIG_PIN, True)
    time.sleep(0.00001)
    GPIO.output(TRIG_PIN, False)
    pulse_start=time.time()
    pulse_end = pulse_start

    while GPIO.input(ECHO_PIN) == 0:
        pulse_start = time.time()
    while GPIO.input(ECHO_PIN) == 1:
        pulse_end = time.time()

    pulse_duration = pulse_end - pulse_start
    distance = pulse_duration * 17150
    return round(distance, 2)

# Chụp ảnh và lưu vào thư mục
def capture_image(slot):
    capture = cv2.VideoCapture(0)
    if not capture.isOpened():
        print("Cannot open camera")
        return False
    ret, frame = capture.read()
    if ret:
        filename = os.path.join(SAVE_PATH, f"car_slot_{slot}.jpg")
        cv2.imwrite(filename, frame)
        car_images[slot] = filename  # Lưu tên file ứng với vị trí xe
        print(f"Image saved as {filename}")
    capture.release()
    cv2.destroyAllWindows()

# Xóa ảnh khi xe rời khỏi vị trí
def delete_image(slot):
    if slot in car_images:
        try:
            os.remove(car_images[slot])
            print(f"Deleted image: {car_images[slot]}")
            del car_images[slot]
        except FileNotFoundError:
            print(f"File not found: {car_images[slot]}")


# Hàm cho xe vào bãi
def car_enter():
    global available_slots
    if available_slots == 0:
        print("Bãi đã đầy!")
        return
    distance = measure_distance()
    if distance < 10:  # Kiểm tra xe ở gần
        for row in range(8):
            for col in range(8):
                if parking_lot[row] & (1 << (7 - col)):  # Tìm vị trí trống
                    slot = row * 8 + col
                    car_id = generate_car_id()  # Sinh ID ngẫu nhiên
                    car_positions[slot] = car_id  # Lưu ID xe vào vị trí
                    entered_cars.append((slot, car_id))  # Lưu xe vào danh sách thứ tự
                    capture_image(slot)  # Chụp ảnh xe
                    available_slots -= 1
                    update_led_for_slot(row, col, 0)  # Cập nhật LED matrix
                    update_lcd(available_slots)  # Cập nhật LCD
                    open_gate()
                    motor_control(speed, 0)
                    time.sleep(2)
                    motor_control(0, 0)
                    close_gate()
                    print(f"Xe {car_id} vào vị trí {slot}")
                    return

# Hàm cho xe rời bãi ngẫu nhiên từ danh sách đã vào
def car_exit():
    global available_slots
    if available_slots == total_slots:
        print("Bãi trống!")
        return
    if entered_cars:
        random_index = random.randint(0, len(entered_cars) - 1)  # Chọn ngẫu nhiên xe
        slot, car_id = entered_cars.pop(random_index)  # Lấy thông tin xe và xóa khỏi danh sách
        car_positions.pop(slot, None)  # Xóa xe khỏi danh sách vị trí
        row, col = divmod(slot, 8)
        delete_image(slot)  # Xóa ảnh xe
        available_slots += 1
        update_led_for_slot(row, col, 1)  # Cập nhật LED matrix (bật đèn vị trí này)
        update_lcd(available_slots)  # Cập nhật LCD
        open_gate()
        motor_control(speed, 1)
        time.sleep(2)
        motor_control(0, 1)
        close_gate()
        print(f"Xe {car_id} rời vị trí {slot}")
# Chương trình chính
def main():
    max7219_init()  # Khởi tạo LED matrix
    update_matrix()
    lcd_init()  # Khởi tạo màn hình LCD
    GPIO.setup(LIGHT_SS, GPIO.IN, GPIO.PUD_UP)  # Cấu hình cảm biến ánh sáng
    try:
        while True:

            if GPIO.input(LIGHT_SS) == 0:  # Kiểm tra nếu môi trường sáng (cảm biến ở mức thấp)
                GPIO.output(RELAY_1, GPIO.LOW)  # Tắt Relay 1
                GPIO.output(RELAY_2, GPIO.LOW)  # Tắt Relay 2
            else:  # Nếu môi trường tối (cảm biến ở mức cao)
                GPIO.output(RELAY_1, GPIO.HIGH)  # Bật Relay 1
                time.sleep(1)  # Chờ 1 giây
                GPIO.output(RELAY_2, GPIO.HIGH)  # Bật Relay 2

            if GPIO.input(BTS["BT1"]) == GPIO.LOW:
                car_enter()
            elif GPIO.input(BTS["BT2"]) == GPIO.LOW:
                car_exit()
            time.sleep(0.1)
    except KeyboardInterrupt:
        GPIO.setmode(GPIO.BCM)  # Đặt lại chế độ đánh số chân GPIO
        servo.stop()
        lcd_clear()
        GPIO.cleanup()
        max7219_write(0x0C, 0x00)  # Tắt LED matrix
        spi.close()
if __name__ == "__main__":
    main()
