import os
import logging
import tempfile
import re
import sys
import json
import hashlib
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "TOKEN"
if not BOT_TOKEN:
    logger.error("BOT_TOKEN not found")
    sys.exit(1)

ACCESS_CONFIG_FILE = "access_config.json"
OWNER_ID = ТВОЙ ID TG

class AccessManager:
    """Manage owner/admins/allowed users."""
    def __init__(self):
        self.owner_id = OWNER_ID
        self.config = self._load_config()
    
    def _load_config(self):
        """Load access config or create default."""
        default_config = {
            "owner_id": self.owner_id,
            "admins": [self.owner_id],
            "allowed_users": [self.owner_id],
            "access_requests": [],
            "auto_approve": False
        }
        if os.path.exists(ACCESS_CONFIG_FILE):
            try:
                with open(ACCESS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading access config: {e}")
                return default_config
        else:
            self._save_config(default_config)
            return default_config
    
    def _save_config(self, config=None):
        """Save access config."""
        if config is None:
            config = self.config
        try:
            with open(ACCESS_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving access config: {e}")
    
    def is_owner(self, user_id: int) -> bool:
        return user_id == self.owner_id
    
    def is_admin(self, user_id: int) -> bool:
        return user_id in self.config.get("admins", [])
    
    def is_user_allowed(self, user_id: int) -> bool:
        allowed_users = self.config.get("allowed_users", [])
        return user_id in allowed_users or self.is_admin(user_id) or self.is_owner(user_id)
    
    def add_allowed_user(self, user_id: int, by_owner_id: int) -> bool:
        if not (self.is_owner(by_owner_id) or self.is_admin(by_owner_id)):
            return False
        if user_id not in self.config["allowed_users"]:
            self.config["allowed_users"].append(user_id)
            self._save_config()
            logger.info(f"Added allowed user: {user_id}")
            return True
        return False
    
    def remove_allowed_user(self, user_id: int, by_owner_id: int) -> bool:
        if not (self.is_owner(by_owner_id) or self.is_admin(by_owner_id)):
            return False
        if user_id in self.config["allowed_users"] and user_id != self.owner_id:
            self.config["allowed_users"].remove(user_id)
            self._save_config()
            logger.info(f"Removed allowed user: {user_id}")
            return True
        return False
    
    def add_access_request(self, user_id: int, username: str = ""):
        requests = self.config.get("access_requests", [])
        for request in requests:
            if request.get("user_id") == user_id:
                return False
        requests.append({
            "user_id": user_id,
            "username": username,
            "timestamp": os.times().elapsed
        })
        self.config["access_requests"] = requests
        self._save_config()
        logger.info(f"Added access request from: {user_id} ({username})")
        return True
    
    def get_access_requests(self):
        return self.config.get("access_requests", [])
    
    def approve_access_request(self, user_id: int, by_owner_id: int) -> bool:
        if not (self.is_owner(by_owner_id) or self.is_admin(by_owner_id)):
            return False
        requests = self.config.get("access_requests", [])
        for request in requests:
            if request.get("user_id") == user_id:
                requests.remove(request)
                self.config["access_requests"] = requests
                self.add_allowed_user(user_id, by_owner_id)
                self._save_config()
                logger.info(f"Approved access for: {user_id}")
                return True
        return False
    
    def deny_access_request(self, user_id: int, by_owner_id: int) -> bool:
        if not (self.is_owner(by_owner_id) or self.is_admin(by_owner_id)):
            return False
        requests = self.config.get("access_requests", [])
        for request in requests:
            if request.get("user_id") == user_id:
                requests.remove(request)
                self.config["access_requests"] = requests
                self._save_config()
                logger.info(f"Denied access for: {user_id}")
                return True
        return False
    
    def add_admin(self, user_id: int, by_owner_id: int) -> bool:
        if not self.is_owner(by_owner_id):
            return False
        if user_id not in self.config["admins"]:
            self.config["admins"].append(user_id)
            if user_id not in self.config["allowed_users"]:
                self.config["allowed_users"].append(user_id)
            self._save_config()
            logger.info(f"Added admin: {user_id}")
            return True
        return False
    
    def remove_admin(self, user_id: int, by_owner_id: int) -> bool:
        if not self.is_owner(by_owner_id):
            return False
        if user_id == self.owner_id:
            return False
        if user_id in self.config["admins"]:
            self.config["admins"].remove(user_id)
            self._save_config()
            logger.info(f"Removed admin: {user_id}")
            return True
        return False
    
    def get_allowed_users(self):
        return self.config.get("allowed_users", [])
    
    def get_admins(self):
        return self.config.get("admins", [])

access_manager = AccessManager()

async def require_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not access_manager.is_user_allowed(user_id):
        keyboard = [
            [InlineKeyboardButton("📨 Запросить доступ", callback_data="request_access")],
            [InlineKeyboardButton("🆘 Помощь", callback_data="help_access")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🔒 Доступ к боту ограничен\n\n"
            "У вас нет разрешения на использование этого бота.\n"
            "Пожалуйста, запросите доступ у администратора.",
            reply_markup=reply_markup
        )
        return False
    return True

async def require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not access_manager.is_admin(user_id):
        await update.message.reply_text(
            "❌ У вас нет прав для выполнения этой команды.\n"
            "Эта команда доступна только администраторам."
        )
        return False
    return True

async def require_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not access_manager.is_owner(user_id):
        await update.message.reply_text("❌ Эта команда доступна только владельцу бота.")
        return False
    return True

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    if data == "request_access":
        username = query.from_user.username or query.from_user.first_name
        if access_manager.add_access_request(user_id, username):
            admins = access_manager.get_admins()
            for admin_id in admins:
                try:
                    keyboard = [
                        [
                            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{user_id}"),
                            InlineKeyboardButton("❌ Отклонить", callback_data=f"deny_{user_id}")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"📨 Новый запрос на доступ:\n👤 Пользователь: {username}\n🆔 ID: {user_id}",
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Error notifying admin {admin_id}: {e}")
            await query.edit_message_text(
                "✅ Запрос на доступ отправлен администраторам\n\nОжидайте одобрения. Вы получите уведомление, когда доступ будет предоставлен."
            )
        else:
            await query.edit_message_text(
                "❌ Вы уже отправили запрос на доступ\n\nПожалуйста, ожидайте ответа от администратора."
            )
    elif data == "help_access":
        await query.edit_message_text(
            "🆘 Помощь по получению доступа\n\nДля получения доступа к боту:\n1. Нажмите кнопку 'Запросить доступ'\n2. Ожидайте одобрения администратора"
        )
    elif data.startswith("approve_"):
        target_user_id = int(data.split("_")[1])
        if access_manager.approve_access_request(target_user_id, user_id):
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="🎉 Ваш запрос на доступ одобрен!\n\nТеперь вы можете использовать все функции бота. Введите /start для начала работы."
                )
            except Exception as e:
                logger.error(f"Error notifying user {target_user_id}: {e}")
            await query.edit_message_text(f"✅ Доступ предоставлен пользователю {target_user_id}")
        else:
            await query.edit_message_text("❌ Ошибка одобрения доступа")
    elif data.startswith("deny_"):
        target_user_id = int(data.split("_")[1])
        if access_manager.deny_access_request(target_user_id, user_id):
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="❌ Ваш запрос на доступ отклонен\n\nЕсли вы считаете это ошибкой, свяжитесь с администратором."
                )
            except Exception as e:
                logger.error(f"Error notifying user {target_user_id}: {e}")
            await query.edit_message_text(f"❌ Доступ отклонен для пользователя {target_user_id}")
        else:
            await query.edit_message_text("❌ Ошибка отклонения доступа")

class DuplicateChecker:
    """Check duplicates by FIO."""
    def __init__(self, data_folder="user_data"):
        self.data_folder = Path(data_folder)
        self.data_folder.mkdir(exist_ok=True)
        self.fio_file = self.data_folder / "fio_hashes.json"
        self.fio_hashes = self._load_hashes(self.fio_file)
    
    def _load_hashes(self, file_path):
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        return set()
    
    def _save_hashes(self, file_path, hashes):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(list(hashes), f, ensure_ascii=False, indent=2)
    
    def _normalize_fio(self, fio):
        if not fio or fio == '-':
            return None
        normalized = ' '.join(fio.strip().lower().split())
        normalized = re.sub(r'[^а-яёa-z\s]', '', normalized)
        return normalized if normalized else None
    
    def _create_fio_hash(self, fio):
        normalized_fio = self._normalize_fio(fio)
        if not normalized_fio:
            return None
        return hashlib.md5(normalized_fio.encode('utf-8')).hexdigest()
    
    def check_duplicates(self, parsed_data):
        duplicates = {'fio': False, 'details': []}
        fio = parsed_data.get('ФИО', '-')
        if fio != '-':
            fio_hash = self._create_fio_hash(fio)
            if fio_hash and fio_hash in self.fio_hashes:
                duplicates['fio'] = True
                duplicates['details'].append(f"ФИО: {fio}")
        return duplicates
    
    def add_to_database(self, parsed_data):
        added = []
        fio = parsed_data.get('ФИО', '-')
        if fio != '-':
            fio_hash = self._create_fio_hash(fio)
            if fio_hash and fio_hash not in self.fio_hashes:
                self.fio_hashes.add(fio_hash)
                added.append('ФИО')
        self._save_hashes(self.fio_file, self.fio_hashes)
        return added
    
    def get_stats(self):
        return {'fio_count': len(self.fio_hashes), 'total_unique': len(self.fio_hashes)}

    def clear_database(self):
        confirmation = input("Вы уверены, что хотите очистить базу данных? (да/нет): ")
        if confirmation.lower() == 'да':
            logger.info("База данных очищена.")
        else:
            logger.info("Очистка базы данных отменена.")

def parse_chunk(chunk):
    out = {'СНИЛС': '-', 'ИНН': '-', 'ФИО': '-', 'Дата рождения': '-', 
           'Телефон': '-', 'Почта': '-', 'Ключ': '-', 'Серия и номер': '-',
           'Дата выдачи': '-', 'Код подразделения': '-', 'Адрес регистрации': '-',
           'Фактическое проживание': '-', 'Пароль': '-'}
    chunk_clean = ' '.join(line.strip() for line in chunk.splitlines() if line.strip())
    chunk_clean = re.sub(r'\s+', ' ', chunk_clean)
    if len(chunk_clean) < 15:
        return out
    email_pass_match = re.search(r'^(\d+\.\s*)?([^:|]+@[^:|]+):([^|\s]+)', chunk_clean)
    phone_pass_match = re.search(r'^(\d+\.\s*)?(\+?7\d{10}):([^|\s]+)', chunk_clean)
    if email_pass_match:
        out['Почта'] = email_pass_match.group(2).strip()
        out['Пароль'] = email_pass_match.group(3).strip()
        if re.match(r'\+?7\d{10}', out['Почта']):
            out['Телефон'] = out['Почта']
    elif phone_pass_match:
        phone = phone_pass_match.group(2).strip()
        out['Телефон'] = phone
        out['Пароль'] = phone_pass_match.group(3).strip()
    separators = ['|', ';', ',', '\t']
    for separator in separators:
        parts = chunk_clean.split(separator)
        if len(parts) > 2:
            break
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if re.match(r'^(\d+\.\s*)?[^:|]+@[^:|]+:[^|\s]+', part) or re.match(r'^(\d+\.\s*)?\+?7\d{10}:[^|\s]+', part):
            continue
        if ':' in part:
            key, value = part.split(':', 1)
            key = key.strip()
            value = value.strip()
        else:
            key = part
            value = ''
        key_lower = key.lower()
        if any(word in key_lower for word in ['снилс', 'snils']):
            out['СНИЛС'] = value if value and value.lower() not in ['не найдено', 'нет', 'none', 'null'] else '-'
        elif any(word in key_lower for word in ['инн', 'inn']):
            out['ИНН'] = value if value and value.lower() not in ['не найдено', 'нет', 'none', 'null'] else '-'
        elif any(word in key_lower for word in ['фио', 'fio', 'фам', 'имя', 'отчество']):
            out['ФИО'] = value
        elif re.search(r"\b(дата\s*рожд(?:ения)?|дата\s*рожд)\b", key_lower) or re.search(r"\bдр\b", key_lower):
            out['Дата рождения'] = value
        elif any(word in key_lower for word in ['тел', 'phone', 'номер тел']):
            out['Телефон'] = value
        elif any(word in key_lower for word in ['почта', 'email', 'e-mail']):
            out['Почта'] = value
        elif any(word in key_lower for word in ['ключ', 'key']):
            out['Ключ'] = value
        elif any(word in key_lower for word in ['серия', 'номер паспорт', 'паспорт']):
            out['Серия и номер'] = value
        elif any(word in key_lower for word in ['дата выд', 'выдан']):
            out['Дата выдачи'] = value
        elif any(word in key_lower for word in ['код подр', 'код отделен']):
            out['Код подразделения'] = value
        elif any(word in key_lower for word in ['адрес рег', 'регистрац', 'прописк']):
            out['Адрес регистрации'] = value if value and value.lower() not in ['не найден', 'нет', 'none', 'null'] else '-'
        elif any(word in key_lower for word in ['факт', 'проживан']):
            out['Фактическое проживание'] = value if value and value.lower() not in ['не найден', 'нет', 'none', 'null'] else '-'
        elif any(word in key_lower for word in ['парол', 'password']):
            out['Пароль'] = value
    if out['Дата рождения'] == '-' or out['Дата рождения'] == '':
        dob_match = re.search(r"дата\s*рожд(?:ения)?\s*[:\-]?\s*(\d{2}\.\d{2}\.\d{4})", chunk_clean, flags=re.IGNORECASE)
        if dob_match:
            out['Дата рождения'] = dob_match.group(1)
    if out['ИНН'] == '-':
        inn_match = re.search(r'\b(\d{12})\b', chunk_clean)
        if inn_match:
            out['ИНН'] = inn_match.group(1)
    if out['Серия и номер'] == '-':
        passport_match = re.search(r'(\d{4}\s*\d{6})', chunk_clean)
        if passport_match:
            out['Серия и номер'] = passport_match.group(1)
    if out['Дата выдачи'] == '-':
        all_dates = re.findall(r'\d{2}\.\d{2}\.\d{4}', chunk_clean)
        if len(all_dates) > 1:
            out['Дата выдачи'] = all_dates[1]
        elif len(all_dates) == 1 and out['Дата рождения'] == '-':
            out['Дата выдачи'] = all_dates[0]
    if out['Код подразделения'] == '-':
        code_match = re.search(r'(\d{3}-\d{3})', chunk_clean)
        if code_match:
            out['Код подразделения'] = code_match.group(1)
    if out['Телефон'] == '-':
        phone_match = re.search(r'(\+7\s?\d{3}\s?\d{3}[\s-]?\d{2}[\s-]?\d{2})', chunk_clean)
        if phone_match:
            out['Телефон'] = phone_match.group(1)
    if out['Фактическое проживание'] != '-':
        out['Адрес проживания'] = out['Фактическое проживание']
    elif out['Адрес регистрации'] != '-':
        out['Адрес проживания'] = out['Адрес регистрации']
    else:
        out['Адрес проживания'] = '-'
    return out

def format_record(parsed, slot_number):
    def clean(value):
        if not value or value == '-':
            return '-'
        value = str(value).strip()
        if value.lower() in ['не найден', 'не найдено', 'нет']:
            return '-'
        return value
    def format_value(value):
        cleaned = clean(value)
        if cleaned == '-':
            return '-'
        return f'`{cleaned}`'
    lines = []
    lines.append(f'#️⃣ СЛОТ №{slot_number}')
    lines.append('🔐 Учетные данные')
    lines.append(f"СНИЛС: {format_value(parsed.get('СНИЛС'))}")
    lines.append(f"Пароль: {format_value(parsed.get('Пароль'))}")
    lines.append(f"Ключ: {format_value(parsed.get('Ключ'))}")
    lines.append('👤 Персональная информация')
    lines.append(f"ФИО: {clean(parsed.get('ФИО'))}")
    lines.append(f"Дата рождения: {format_value(parsed.get('Дата рождения'))}")
    lines.append(f"Адрес проживания: {format_value(parsed.get('Адрес проживания'))}")
    lines.append('📞 Контакты')
    lines.append(f"Телефон: {format_value(parsed.get('Телефон'))}")
    lines.append(f"Почта: {format_value(parsed.get('Почта'))}")
    lines.append('📄 Документы')
    lines.append('Паспорт РФ:')
    lines.append(f"Серия/номер: {format_value(parsed.get('Серия и номер'))}")
    lines.append(f"Дата выдачи: {format_value(parsed.get('Дата выдачи'))}")
    lines.append(f"Код подразделения: {format_value(parsed.get('Код подразделения'))}")
    lines.append(f"ИНН: {format_value(parsed.get('ИНН'))}")
    return '\n'.join(lines) + '\n\n'

def get_birth_year(parsed):
    birth_date = parsed.get('Дата рождения', '-')
    if birth_date != '-':
        year_match = re.search(r'(\d{4})', birth_date)
        if year_match:
            return int(year_match.group(1))
    return None

def process_file_content_with_check(file_content: str, filename: str):
    try:
        if not file_content or len(file_content.strip()) == 0:
            return {'error': 'Файл не содержит данных'}
        original_content = file_content
        if not any(char.isalpha() for char in file_content[:1000]):
            encodings = ['cp1251', 'iso-8859-1', 'cp866']
            for encoding in encodings:
                try:
                    with open(filename, 'r', encoding=encoding) as f:
                        file_content = f.read()
                    if any(char.isalpha() for char in file_content[:1000]):
                        break
                except:
                    continue
        chunks = []
        lines = file_content.splitlines()
        current_chunk = []
        lines = [line for line in lines if line.strip()]
        if len(lines) == 0:
            return {'error': 'Файл не содержит текстовых данных'}
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                if current_chunk:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = []
                continue
            is_new_record = (
                re.match(r'^\d+\.\s*[^:|]+@[^:|]+:[^|\s]+', line) or
                re.match(r'^\d+\.\s*\+?7\d{10}:[^|\s]+', line) or
                re.match(r'^[^:|]+@[^:|]+:[^|\s]+', line) or
                re.match(r'^\+?7\d{10}:[^|\s]+', line) or
                (i > 0 and not lines[i-1].strip() and any(keyword in line for keyword in ['СНИЛС', 'ФИО', 'ИНН', 'Паспорт']))
            )
            if is_new_record and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
            current_chunk.append(line)
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        if len(chunks) <= 1:
            chunks = re.split(r'\n\s*\n', file_content)
        if len(chunks) <= 1:
            chunks = re.split(r'(?=\d+\.\s)', file_content)
        chunks = [chunk.strip() for chunk in chunks if chunk.strip() and len(chunk.strip()) > 10]
        if len(chunks) == 0:
            return {
                'valid': '',
                'nevalid': '',
                'duplicates': '',
                'all': '',
                'valid_count': 0,
                'nevalid_count': 0,
                'duplicate_count': 0,
                'total_count': 0,
                'stats': {'fio_count': 0, 'total_unique': 0}
            }
        checker = DuplicateChecker()
        valid_results = []
        nevalid_results = []
        duplicate_results = []
        slot_number = 1
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk or len(chunk) < 20:
                continue
            parsed = parse_chunk(chunk)
            has_fio = parsed.get('ФИО') != '-' and len(parsed.get('ФИО', '')) > 5
            has_other_data = any(parsed.get(field) != '-' for field in ['СНИЛС', 'Телефон', 'Почта', 'Серия и номер', 'ИНН'])
            if has_fio and has_other_data:
                duplicates = checker.check_duplicates(parsed)
                formatted = format_record(parsed, slot_number)
                if duplicates['fio']:
                    duplicate_info = "🚨 ОБНАРУЖЕН ДУБЛЬ ПО ФИО:\n"
                    for detail in duplicates['details']:
                        duplicate_info += f"• {detail}\n"
                    formatted = duplicate_info + "\n" + formatted
                    duplicate_results.append(formatted)
                else:
                    added_fields = checker.add_to_database(parsed)
                    if added_fields:
                        formatted += f"✅ Добавлено в базу: {', '.join(added_fields)}\n"
                    birth_year = get_birth_year(parsed)
                    if birth_year is not None:
                        if birth_year >= 1952:
                            valid_results.append(formatted)
                        else:
                            nevalid_results.append(formatted)
                    else:
                        nevalid_results.append(formatted)
                slot_number += 1
        stats = checker.get_stats()
        return {
            'valid': ''.join(valid_results),
            'nevalid': ''.join(nevalid_results),
            'duplicates': ''.join(duplicate_results),
            'all': ''.join(valid_results + nevalid_results + duplicate_results),
            'valid_count': len(valid_results),
            'nevalid_count': len(nevalid_results),
            'duplicate_count': len(duplicate_results),
            'total_count': len(valid_results) + len(nevalid_results) + len(duplicate_results),
            'stats': stats
        }
    except Exception as e:
        error_msg = f"Ошибка обработки файла: {str(e)}"
        logger.error(f"Error processing file {filename}: {e}")
        return {'error': error_msg}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    if not access_manager.is_user_allowed(user_id):
        keyboard = [
            [InlineKeyboardButton("📨 Запросить доступ", callback_data="request_access")],
            [InlineKeyboardButton("🆘 Помощь", callback_data="help_access")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"👋 Привет, {user_name}!\n\n"
            "🔒 Доступ к боту ограничен\n\n"
            "У вас нет разрешения на использование этого бота. \n"
            "Пожалуйста, запросите доступ у администратора.",
            reply_markup=reply_markup
        )
        return
    welcome_text = (
        f'👋 Привет, {user_name}!\n\n'
        'Я бот для обработки логов с проверкой дублей по ФИО.\n\n'
        '📁 Отправь мне .txt файл, и я:\n'
        '• Разберу данные по полям\n'
        '• Отсортирую по году рождения\n'
        '• Проверю на дубли по ФИО\n'
        '• Верну структурированные результаты\n\n'
        '✅ Валидные: 1952 год и младше\n'
        '❌ Невалидные: до 1952 года\n'
        '🚨 Дубли: уже есть в базе по ФИО\n\n'
        'Основные команды:\n'
        '/stats - статистика базы\n'
        '/help - помощь'
    )
    if access_manager.is_owner(user_id):
        welcome_text += '\n\n👑 Вы владелец бота\n/access_panel - управление доступом'
    elif access_manager.is_admin(user_id):
        welcome_text += '\n\n⚡ Вы администратор\n/access_panel - управление доступом'
    await update.message.reply_text(welcome_text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_access(update, context):
        return
    checker = DuplicateChecker()
    stats = checker.get_stats()
    stats_msg = (
        "📊 Статистика базы данных:\n\n"
        f"• Уникальных ФИО: {stats['fio_count']}\n"
        f"📈 Всего уникальных записей: {stats['total_unique']}"
    )
    await update.message.reply_text(stats_msg)

async def clear_db_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    checker = DuplicateChecker()
    result = checker.clear_database()
    await update.message.reply_text(result)

async def access_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await require_admin(update, context) or await require_owner(update, context)):
        return
    user_id = update.effective_user.id
    allowed_users = access_manager.get_allowed_users()
    access_requests = access_manager.get_access_requests()
    panel_text = (
        "🔐 Панель управления доступом\n\n"
        f"📊 Пользователей с доступом: {len(allowed_users)}\n"
        f"📨 Запросов на доступ: {len(access_requests)}\n\n"
    )
    if access_manager.is_owner(user_id):
        panel_text += "👑 Команды владельца:\n"
        panel_text += "/add_admin <user_id> - добавить администратора\n"
        panel_text += "/remove_admin <user_id> - удалить администратора\n"
        panel_text += "/list_admins - список администраторов\n\n"
    panel_text += "👥 Команды управления доступом:\n"
    panel_text += "/add_user <user_id> - добавить пользователя\n"
    panel_text += "/remove_user <user_id> - удалить пользователя\n"
    panel_text += "/list_users - список пользователей\n"
    panel_text += "/list_requests - список запросов\n"
    await update.message.reply_text(panel_text)

async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await require_admin(update, context) or await require_owner(update, context)):
        return
    if not context.args:
        await update.message.reply_text("❌ Укажите ID пользователя: /add_user <user_id>")
        return
    try:
        user_id = int(context.args[0])
        if access_manager.add_allowed_user(user_id, update.effective_user.id):
            await update.message.reply_text(f"✅ Пользователь {user_id} добавлен в белый список")
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="🎉 Вам предоставлен доступ к боту!\n\nТеперь вы можете использовать все функции бота. Введите /start для начала работы."
                )
            except Exception as e:
                logger.error(f"Error notifying user {user_id}: {e}")
        else:
            await update.message.reply_text("❌ Ошибка добавления пользователя")
    except ValueError:
        await update.message.reply_text("❌ Неверный формат ID пользователя")

async def remove_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await require_admin(update, context) or await require_owner(update, context)):
        return
    if not context.args:
        await update.message.reply_text("❌ Укажите ID пользователя: /remove_user <user_id>")
        return
    try:
        user_id = int(context.args[0])
        if access_manager.remove_allowed_user(user_id, update.effective_user.id):
            await update.message.reply_text(f"✅ Пользователь {user_id} удален из белого списка")
        else:
            await update.message.reply_text("❌ Ошибка удаления пользователя")
    except ValueError:
        await update.message.reply_text("❌ Неверный формат ID пользователя")

async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await require_admin(update, context) or await require_owner(update, context)):
        return
    allowed_users = access_manager.get_allowed_users()
    admins = access_manager.get_admins()
    if not allowed_users:
        await update.message.reply_text("❌ Нет пользователей с доступом")
        return
    users_text = "👥 Пользователи с доступом:\n\n"
    for i, user_id in enumerate(allowed_users, 1):
        if user_id == access_manager.owner_id:
            role = "👑 Владелец"
        elif user_id in admins:
            role = "⚡ Администратор"
        else:
            role = "👤 Пользователь"
        users_text += f"{i}. {user_id} - {role}\n"
    users_text += f"\n📊 Всего: {len(allowed_users)} пользователей"
    await update.message.reply_text(users_text)

