import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import io
import re
from pdf2image import convert_from_bytes
from openpyxl import Workbook
from openpyxl.styles.numbers import NumberFormat

# --- 1. CÁC HÀM XỬ LÝ LOGIC NGHIỆP VỤ ---

# Ánh xạ Tên xã và Mã ĐVHC (Theo yêu cầu của bạn)
COMMUNE_MAP = {
    "thị trấn Tam Sơn": "xã Tam Sơn",
    "xã Đồng Quế": "xã Tam Sơn",
    "xã Tân Lập": "xã Tam Sơn",
    "xã Nhạo sơn": "xã Tam Sơn",
    "xã Như Thụy": "xã Tam Sơn",
    "xã Tứ Yên": "xã Sông Lô",
    "xã Đồng Thịnh": "xã Sông Lô",
    "xã Đức Bác": "xã Sông Lô",
    "xã Yên Thạch": "xã Sông Lô",
    "xã Hải Lựu": "xã Hải Lựu",
    "xã Nhân Đạo": "xã Hải Lựu",
    "xã Đôn Nhân": "xã Hải Lựu",
    "xã Phương Khoan": "xã Hải Lựu",
    "xã Quang Yên": "xã Yên Lãng",
    "xã Lãng Công": "xã Yên Lãng",
}

CODE_MAP = {
    "xã Tam Sơn": "08824",
    "xã Sông Lô": "08848",
    "xã Yên Lãng": "08773",
    "xã Hải Lựu": "08782",
}

# Danh sách cột theo thứ tự yêu cầu
FINAL_COLUMNS = [
    'A_ma_dvhc', 'B_so_phat_hanh_gcn', 'C_ngay_cap_gcn', 'D_so_vao_so_gcn',
    'E_ho_ten', 'F_nam_sinh', 'G_gioi_tinh', 'H_cccd', 'I_dia_chi_thuong_tru',
    'J_phap_nhan', 'K_vai_tro_phap_nhan', 'L_ma_dinh_danh_thua_dat',
    'M_so_to_ban_do_gcn', 'N_so_thua_dat_gcn', 'O_so_hieu_bd_dc',
    'P_so_thua_bd_dc', 'Q_dia_chi_thua_dat', 'R_dien_tich_thua_dat',
    'S_loai_dat_1', 'T_dien_tich_1', 'U_nguon_goc_1', 'V_hinh_thuc_1', 'W_thoi_han_1',
    'X_loai_dat_2', 'Y_dien_tich_2', 'Z_nguon_goc_2', 'AA_hinh_thuc_2', 'BB_thoi_han_2'
]

COLUMN_NAMES_VI = {
    'A_ma_dvhc': 'Mã ĐVHC cấp xã',
    'B_so_phat_hanh_gcn': 'Số phát hành GCN',
    'C_ngay_cap_gcn': 'Ngày cấp GCN',
    'D_so_vao_so_gcn': 'Số vào sổ GCN',
    'E_ho_ten': 'Họ tên chủ sử dụng đất',
    'F_nam_sinh': 'Năm sinh',
    'G_gioi_tinh': 'Giới tính',
    'H_cccd': 'CCCD',
    'I_dia_chi_thuong_tru': 'Địa chỉ thường trú',
    'J_phap_nhan': 'Pháp nhân trên GCN',
    'K_vai_tro_phap_nhan': 'Vai trò pháp nhân',
    'L_ma_dinh_danh_thua_dat': 'Mã định danh thửa đất',
    'M_so_to_ban_do_gcn': 'Số tờ bản đồ GCN',
    'N_so_thua_dat_gcn': 'Số thứ tự thửa GCN',
    'O_so_hieu_bd_dc': 'Số hiệu tờ bản đồ ĐC',
    'P_so_thua_bd_dc': 'Số thứ tự thửa trên BĐ ĐC',
    'Q_dia_chi_thua_dat': 'Địa chỉ thửa đất',
    'R_dien_tich_thua_dat': 'Diện tích thửa đất',
    'S_loai_dat_1': 'Loại đất 1',
    'T_dien_tich_1': 'Diện tích 1',
    'U_nguon_goc_1': 'Nguồn gốc SD 1',
    'V_hinh_thuc_1': 'Hình thức SD 1',
    'W_thoi_han_1': 'Thời hạn SD 1',
    'X_loai_dat_2': 'Loại đất 2',
    'Y_dien_tich_2': 'Diện tích 2',
    'Z_nguon_goc_2': 'Nguồn gốc SD 2',
    'AA_hinh_thuc_2': 'Hình thức SD 2',
    'BB_thoi_han_2': 'Thời hạn SD 2'
}

