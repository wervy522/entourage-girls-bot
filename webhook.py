from flask import Flask, request, jsonify
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import logging
import os

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получение конфигурации из переменных окружения
LAVA_API_KEY = os.environ.get('LAVA_API_KEY')
GOOGLE_SHEET_NAME = os.environ.get('GOOGLE_SHEET_NAME')

if not LAVA_API_KEY or not GOOGLE_SHEET_NAME:
    raise ValueError("Необходимо установить переменные окружения LAVA_API_KEY и GOOGLE_SHEET_NAME")

# Настройка доступа к Google Sheets
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']

# Получение учетных данных Google из переменной окружения
GOOGLE_CREDENTIALS = os.environ.get('GOOGLE_CREDENTIALS')
if not GOOGLE_CREDENTIALS:
    raise ValueError("Необходимо установить переменную окружения GOOGLE_CREDENTIALS")

# Создаем временный файл с учетными данными
import tempfile
with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp:
    temp.write(GOOGLE_CREDENTIALS)
    temp_path = temp.name

try:
    credentials = ServiceAccountCredentials.from_json_keyfile_name(temp_path, scope)
    gc = gspread.authorize(credentials)
    sheet = gc.open(GOOGLE_SHEET_NAME).sheet1
finally:
    # Удаляем временный файл
    os.unlink(temp_path)

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработка вебхуков от Lava Top"""
    try:
        # Получаем данные из вебхука
        data = request.json
        logger.info(f"Получен вебхук: {data}")
        
        # Проверяем статус платежа
        if data.get('status') == 'success':
            # Получаем данные пользователя из custom_fields
            custom_fields = data.get('custom_fields', {})
            user_id = custom_fields.get('user_id')
            username = custom_fields.get('username')
            
            if user_id and username:
                # Обновляем статус в Google таблице
                try:
                    # Ищем строку с telegram пользователя
                    cell = sheet.find(username)
                    if cell:
                        # Обновляем статус
                        sheet.update_cell(cell.row, sheet.find('Статус').col, 'Оплачено')
                        logger.info(f"Статус обновлен для пользователя {username}")
                        return jsonify({'status': 'success'}), 200
                except gspread.exceptions.CellNotFound:
                    logger.error(f"Пользователь {username} не найден в таблице")
                    return jsonify({'status': 'error', 'message': 'User not found'}), 404
                
        return jsonify({'status': 'error', 'message': 'Invalid payment status'}), 400
        
    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port) 