async def list_requests_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (await require_admin(update, context) or await require_owner(update, context)):
        return
    access_requests = access_manager.get_access_requests()
    if not access_requests:
        await update.message.reply_text("✅ Нет активных запросов на доступ")
        return
    requests_text = "📨 Активные запросы на доступ:\n\n"
    for i, request in enumerate(access_requests, 1):
        user_id = request.get("user_id")
        username = request.get("username", "Без username")
        requests_text += f"{i}. {username} (ID: {user_id})\n"
    requests_text += f"\nДля одобрения используйте кнопки в уведомлениях"
    await update.message.reply_text(requests_text)

async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_owner(update, context):
        return
    if not context.args:
        await update.message.reply_text("❌ Укажите ID пользователя: /add_admin <user_id>")
        return
    try:
        user_id = int(context.args[0])
        if access_manager.add_admin(user_id, update.effective_user.id):
            await update.message.reply_text(f"✅ Пользователь {user_id} добавлен в администраторы")
        else:
            await update.message.reply_text("❌ Ошибка добавления администратора")
    except ValueError:
        await update.message.reply_text("❌ Неверный формат ID пользователя")

async def remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_owner(update, context):
        return
    if not context.args:
        await update.message.reply_text("❌ Укажите ID пользователя: /remove_admin <user_id>")
        return
    try:
        user_id = int(context.args[0])
        if access_manager.remove_admin(user_id, update.effective_user.id):
            await update.message.reply_text(f"✅ Пользователь {user_id} удален из администраторов")
        else:
            await update.message.reply_text("❌ Ошибка удаления администратора")
    except ValueError:
        await update.message.reply_text("❌ Неверный формат ID пользователя")