def get_gemini_model(api_key):
    """Khởi tạo và trả về mô hình Gemini."""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro-latest')
        return model
    except Exception as e:
        st.error(f"Lỗi khởi tạo mô hình Gemini: {e}")
        return None

def extract_information(model, images):
    """
    Gửi ảnh đến Gemini và yêu cầu trích xuất thông tin dưới dạng JSON.
    """
    prompt = """
    Bạn là một trợ lý OCR chuyên nghiệp, chuyên trích xuất thông tin từ Giấy chứng nhận quyền sử dụng đất (GCN) của Việt Nam.
    Hãy phân tích (các) hình ảnh sau và trả về thông tin dưới dạng một đối tượng JSON.

    QUAN TRỌNG:
    1. Trích xuất TẤT CẢ tên chủ sở hữu.
    2. Nếu có nhiều chủ sở hữu, hãy trả về `chu_su_dung`, `nam_sinh`, `gioi_tinh`, `cccd` dưới dạng danh sách (array) theo đúng thứ tự.
    3. Nếu chỉ có 1 chủ sở hữu, vẫn trả về dưới dạng danh sách 1 phần tử.
    4. Giới tính chỉ ghi "Nam" hoặc "Nữ".
    5. Ngày cấp GCN trả về định dạng "DD/MM/YYYY" hoặc "MM YYYY".
    
    Cấu trúc JSON bắt buộc:
    {
      "so_phat_hanh_gcn": "...",
      "ngay_cap_gcn": "...",
      "so_vao_so_gcn": "...",
      "chu_su_dung": ["Tên người 1", "Tên người 2"],
      "nam_sinh": ["Năm sinh 1", "Năm sinh 2"],
      "gioi_tinh": ["Nam", "Nữ"],
      "cccd": ["CCCD 1", "CCCD 2"],
      "dia_chi_thuong_tru": "...",
      "ma_dinh_danh_thua_dat": "...",
      "so_to_ban_do_gcn": "...",
      "so_thua_dat_gcn": "...",
      "dia_chi_thua_dat": "...",
      "dien_tich_thua_dat": "...",
      "dat_1_loai": "...",
      "dat_1_dien_tich": "...",
      "dat_1_nguon_goc": "...",
      "dat_1_hinh_thuc": "...",
      "dat_1_thoi_han": "...",
      "dat_2_loai": "...",
      "dat_2_dien_tich": "...",
      "dat_2_nguon_goc": "...",
      "dat_2_hinh_thuc": "...",
      "dat_2_thoi_han": "..."
    }
    """
    
    # Tạo nội dung gửi đi bao gồm prompt và (các) ảnh
    content = [prompt] + images
    
    try:
        response = model.generate_content(content)
        raw_text = response.text
        
        # --- CẬP NHẬT QUAN TRỌNG ---
        # Tìm khối JSON đầu tiên trong phản hồi.
        # AI có thể trả về văn bản giới thiệu (ví dụ: "Chắc chắn rồi...")
        # nên chúng ta cần tìm đúng đoạn bắt đầu bằng { và kết thúc bằng }
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        
        if json_match:
            cleaned_text = json_match.group(0)
            # Loại bỏ 'cite:' nếu có
            cleaned_text = re.sub(r'cite:', '', cleaned_text).strip()
            return cleaned_text
        else:
            # Nếu không tìm thấy JSON, báo lỗi
            st.error(f"Không tìm thấy khối JSON hợp lệ trong phản hồi của AI. Phản hồi thô: {raw_text}")
            return None
            
    except Exception as e:
        st.error(f"Lỗi khi gọi API Gemini: {e}")
        st.error(f"Phản hồi thô từ API (nếu có): {getattr(e, 'response', 'Không có')}")
        return None

def find_commune_code(address_str):
    """Tìm mã ĐVHC dựa trên địa chỉ đã chuẩn hóa."""
    if not isinstance(address_str, str):
        return None
    for commune, code in CODE_MAP.items():
        if commune in address_str:
            return code
    return None

