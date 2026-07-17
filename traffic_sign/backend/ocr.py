import easyocr
import cv2

reader = easyocr.Reader(['en'], gpu=True)
print("GPU HERE:", reader.device)

def read_speed_sign(image):

    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # enlarge image
        gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

        # improve contrast
        gray = cv2.equalizeHist(gray)

        # reduce noise
        gray = cv2.GaussianBlur(gray, (5,5), 0)

        # threshold
        _, thresh = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)

        results = reader.readtext(
            thresh,
            allowlist="0123456789"
        )

        best_speed = None
        best_conf = 0

        for bbox, text, conf in results:

            text = text.strip()

            print("OCR RAW:", text)

            if text.isdigit():

                speed = int(text)

                if conf > best_conf:
                    best_conf = conf
                    best_speed = speed

        return best_speed, best_conf

    except Exception as e:
        print("OCR error:", e)
        return None, 0