async def list_admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_owner(update, context):
        return
    admins = access_manager.get_admins()
    if not admins:
        await update.message.reply_text("❌ Нет администраторов")
        return
    admins_text = "👥 Список администраторов:\n\n"
    for i, admin_id in enumerate(admins, 1):
        role = "👑 Владелец" if admin_id == access_manager.owner_id else "⚡ Администратор"
        admins_text += f"{i}. {admin_id} - {role}\n"
    await update.message.reply_text(admins_text)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_access(update, context):
        return
    temp_files_to_cleanup = []
    try:
        document = update.message.document
        if not document.file_name.endswith('.txt'):
            await update.message.reply_text("❌ Пожалуйста, отправьте .txt файл")
            return
        if document.file_size == 0:
            await update.message.reply_text("❌ Файл пустой. Пожалуйста, отправьте файл с данными.")
            return
        if document.file_size > 50 * 1024 * 1024:
            await update.message.reply_text("❌ Файл слишком большой. Максимальный размер: 50 МБ")
            return
        await update.message.reply_text("⏳ Обрабатываю файл с проверкой дублей по ФИО...")
        file = await context.bot.get_file(document.file_id)
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt', encoding='utf-8') as temp_file:
            temp_path = temp_file.name
        temp_files_to_cleanup.append(temp_path)
        try:
            await file.download_to_drive(temp_path)
            file_stats = os.stat(temp_path)
            if file_stats.st_size == 0:
                await update.message.reply_text("❌ Файл пустой после скачивания. Возможно, проблема с файлом.")
                return
            with open(temp_path, 'r', encoding='utf-8', errors='ignore') as f:
                file_content = f.read().strip()
            if not file_content:
                await update.message.reply_text("❌ Файл не содержит текстовых данных.")
                return
            if len(file_content) < 10:
                await update.message.reply_text("❌ Файл содержит слишком мало данных для обработки.")
                return
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка чтения файла: {str(e)}")
            return
        results = process_file_content_with_check(file_content, document.file_name)
        if 'error' in results:
            await update.message.reply_text(f"❌ {results['error']}")
            return
        if (results['valid_count'] == 0 and 
            results['nevalid_count'] == 0 and 
            results['duplicate_count'] == 0):
            await update.message.reply_text(
                "⚠️ В файле не найдено записей для обработки.\n\n"
                "Возможные причины:\n"
                "• Неправильный формат данных\n"
                "• Отсутствуют ФИО в данных\n"
                "• Данные не соответствуют ожидаемому формату\n\n"
                "Проверьте формат файла и попробуйте снова."
            )
            return
        stats = results.get('stats', {})
        stats_msg = (
            f"📊 Результаты обработки:\n"
            f"✅ Валидных записей: {results['valid_count']}\n"
            f"❌ Невалидных записей: {results['nevalid_count']}\n"
            f"🚨 Дублей найдено: {results['duplicate_count']}\n"
            f"📋 Всего записей: {results['total_count']}\n\n"
            f"💾 В базе уникальных ФИО: {stats.get('fio_count', 0)}"
        )
        await update.message.reply_text(stats_msg)
        async def send_file_safely(file_content: str, filename: str, caption: str):
            temp_file_path = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
                    f.write(file_content)
                    temp_file_path = f.name
                with open(temp_file_path, 'rb') as file_to_send:
                    await update.message.reply_document(
                        document=file_to_send,
                        filename=filename,
                        caption=caption
                    )
                return True
            except Exception as e:
                logger.error(f"Error sending file {filename}: {e}")
                return False
            finally:
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                    except Exception as e:
                        logger.error(f"Error deleting file {temp_file_path}: {e}")
        send_results = []
        if results['duplicate_count'] > 0 and results['duplicates'].strip():
            success = await send_file_safely(
                results['duplicates'],
                "duplicates.txt",
                f"Дубли по ФИО ({results['duplicate_count']} шт.)"
            )
            send_results.append(("дубли", success))
        if results['valid_count'] > 0 and results['valid'].strip():
            success = await send_file_safely(
                results['valid'],
                "valid.txt", 
                f"Валидные записи ({results['valid_count']} шт.)"
            )
            send_results.append(("валидные", success))
        if results['nevalid_count'] > 0 and results['nevalid'].strip():
            success = await send_file_safely(
                results['nevalid'],
                "nevalid.txt",
                f"Невалидные записи ({results['nevalid_count']} шт.)"
            )
            send_results.append(("невалидные", success))
        if results['total_count'] > 0 and results['all'].strip():
            success = await send_file_safely(
                results['all'],
                "all_records.txt",
                f"Все записи ({results['total_count']} шт.)"
            )
            send_results.append(("все записи", success))
        failed_sends = [name for name, success in send_results if not success]
        if failed_sends:
            await update.message.reply_text(
                f"⚠️ Не удалось отправить некоторые файлы: {', '.join(failed_sends)}\n"
                f"Но обработка данных завершена успешно!"
            )
        else:
            await update.message.reply_text("🎉 Обработка завершена!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        for temp_file in temp_files_to_cleanup:
            if os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    logger.error(f"Error deleting temp file {temp_file}: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_access(update, context):
        return
    user_id = update.effective_user.id
    help_text = (
        'ℹ️ Помощь по боту:\n\n'
        '📁 Отправьте .txt файл для обработки\n\n'
        'Основные команды:\n'
        '/start - начать работу\n'
        '/stats - статистика базы\n'
        '/help - эта справка\n\n'
        'Бот проверяет дубли только по ФИО'
    )
    if access_manager.is_admin(user_id) or access_manager.is_owner(user_id):
        help_text += '\n\n⚡ Административные команды:\n'
        help_text += '/clear_db - очистить базу данных\n'
        help_text += '/access_panel - управление доступом'
        if access_manager.is_owner(user_id):
            help_text += '\n\n👑 Команды владельца:\n'
            help_text += '/add_admin <id> - добавить администратора\n'
            help_text += '/remove_admin <id> - удалить администратора\n'
            help_text += '/list_admins - список администраторов'
    await update.message.reply_text(help_text)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_access(update, context):
        return
    await update.message.reply_text(
        "📁 Пожалуйста, отправьте мне .txt файл для обработки.\n"
        "Используйте /help для получения справки."
    )

def main():
    print("Запуск бота...")
    print(f"Владелец бота: {OWNER_ID}")
    print(f"Пользователей с доступом: {len(access_manager.get_allowed_users())}")
    print(f"Администраторов: {len(access_manager.get_admins())}")
    print(f"Активных запросов: {len(access_manager.get_access_requests())}")
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("clear_db", clear_db_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("access_panel", access_panel_command))
        application.add_handler(CommandHandler("add_user", add_user_command))
        application.add_handler(CommandHandler("remove_user", remove_user_command))
        application.add_handler(CommandHandler("list_users", list_users_command))
        application.add_handler(CommandHandler("list_requests", list_requests_command))
        application.add_handler(CommandHandler("add_admin", add_admin_command))
        application.add_handler(CommandHandler("remove_admin", remove_admin_command))
        application.add_handler(CommandHandler("list_admins", list_admins_command))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        print("Бот запущен")
        application.run_polling(drop_pending_updates=True)
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