def normalize_address(address_str):
    """Chuẩn hóa địa chỉ theo quy tắc."""
    if not isinstance(address_str, str):
        return address_str
    
    address = address_str
    # 1. Ánh xạ các xã
    for old, new in COMMUNE_MAP.items():
        address = address.replace(old, new)
        
    # 2. Bỏ "huyện Sông Lô"
    address = address.replace("huyện Sông Lô", "")
    
    # 3. Đổi tỉnh
    address = address.replace("tỉnh Vĩnh Phúc", "tỉnh Phú Thọ")
    
    # Dọn dẹp dấu phẩy thừa
    address = re.sub(r', ,', ',', address).strip().strip(',')
    return address

def fill_nguon_goc(loai_dat, nguon_goc_goc):
    """Điền nguồn gốc sử dụng đất nếu trống."""
    if pd.isna(nguon_goc_goc) or nguon_goc_goc == "":
        if pd.isna(loai_dat):
            return None
        loai_dat = str(loai_dat).lower()
        if "đất ở" in loai_dat:
            return "Công nhận QSDĐ như giao đất có thu tiền sử dụng đất"
        if "đất vườn" in loai_dat or "cây lâu năm" in loai_dat:
            return "Công nhận QSDĐ như giao đất không thu tiền sử dụng đất"
    return nguon_goc_goc

def fill_hinh_thuc(phap_nhan, hinh_thuc_goc):
    """Điền hình thức sử dụng đất nếu trống."""
    if pd.isna(hinh_thuc_goc) or hinh_thuc_goc == "":
        if phap_nhan == "cá nhân":
            return "Sử dụng riêng"
        if phap_nhan in ["vợ chồng", "hộ gia đình"]:
            return "Sử dụng chung"
    return hinh_thuc_goc

