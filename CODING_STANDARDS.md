# CODING STANDARDS — Harvest Project

## 1. Язык и стиль

- **Код**: Python 3.10+
- **Форматирование**: Black, 120 символов на строку
- **Линтер**: Ruff (все правила кроме тех что конфликтуют с Black)
- **Типы**: mypy (опционально, не строго)
- **Безопасность**: bandit (ручной запуск)

## 2. Структура проекта

```
harvest/
├── harvest/          # Пакет
│   ├── __init__.py   # Версия, __doc__
│   ├── cli.py        # Интерфейс командной строки (Click)
│   ├── core.py       # Scraper — базовый парсер
│   ├── config.py     # Конфигурация (YAML)
│   ├── extract.py    # Структурированное извлечение данных
│   ├── crawl.py      # Краулер (BFS)
│   ├── contacts.py   # Сбор контактов
│   ├── export.py     # Экспорт (CSV, JSON)
│   ├── notify.py     # Уведомления (Telegram, webhook, stdout)
│   ├── browser.py    # Браузерная сессия + поиск ключей
│   ├── rotator.py    # Ротация прокси
│   ├── monitor.py    # Мониторинг изменений
│   ├── pipeline.py   # Конвейер операций
│   └── server.py     # FastAPI HTTP API
├── tests/
│   └── test_all.py   # Тесты
├── plugins/          # Плагины (опционально)
├── pyproject.toml    # Зависимости и метаданные
├── .pre-commit-config.yaml
└── Makefile
```

## 3. Принципы

### SRP (Single Responsibility Principle)
- Один модуль = одна ответственность
- core.py — только HTTP запросы
- export.py — только форматы вывода
- notify.py — только отправка уведомлений

### Отсутствие «магических» зависимостей
- Scrapling — основная зависимость для парсинга
- Нет привязки к OmniRoute или конкретному API
- Работает с любым OpenAI-совместимым API

### Graceful Degradation
- Любой модуль работает без конфига
- Если нет PyYAML — используется fallback парсер
- Если нет aiohttp — уведомления падают на stdout

## 4. Обработка ошибок

```python
# ПЛОХО:
except:
    pass

# ХОРОШО:
except Exception as e:
    logger.error(f"Операция не удалась: {e}")
    return fallback_value
```

- Всегда логировать через `logging.getLogger(__name__)`
- Никогда не «проглатывать» исключения без логирования
- В CLI — человекочитаемые сообщения об ошибках

## 5. Асинхронность

- HTTP/Cеть — асинхронно (await)
- Файловые операции — синхронно
- Не смешивать async и sync без необходимости

## 6. Тестирование

```bash
# Все тесты
python3 -m pytest tests/ -v

# С покрытием
python3 -m pytest tests/ --cov=harvest -v

# Без pytest
python3 tests/test_all.py
```

- Тесты НЕ требуют сети (use mocks for HTTP)
- Тесты НЕ требуют установки зависимостей (fallback режим)
- Тестировать: пустые входные данные, None, спецсимволы, граничные значения

## 7. Git

- Сообщения коммитов: `type: краткое описание`
  - `feat:` — новая фича
  - `fix:` — исправление бага
  - `test:` — тесты
  - `docs:` — документация
  - `refactor:` — рефакторинг
  - `chore:` — техника
- Ветки: `feature/название`, `fix/название`
- Релизы: `v{major}.{minor}.{patch}`

## 8. Перед коммитом

```bash
# Обязательно:
ruff check .
ruff format --check .

# Рекомендуется:
python3 -m pytest tests/ -v

# При наличии mypy:
mypy harvest/ --ignore-missing-imports

# При наличии bandit:
bandit -r harvest/ -c pyproject.toml
```

## 9. Добавление новой фичи

1. Создать модуль в `harvest/` (один файл — одна ответственность)
2. Добавить команду в `cli.py`
3. Добавить тесты в `tests/test_all.py`
4. Обновить `README.md` если надо
5. Проверить `ruff check .`
6. Проверить `python3 tests/test_all.py`
