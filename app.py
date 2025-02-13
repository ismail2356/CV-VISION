from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import os
from dotenv import load_dotenv
from PIL import Image
import io
import json
import fitz  # PyMuPDF için
import tempfile
import base64

load_dotenv()

app = Flask(__name__)

# Google Gemini API anahtarını yükle
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))

# Görüntü analizi için model
vision_model = genai.GenerativeModel('gemini-1.5-flash')

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

def extract_text_from_pdf(pdf_bytes):
    # PDF'i geçici dosyaya kaydet
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
        tmp_file.write(pdf_bytes)
        tmp_path = tmp_file.name

    try:
        # PDF'i aç
        pdf_document = fitz.open(tmp_path)
        
        # İlk sayfayı görüntü olarak al (CV genelde tek sayfa)
        page = pdf_document[0]
        pix = page.get_pixmap()
        img_data = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_data))
        
        # Resmi base64'e çevir
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        try:
            # Görüntüyü analiz et
            vision_response = vision_model.generate_content([
                """This is a CV image. Please extract the following information in JSON format:
                {
                    "ad": "First name",
                    "soyad": "Last name",
                    "dogum_tarihi": "Date of birth in DD.MM.YYYY format",
                    "tc_no": "ID number (if available)",
                    "yabanci_dil": "Known languages",
                    "telefon": "Phone number",
                    "email": "Email address",
                    "universite": "University name",
                    "fakulte": "Faculty name",
                    "bolum": "Department name",
                    "egitim_seviyesi": "Education level (Bachelor's/Master's/PhD etc.)",
                    "sinif": "Current year/grade",
                    "linkedin": "LinkedIn profile link",
                    "github": "GitHub profile link"
                }
                
                Important Notes:
                1. Respond ONLY in JSON format, no additional explanation
                2. Use empty string ("") for missing information
                3. Return information exactly in the format above
                4. Use empty string for information not explicitly shown, do not make assumptions""",
                {"mime_type": "image/png", "data": img_str}
            ])
            
            # JSON yanıtı döndür
            response_text = vision_response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:-3]
            elif response_text.startswith('{'):
                response_text = response_text
                
            print("Gemini Response:", response_text)
            return json.loads(response_text)
            
        except Exception as vision_error:
            print("Image Analysis Error:", str(vision_error))
            raise vision_error
            
        finally:
            # Kaynakları temizle
            pdf_document.close()
            os.unlink(tmp_path)
            
    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise e

def extract_text_from_image(image):
    try:
        # Resmi base64'e çevir
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        # Görüntü analizi yap
        vision_response = vision_model.generate_content([
            """This is a CV image. Please extract the following information in JSON format:
            {
                "ad": "First name",
                "soyad": "Last name",
                "dogum_tarihi": "Date of birth in DD.MM.YYYY format",
                "tc_no": "ID number (if available)",
                "yabanci_dil": "Known languages",
                "telefon": "Phone number",
                "email": "Email address",
                "universite": "University name",
                "fakulte": "Faculty name",
                "bolum": "Department name",
                "egitim_seviyesi": "Education level (Bachelor's/Master's/PhD etc.)",
                "sinif": "Current year/grade",
                "linkedin": "LinkedIn profile link",
                "github": "GitHub profile link"
            }
            
            Important Notes:
            1. Respond ONLY in JSON format, no additional explanation
            2. Use empty string ("") for missing information
            3. Return information exactly in the format above
            4. Use empty string for information not explicitly shown, do not make assumptions""",
            {"mime_type": "image/png", "data": img_str}
        ])
        
        # JSON yanıtı döndür
        response_text = vision_response.text.strip()
        if response_text.startswith('```json'):
            response_text = response_text[7:-3]
        elif response_text.startswith('{'):
            response_text = response_text
            
        print("Gemini Response:", response_text)
        return json.loads(response_text)
        
    except Exception as e:
        print("Image Analysis Error:", str(e))
        raise e

@app.route('/parse_cv', methods=['POST'])
def parse_cv():
    if 'cv' not in request.files:
        return jsonify({'error': 'CV dosyası bulunamadı'}), 400
    
    cv_file = request.files['cv']
    if not cv_file.filename:
        return jsonify({'error': 'Dosya seçilmedi'}), 400
    
    try:
        # CV dosyasını oku
        cv_bytes = cv_file.read()
        
        # Dosya uzantısını kontrol et
        file_ext = cv_file.filename.rsplit('.', 1)[1].lower() if '.' in cv_file.filename else ''
        
        try:
            if file_ext == 'pdf':
                parsed_data = extract_text_from_pdf(cv_bytes)
            else:
                # Resmi aç
                image = Image.open(io.BytesIO(cv_bytes))
                parsed_data = extract_text_from_image(image)
                
            return jsonify(parsed_data)
            
        except Exception as process_error:
            print("İşleme Hatası:", str(process_error))
            return jsonify({
                'error': 'CV işlenemedi',
                'details': str(process_error)
            }), 500
            
    except Exception as e:
        print("Genel Hata:", str(e))
        return jsonify({
            'error': 'İşlem sırasında hata oluştu',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    # Port ve host ayarları
    PORT = 5000
    HOST = '127.0.0.1'
    print(f"\nUygulama şu adreste çalışıyor: http://{HOST}:{PORT}")
    print("Web tarayıcınızda bu adresi açın")
    print("Çıkmak için CTRL+C tuşlarına basın\n")
    app.run(host=HOST, port=PORT, debug=True) 