def process_gemini_output(json_list):
    """
    Chuyển đổi danh sách JSON thô từ Gemini thành DataFrame đã qua xử lý.
    Đây là nơi áp dụng TẤT CẢ các quy tắc nghiệp vụ.
    """
    all_rows = []
    
    for data in json_list:
        if not data:
            continue
            
        try:
            # --- BẮT ĐẦU SỬA LỖI ---
            # Ép kiểu dữ liệu để đảm bảo là danh sách
            chu_su_dung_val = data.get('chu_su_dung', [])
            
            if chu_su_dung_val is None:
                chu_su_dung_val = [] 
            elif not isinstance(chu_su_dung_val, list):
                chu_su_dung_val = [chu_su_dung_val] 
                
            data['chu_su_dung'] = chu_su_dung_val 
            # ĐẢM BẢO num_owners 100% LÀ SỐ NGUYÊN (int)
            num_owners = int(len(chu_su_dung_val))
            
            # Bảo vệ các trường danh sách khác (nam_sinh, gioi_tinh, cccd)
            for key in ['nam_sinh', 'gioi_tinh', 'cccd']:
                key_val = data.get(key, [])
                if key_val is None:
                    key_val = []
                elif not isinstance(key_val, list):
                    key_val = [key_val]
                
                # Đảm bảo các list này có cùng độ dài
                if len(key_val) < num_owners:
                    # ĐẢM BẢO SỐ LƯỢNG CẦN THÊM 100% LÀ SỐ NGUYÊN (int)
                    padding_needed = int(num_owners - len(key_val))
                    key_val.extend([None] * padding_needed)
                
                data[key] = key_val 
            # --- KẾT THÚC SỬA LỖI ---

            # Quy tắc 12: Xác định Pháp nhân (Cột J)
            j_phap_nhan = "cá nhân" 
            if num_owners == 2:
                j_phap_nhan = "vợ chồng"
            elif num_owners > 2:
                j_phap_nhan = "hộ gia đình"
                
            # Vòng lặp này bây giờ đã an toàn vì num_owners là int
            for i in range(num_owners):
                # Quy tắc 13: Xác định Vai trò pháp nhân (Cột K)
                k_vai_tro = None
                gioi_tinh = data['gioi_tinh'][i] if i < len(data['gioi_tinh']) else None
                
                if j_phap_nhan == "cá nhân":
                    k_vai_tro = "cá nhân"
                elif j_phap_nhan == "hộ gia đình":
                    k_vai_tro = "chủ hộ" 
                elif j_phap_nhan == "vợ chồng":
                    if gioi_tinh == "Nữ":
                        k_vai_tro = "vợ"
                    elif gioi_tinh == "Nam":
                        k_vai_tro = "chồng"
                        
                # Quy tắc 15: Xử lý "và vợ" -> "bà"
                ho_ten = data['chu_su_dung'][i] if i < len(data['chu_su_dung']) else None
                if ho_ten and "và vợ" in ho_ten:
                    ho_ten = "bà" 

                # Quy tắc 7: Thêm số 0 vào CCCD
                cccd = data['cccd'][i] if i < len(data['cccd']) else None
                if cccd and not str(cccd).startswith('0'):
                    cccd = '0' + str(cccd)
                    
                # Quy tắc 15: Chuẩn hóa ngày cấp
                ngay_cap = data.get('ngay_cap_gcn')
                if ngay_cap and ' ' in ngay_cap:
                    ngay_cap = ngay_cap.replace(' ', '/')
                    
                # Quy tắc 15: Bỏ dấu . ở số vào sổ
                so_vao_so = data.get('so_vao_so_gcn')
                if so_vao_so:
                    so_vao_so = str(so_vao_so).replace('.', '')

                row = {
                    'B_so_phat_hanh_gcn': data.get('so_phat_hanh_gcn'),
                    'C_ngay_cap_gcn': ngay_cap,
                    'D_so_vao_so_gcn': so_vao_so,
                    'E_ho_ten': ho_ten,
                    'F_nam_sinh': data['nam_sinh'][i] if i < len(data['nam_sinh']) else None,
                    'G_gioi_tinh': gioi_tinh,
                    'H_cccd': cccd,
                    'I_dia_chi_thuong_tru': data.get('dia_chi_thuong_tru'),
                    'J_phap_nhan': j_phap_nhan,
                    'K_vai_tro_phap_nhan': k_vai_tro,
                    'L_ma_dinh_danh_thua_dat': data.get('ma_dinh_danh_thua_dat'),
                    'M_so_to_ban_do_gcn': data.get('so_to_ban_do_gcn'),
                    'N_so_thua_dat_gcn': data.get('so_thua_dat_gcn'),
                    'Q_dia_chi_thua_dat': data.get('dia_chi_thua_dat'),
                    'R_dien_tich_thua_dat': data.get('dien_tich_thua_dat'),
                    'S_loai_dat_1': data.get('dat_1_loai'),
                    'T_dien_tich_1': data.get('dat_1_dien_tich'),
                    'U_nguon_goc_1': data.get('dat_1_nguon_goc'),
                    'V_hinh_thuc_1': data.get('dat_1_hinh_thuc'),
                    'W_thoi_han_1': data.get('dat_1_thoi_han'),
                    'X_loai_dat_2': data.get('dat_2_loai'),
                    'Y_dien_tich_2': data.get('dat_2_dien_tich'),
                    'Z_nguon_goc_2': data.get('dat_2_nguon_goc'),
                    'AA_hinh_thuc_2': data.get('dat_2_hinh_thuc'),
                    'BB_thoi_han_2': data.get('dat_2_thoi_han')
                }
                all_rows.append(row)
                
        except Exception as e:
            st.warning(f"Lỗi khi xử lý dữ liệu JSON: {e}. Dữ liệu thô: {data}")
            import traceback
            traceback.print_exc()

    if not all_rows:
        return pd.DataFrame(columns=FINAL_COLUMNS)

    df = pd.DataFrame(all_rows)
    
    # --- ÁP DỤNG CÁC QUY TẮC SAU KHI TẠO DF ---

    for col in FINAL_COLUMNS:
        if col not in df.columns:
            df[col] = None
            
    df['Q_dia_chi_thua_dat'] = df['Q_dia_chi_thua_dat'].apply(normalize_address)
    df['A_ma_dvhc'] = df['Q_dia_chi_thua_dat'].apply(find_commune_code)
    df['I_dia_chi_thuong_tru'] = df['I_dia_chi_thuong_tru'].fillna(df['Q_dia_chi_thua_dat'])
    df['S_loai_dat_1'] = df['S_loai_dat_1'].fillna("Đất ở tại nông thôn")
    df['O_so_hieu_bd_dc'] = df['M_so_to_ban_do_gcn']
    df['P_so_thua_bd_dc'] = df['N_so_thua_dat_gcn']
    df['U_nguon_goc_1'] = df.apply(lambda row: fill_nguon_goc(row['S_loai_dat_1'], row['U_nguon_goc_1']), axis=1)
    df['Z_nguon_goc_2'] = df.apply(lambda row: fill_nguon_goc(row['X_loai_dat_2'], row['Z_nguon_goc_2']), axis=1)
    df['V_hinh_thuc_1'] = df.apply(lambda row: fill_hinh_thuc(row['J_phap_nhan'], row['V_hinh_thuc_1']), axis=1)
    df['AA_hinh_thuc_2'] = df.apply(lambda row: fill_hinh_thuc(row['J_phap_nhan'], row['AA_hinh_thuc_2']), axis=1)
    df = df.replace("cite:", "", regex=True)
    df = df[FINAL_COLUMNS]
    df = df.rename(columns=COLUMN_NAMES_VI)
    
    return df

