from PIL import ImageFont, ImageDraw, Image
import numpy as np
import pytesseract
import cv2

# Đường dẫn ảnh biển số
img = cv2.imread('3.jpg')
img = cv2.resize(img, (800, 600))  # Resize để tăng hiệu suất xử lý

# Đường dẫn font chữ
fontpath = "/arial.ttf"
font = ImageFont.truetype(fontpath, 32)
b, g, r, a = 0, 255, 0, 0

# Tiền xử lý ảnh
grayscale = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
blurred = cv2.GaussianBlur(grayscale, (5, 5), 0)
edged = cv2.Canny(blurred, 10, 200)

# Tìm các contours
contours, _ = cv2.findContours(edged, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
contours = sorted(contours, key=cv2.contourArea, reverse=True)

# Tỷ lệ khung hình và diện tích
aspect_ratios = [(1.2, 1.5), (1.9, 2.2), (4.5, 5.0)]  # Tỷ lệ khung hình xe máy, ô tô loại 1, loại 2
min_area = 4000  # Diện tích tối thiểu
max_area = 50000  # Diện tích tối đa

number_plate_shape = None
for c in contours:
    area = cv2.contourArea(c)
    if min_area < area < max_area:
        # Xác định hình chữ nhật bao quanh
        x, y, w, h = cv2.boundingRect(c)
        aspect_ratio = w / h
        if any(lower <= aspect_ratio <= upper for lower, upper in aspect_ratios):
            perimeter = cv2.arcLength(c, True)
            approximation = cv2.approxPolyDP(c, 0.02 * perimeter, True)
            if len(approximation) == 4:  # Chỉ lấy hình chữ nhật
                number_plate_shape = approximation
                break

# Nếu tìm thấy biển số
if number_plate_shape is not None:
    x, y, w, h = cv2.boundingRect(number_plate_shape)
    number_plate = grayscale[y:y + h, x:x + w]  # Cắt vùng biển số

    # OCR bằng Tesseract để nhận diện biển số
    custom_config = r'--oem 3 --psm 8'  # Tham số để Tesseract nhận diện tốt hơn (OEM: 3 cho LSTM OCR, PSM: 8 cho văn bản đơn lẻ)
    detected_text = pytesseract.image_to_string(number_plate, config=custom_config)

    if len(detected_text.strip()) == 0:
        text = "Không thấy bảng số xe"
        img_pil = Image.fromarray(img)
        draw = ImageDraw.Draw(img_pil)
        draw.text((150, 500), text, font=font, fill=(b, g, r, a))
        img = np.array(img_pil)
    else:
        cv2.drawContours(img, [number_plate_shape], -1, (255, 0, 0), 3)

        # Hậu xử lý kết quả nhận diện
        processed_text = ''.join([char for char in detected_text if char.isalnum() or char in ['-', '.']])
        processed_text = processed_text.upper().replace('G', '9').replace('O', '0')  # Chuyển thành in hoa và sửa lỗi

        # Sửa lỗi nhầm lẫn A và 4
        processed_text = processed_text.replace('A', '4')

        # Hiển thị kết quả nhận diện
        final_text = "Biển số: " + processed_text

        img_pil = Image.fromarray(img)
        draw = ImageDraw.Draw(img_pil)
        draw.text((200, 500), final_text, font=font, fill=(b, g, r, a))
        img = np.array(img_pil)

    cv2.imshow('Plate Detection', img)
    cv2.waitKey(0)
else:
    print("Không tìm thấy vùng biển số")
