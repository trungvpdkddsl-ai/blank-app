import time
import requests
import threading

# Thay đổi URL này nếu ứng dụng của bạn không chạy trên cổng 8501 (Mặc định là 8501)
# Nếu bạn đang dùng Codespaces, Streamlit thường chạy trên cổng 8501.
# Địa chỉ này là địa chỉ localhost, vì chúng ta đang chạy cùng máy chủ
URL = "http://localhost:8501" 
INTERVAL_SECONDS = 300 # 5 phút = 300 giây

def ping_server():
    """Gửi yêu cầu ping đến máy chủ để giữ cho Codespace không bị ngủ."""
    while True:
        try:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Đang ping máy chủ tại {URL}...")
            response = requests.get(URL, timeout=10)
            if response.status_code == 200:
                print("Ping thành công (200 OK).")
            else:
                print(f"Cảnh báo: Ping trả về mã {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Lỗi ping: Không thể kết nối tới {URL}. {e}")
        
        # Chờ 5 phút trước khi ping tiếp
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    print(f"Dịch vụ Keep-Alive đã bắt đầu. Ping sau mỗi {INTERVAL_SECONDS} giây.")
    
    # Chạy ping_server trong một luồng riêng biệt
    ping_thread = threading.Thread(target=ping_server)
    ping_thread.daemon = True # Cho phép thread thoát khi chương trình chính kết thúc
    ping_thread.start()