def to_excel(df):
    """Xuất DataFrame ra file Excel (dưới dạng bytes) với định dạng CCCD là Text."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='KetQuaTrichXuat')
        
        # Lấy workbook và worksheet
        workbook = writer.book
        worksheet = writer.sheets['KetQuaTrichXuat']
        
        # Tìm cột CCCD (tên tiếng Việt)
        cccd_col_index = None
        for i, col_name in enumerate(df.columns):
            if col_name == 'CCCD':
                cccd_col_index = i + 1 # openpyxl index bắt đầu từ 1
                break
        
        # Quy tắc 15: Định dạng cột CCCD là Text
        if cccd_col_index:
            col_letter = chr(ord('A') + cccd_col_index - 1)
            text_format = NumberFormat('@')
            
            # Áp dụng định dạng cho tất cả các ô trong cột (trừ header)
            for cell in worksheet[col_letter][1:]:
                cell.number_format = text_format
                
    processed_data = output.getvalue()
    return processed_data

# --- 2. GIAO DIỆN NGƯỜI DÙNG (STREAMLIT) ---

st.set_page_config(layout="wide")
st.title("📄 Trình trích xuất thông tin GCN của Anh Trung Đẹp Trai")
st.write("Ứng dụng này upload file PDF/Ảnh GCN, dùng AI để đọc và áp dụng các quy tắc nghiệp vụ của anh Trung đã định nghĩa, vui lòng mời a cốc bia để sử dụng phần mềm.")

# Nhập API Key
api_key = st.text_input("Nhập Google AI Studio API Key của bạn:", type="password")

uploaded_files = st.file_uploader(
    "Tải lên file GCN (PDF, PNG, JPG)",
    type=["pdf", "png", "jpg", "jpeg"],
    accept_multiple_files=True
)

if st.button("🚀 Bắt đầu xử lý"):
    if not api_key:
        st.error("Vui lòng nhập API Key của Gemini.")
    elif not uploaded_files:
        st.error("Vui lòng tải lên ít nhất một file.")
    else:
        model = get_gemini_model(api_key)
        if model:
            all_json_results = []
            progress_bar = st.progress(0)
            
            for i, uploaded_file in enumerate(uploaded_files):
                st.info(f"Đang xử lý file: {uploaded_file.name}...")
                
                # Chuyển file sang dạng ảnh PIL
                images = []
                try:
                    if uploaded_file.type == "application/pdf":
                        # Chuyển PDF sang danh sách ảnh
                        images = convert_from_bytes(uploaded_file.read(), poppler_path="/usr/bin/")
                    else:
                        # File ảnh
                        images = [Image.open(uploaded_file)]
                except Exception as e:
                    st.error(f"Lỗi khi đọc file {uploaded_file.name}: {e}")
                    continue
                    
                # Gọi Gemini
                json_str = extract_information(model, images)
                
                if json_str:
                    try:
                        # Chuyển đổi chuỗi JSON thành đối tượng Python
                        json_data = pd.read_json(io.StringIO(json_str), typ='series').to_dict()
                        all_json_results.append(json_data)
                        st.success(f"Trích xuất thành công: {uploaded_file.name}")
                    except Exception as e:
                        st.error(f"Lỗi khi phân tích JSON từ file {uploaded_file.name}: {e}")
                        st.text_area("Dữ liệu JSON thô (lỗi)", json_str)
                        
                progress_bar.progress((i + 1) / len(uploaded_files))

            if all_json_results:
                st.header("🔄 Đang áp dụng quy tắc nghiệp vụ...")
                try:
                    # Bước quan trọng: Xử lý toàn bộ dữ liệu
                    final_df = process_gemini_output(all_json_results)
                    
                    st.header("✅ Hoàn tất! Xem trước kết quả:")
                    st.dataframe(final_df)
                    
                    # Tạo file Excel để tải về
                    excel_data = to_excel(final_df)
                    
                    st.download_button(
                        label="📥 Tải về file Excel kết quả",
                        data=excel_data,
                        file_name="KetQua_TrichXuat_GCN.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except Exception as e:
                    st.error(f"Lỗi nghiêm trọng khi áp dụng quy tắc nghiệp vụ: {e}")