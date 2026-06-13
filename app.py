import base64
import io
import os
import socket
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import qrcode
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, send_file, url_for

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ipb-form-secret-key')

RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL', 'ipbguarapari@gmail.com')
EMAIL_SENDER = os.environ.get('EMAIL_SENDER', '')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return 'localhost'


def get_form_url():
    host_url = os.environ.get('HOST_URL', '').rstrip('/')
    if not host_url:
        # dentro de request context: usa o host real
        try:
            host_url = request.host_url.rstrip('/')
        except RuntimeError:
            local_ip = get_local_ip()
            host_url = f'http://{local_ip}:5001'
    return f'{host_url}/form'


def build_qr_image(form_url):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H,
                        box_size=12, border=4)
    qr.add_data(form_url)
    qr.make(fit=True)
    return qr.make_image(fill_color='#1B2B5E', back_color='white')


def generate_qr_b64():
    """Gera o QR como base64 para embutir no HTML (sem gravar em disco)."""
    form_url = get_form_url()
    img = build_qr_image(form_url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    b64 = base64.b64encode(buf.getvalue()).decode()
    return form_url, f'data:image/png;base64,{b64}'


def generate_qr_file():
    """Gera o QR em /tmp para download (único diretório gravável na Vercel)."""
    form_url = get_form_url()
    img = build_qr_image(form_url)
    tmp_path = '/tmp/qrcode_ipb.png'
    img.save(tmp_path)
    return tmp_path


def send_email(name, phone):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print('[Email] Não configurado. Defina EMAIL_SENDER e EMAIL_PASSWORD no .env.')
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = EMAIL_SENDER
        msg['To'] = RECIPIENT_EMAIL
        msg['Subject'] = f'Novo Contato — {name}'
        now = datetime.now().strftime('%d/%m/%Y às %H:%M')
        body = f"""
        <html><body style="font-family:Arial,sans-serif;color:#333;background:#f5f0e8;">
        <div style="max-width:500px;margin:30px auto;background:#fff;border-radius:10px;
                    border-top:5px solid #1B2B5E;padding:30px;">
          <h2 style="color:#1B2B5E;margin-bottom:4px;">Novo Contato Recebido</h2>
          <p style="color:#888;font-size:13px;margin-top:0;">{now}</p>
          <hr style="border:none;border-top:1px solid #e0e0e0;margin:20px 0;">
          <table style="width:100%;border-collapse:collapse;">
            <tr>
              <td style="padding:10px 0;color:#1A5C1A;font-weight:bold;width:100px;">Nome</td>
              <td style="padding:10px 0;">{name}</td>
            </tr>
            <tr style="background:#f9f9f9;">
              <td style="padding:10px 8px;color:#1A5C1A;font-weight:bold;">Telefone</td>
              <td style="padding:10px 8px;">{phone}</td>
            </tr>
          </table>
          <hr style="border:none;border-top:1px solid #e0e0e0;margin:20px 0;">
          <p style="color:#aaa;font-size:12px;text-align:center;">
            Enviado automaticamente — IPB Guarapari
          </p>
        </div>
        </body></html>
        """
        msg.attach(MIMEText(body, 'html'))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print(f'[Email] Enviado para {RECIPIENT_EMAIL} — {name} / {phone}')
        return True
    except Exception as e:
        print(f'[Email] Erro: {e}')
        return False


@app.route('/')
def index():
    form_url, qr_b64 = generate_qr_b64()
    return render_template('index.html', form_url=form_url, qr_b64=qr_b64)


@app.route('/form')
def form():
    return render_template('form.html')


@app.route('/submit', methods=['POST'])
def submit():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    if not name or not phone:
        return redirect(url_for('form'))
    send_email(name, phone)
    return redirect(url_for('success'))


@app.route('/success')
def success():
    return render_template('success.html')


@app.route('/download-qr')
def download_qr():
    tmp_path = generate_qr_file()
    return send_file(tmp_path, as_attachment=True, download_name='qrcode_ipb.png')


if __name__ == '__main__':
    local_ip = get_local_ip()
    print(f'\n{"="*50}')
    print('   Sistema de Contato — IPB Guarapari')
    print(f'{"="*50}')
    print(f'  Painel / QR Code: http://localhost:5001')
    print(f'  Formulário Local: http://localhost:5001/form')
    print(f'  Formulário Rede : http://{local_ip}:5001/form')
    print(f'  Destino de email: {RECIPIENT_EMAIL}')
    print(f'{"="*50}\n')
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)

