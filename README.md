# nifi-mcp-universal

MCP-шлюз для Apache NiFi. Подключает Claude Code / Cursor / VS Code к нескольким NiFi инстансам одновременно через [Model Context Protocol](https://modelcontextprotocol.io/).

Один адрес `http://localhost:8085/mcp` вместо ручной настройки. Шлюз принимает запросы от AI и маршрутизирует их к нужному NiFi. Каждый сеанс AI-ассистента работает со своим активным подключением независимо (per-session routing).

---

## Оглавление

- [Возможности](#возможности)
- [Требования](#требования)
- [Быстрый старт](#быстрый-старт)
- [После установки — первые шаги](#после-установки--первые-шаги)
- [Подключение к Claude Code](#подключение-к-claude-code)
- [MCP Tools](#mcp-tools)
- [Dashboard](#dashboard)
- [Методы аутентификации](#методы-аутентификации)
- [Управление сертификатами](#управление-сертификатами)
- [Конфигурация](#конфигурация)
- [API Endpoints](#api-endpoints)
- [Совместимость](#совместимость)
- [Архитектура](#архитектура)
- [Стек](#стек)
- [Troubleshooting](#troubleshooting)
- [Благодарности](#благодарности)
- [Лицензия](#лицензия)

---

## Возможности

- **Multi-NiFi** — подключение к нескольким NiFi инстансам одновременно с переключением через MCP tools или Dashboard
- **Per-session routing** — каждая сессия Claude Code может работать со своим NiFi
- **72 MCP tools** — управление подключениями, процессоры, соединения, controller services, process groups, порты, parameter contexts, best practices
- **Dashboard** — веб-интерфейс для управления подключениями с загрузкой сертификатов (`/dashboard`)
- **Docker** — запуск одной командой
- **Кроссплатформенность** — Linux и Windows (через docker-compose override)
- **7 методов аутентификации** — Certificate P12/PEM, Knox JWT/Cookie/Passcode, Basic Auth, No Auth
- **NiFi 1.x и 2.x** — автоматическое определение версии
- **Read-only по умолчанию** — безопасный режим, write-операции требуют явного включения
- **Двуязычный UI** — русский и английский

## Требования

| Компонент | Минимальная версия | Установка |
|-----------|-------------------|-----------|
| **Docker Engine** | 24+ | [docs.docker.com/get-docker](https://docs.docker.com/get-docker/) |
| **Docker Compose** | v2 (плагин) | [docs.docker.com/compose/install](https://docs.docker.com/compose/install/) |
| **Claude Code CLI** | любая | [claude.ai/download](https://claude.ai/download) |
| **ОС** | Linux, macOS, Windows (Git Bash или WSL2) | — |

> **Важно:** требуется именно `docker compose` (v2, встроенный плагин), а не устаревший `docker-compose` (v1). Проверить: `docker compose version`.

---

## Быстрый старт

### Linux / macOS

```bash
git clone https://github.com/AlekseiSeleznev/nifi-mcp-universal.git
cd nifi-mcp-universal
./setup.sh
```

### Windows

**Требуется** [Git for Windows](https://gitforwindows.org/) (включает Git Bash) или WSL2.

```bash
git clone https://github.com/AlekseiSeleznev/nifi-mcp-universal.git
cd nifi-mcp-universal
./setup.sh
```

### Что делает `setup.sh`

1. Определяет ОС — на macOS/Windows автоматически создаёт `docker-compose.override.yml` с bridge-сетью (host mode не поддерживается Docker Desktop)
2. Создаёт `.env` из `.env.example` (порт 8085)
3. Собирает и запускает Docker-контейнер (`restart: always` — переживает перезагрузку)
4. Ждёт healthcheck
5. Регистрирует MCP-сервер в Claude Code через `claude mcp add`

После установки откройте Claude Code и выполните `/mcp` для проверки.

**Dashboard:** [http://localhost:8085/dashboard](http://localhost:8085/dashboard)

### Ручная установка

Если `setup.sh` не подходит:

```bash
cp .env.example .env
# Отредактируйте .env при необходимости

# Linux:
docker compose up -d --build

# macOS / Windows:
docker compose -f docker-compose.yml -f docker-compose.windows.yml up -d --build

# Регистрация в Claude Code:
claude mcp add --transport http -s user nifi-universal http://localhost:8085/mcp
```

## После установки — первые шаги

### 1. Проверить MCP в Claude Code

Откройте Claude Code и выполните:

```
/mcp
```

В списке должен появиться `nifi-universal`. Если его нет — см. раздел [Troubleshooting](#troubleshooting).

### 2. Открыть Dashboard

Перейдите по адресу: [http://localhost:8085/dashboard](http://localhost:8085/dashboard)

### 3. Добавить первое подключение к NiFi

**Вариант А — через Dashboard:**

1. Откройте [http://localhost:8085/dashboard](http://localhost:8085/dashboard)
2. Нажмите кнопку **"Добавить подключение"**
3. Введите имя, URL NiFi и выберите метод аутентификации
4. Нажмите **"Подключить"**

**Вариант Б — через MCP tool в Claude Code:**

```
connect_nifi(
  name="prod",
  url="https://nifi.example.com:8443",
  auth_method="basic",
  username="admin",
  password="secret"
)
```

Методы аутентификации: `basic`, `certificate_p12`, `certificate_pem`, `knox_jwt`, `knox_cookie`, `knox_passcode`, `no_auth`.

### 4. Переключаться между инстансами NiFi

```
switch_nifi(name="staging")
```

или через Dashboard — кнопка **"Активировать"** напротив нужного подключения.

### 5. Включить write-режим

По умолчанию все подключения работают в **read-only** режиме (безопасно).  
Чтобы разрешить изменения, при подключении передайте `readonly=false`:

```
connect_nifi(name="dev", url="http://localhost:8080", auth_method="no_auth", readonly=false)
```

или через Dashboard — снимите флажок **"Только чтение"** при создании подключения.

### Гарантия работы после перезагрузки

- Контейнер настроен с `restart: always` — автоматически стартует при запуске Docker
- MCP зарегистрирован с `scope: user` — работает во **всех** сеансах Claude Code без повторной настройки
- После перезагрузки Docker должен быть запущен (`sudo systemctl enable docker` на Linux)

---

## Подключение к Claude Code

`setup.sh` регистрирует сервер автоматически. Если нужно вручную:

```bash
claude mcp add --transport http -s user nifi-universal http://localhost:8085/mcp
```

Или добавьте в `~/.claude.json` в секцию `mcpServers`:

```json
{
  "nifi-universal": {
    "type": "http",
    "url": "http://localhost:8085/mcp"
  }
}
```

Перезапустите Claude Code. Сервер появится в списке `/mcp`.

## MCP Tools

### Управление подключениями (6)
| Tool | Описание |
|------|----------|
| `connect_nifi` | Подключиться к NiFi (имя, URL, метод аутентификации) |
| `disconnect_nifi` | Отключиться от NiFi |
| `switch_nifi` | Переключить активное подключение для текущей сессии |
| `list_nifi_connections` | Список всех зарегистрированных подключений |
| `get_server_status` | Статус MCP-шлюза: подключения, сессии |
| `test_nifi_connection` | Тест подключения без сохранения |

### Обзор потоков (20)
| Tool | Описание |
|------|----------|
| `get_nifi_version` | Версия NiFi и информация о сборке |
| `get_root_process_group` | Корневая группа процессов |
| `list_processors` | Список процессоров в группе |
| `list_connections` | Список соединений в группе |
| `get_bulletins` | Системные уведомления и ошибки |
| `list_parameter_contexts` | Контексты параметров |
| `get_controller_services` | Controller-сервисы |
| `get_processor_types` | Доступные типы процессоров |
| `search_flow` | Поиск компонентов по имени |
| `get_connection_details` | Детали соединения (очередь, relationships) |
| `get_processor_details` | Полная конфигурация процессора |
| `list_input_ports` / `list_output_ports` | Порты группы |
| `get_processor_state` | Состояние процессора (RUNNING/STOPPED) |
| `check_connection_queue` | Размер очереди (flowfiles, bytes) |
| `get_flow_summary` | Сводка по группе (счётчики, очереди) |
| `get_flow_health_status` | Полный health-check потока |
| `get_controller_service_details` | Детали controller-сервиса |
| `find_controller_services_by_type` | Поиск сервисов по типу |
| `get_parameter_context_details` | Параметры контекста |

### Рекомендации и шаблоны (5)
| Tool | Описание |
|------|----------|
| `analyze_flow_build_request` | Анализ запроса на построение потока |
| `get_setup_instructions` | Инструкции по настройке |
| `check_configuration` | Валидация конфигурации |
| `get_best_practices_guide` | Руководство по лучшим практикам |
| `get_recommended_workflow` | Рекомендуемый пошаговый workflow |

### Операции записи (41)
| Категория | Tools |
|-----------|-------|
| Процессоры (8) | `start_processor`, `stop_processor`, `create_processor`, `update_processor_config`, `delete_processor`, `terminate_processor`, `start_all_processors_in_group`, `stop_all_processors_in_group` |
| Соединения (3) | `create_connection`, `delete_connection`, `empty_connection_queue` |
| Controller Services (6) | `create_controller_service`, `update_controller_service_properties`, `enable_controller_service`, `disable_controller_service`, `delete_controller_service`, `enable_all_controller_services_in_group` |
| Process Groups (4) | `start_new_flow`, `create_process_group`, `update_process_group_name`, `delete_process_group` |
| Порты (10) | `create_input_port`, `create_output_port`, `update_input_port`, `update_output_port`, `delete_input_port`, `delete_output_port`, `start_input_port`, `stop_input_port`, `start_output_port`, `stop_output_port` |
| Parameter Contexts (4) | `create_parameter_context`, `update_parameter_context`, `delete_parameter_context`, `apply_parameter_context_to_process_group` |

> Write-операции доступны только для подключений с `readonly=false`.

## Dashboard

Веб-интерфейс для управления подключениями: `http://localhost:8085/dashboard`

- Подключение/отключение NiFi инстансов через форму
- Загрузка сертификатов (P12, PEM) через dashboard
- Выбор метода аутентификации из 7 вариантов
- Переключение активного NiFi
- Read-only / Read-Write режим per-connection
- Двуязычный интерфейс (RU/EN)
- Встроенная документация (`/dashboard/docs`)

## Методы аутентификации

| Метод | Описание |
|-------|----------|
| **Certificate (P12)** | PKCS#12 файл с приватным ключом и сертификатом (mTLS) |
| **Certificate (PEM)** | Отдельные PEM/CRT и KEY файлы |
| **Knox JWT Token** | JWT токен для CDP NiFi (как `hadoop-jwt` cookie) |
| **Knox Cookie** | Pre-authenticated session cookie |
| **Knox Passcode** | Passcode token + Knox gateway URL |
| **Basic Auth** | Логин/пароль через Knox token endpoint |
| **No Auth** | Без аутентификации (dev/test) |

## Управление сертификатами

Сертификаты загружаются через Dashboard и хранятся внутри Docker volume (`/data/certs/`):

```
/data/certs/
├── production-nifi/
│   └── keystore.p12
├── staging-nifi/
│   ├── cert.pem
│   └── key.pem
```

Пароли сертификатов сохраняются в state-файле (`/data/nifi_state.json`) и **не возвращаются через API** (маскируются как `***`).

## Конфигурация

Через `.env` или переменные окружения:

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `NIFI_MCP_PORT` | `8085` | Порт сервера |
| `NIFI_MCP_LOG_LEVEL` | `INFO` | Уровень логирования |
| `NIFI_MCP_API_KEY` | — | Bearer token для MCP endpoint |
| `NIFI_MCP_NIFI_API_BASE` | — | URL NiFi для авто-подключения при старте |
| `NIFI_MCP_NIFI_READONLY` | `true` | Read-only по умолчанию |
| `NIFI_MCP_VERIFY_SSL` | `true` | Проверка SSL по умолчанию |
| `NIFI_MCP_HTTP_TIMEOUT` | `30` | Таймаут HTTP-запросов (секунды) |
| `NIFI_MCP_SESSION_TIMEOUT` | `28800` | Idle timeout сессий (секунды, 8 часов) |

## API Endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/mcp` | POST | MCP Streamable HTTP transport |
| `/health` | GET | Health check + статус подключений |
| `/dashboard` | GET | Веб-интерфейс |
| `/dashboard/docs` | GET | Документация |
| `/api/connections` | GET | Список подключений |
| `/api/connect` | POST | Подключить NiFi (multipart/JSON) |
| `/api/disconnect` | POST | Отключить NiFi |
| `/api/edit` | POST | Редактировать подключение |
| `/api/switch` | POST | Переключить активное подключение |
| `/api/test` | POST | Тест подключения |

## Совместимость

- Apache NiFi 1.x, 2.x
- Python 3.12+
- Docker / Docker Compose v2

## Архитектура

```
nifi-mcp-universal/
├── gateway/
│   ├── gateway/
│   │   ├── __main__.py          # Entry point (uvicorn)
│   │   ├── server.py            # Starlette ASGI + MCP transport
│   │   ├── mcp_server.py        # MCP tools dispatch
│   │   ├── config.py            # Settings (Pydantic)
│   │   ├── nifi_registry.py     # Connection registry (JSON)
│   │   ├── nifi_client_manager.py # Multi-NiFi client manager
│   │   ├── web_ui.py            # Dashboard
│   │   ├── nifi/                # Vendored NiFi client
│   │   │   ├── client.py        # NiFi REST API client
│   │   │   ├── auth.py          # Knox/P12/Basic auth
│   │   │   ├── flow_builder.py  # Flow patterns
│   │   │   └── best_practices.py
│   │   └── tools/
│   │       ├── admin.py         # connect/disconnect/switch
│   │       ├── read_tools.py    # 24 read-only tools
│   │       └── write_tools.py   # 42 write tools
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml
├── docker-compose.windows.yml
├── .env.example
└── README.md
```

## Тестирование

Тесты расположены в `gateway/tests/` и покрывают всю кодовую базу без обращений к реальному NiFi.

### Запуск тестов

```bash
cd gateway
python3 -m pytest tests/ -v
```

Быстрый запуск без подробного вывода:

```bash
cd gateway
python3 -m pytest tests/
```

Запуск отдельного модуля:

```bash
cd gateway
python3 -m pytest tests/test_nifi_client.py -v
```

### Структура тестов

| Файл | Покрытие |
|------|---------|
| `test_config.py` | Settings defaults, env-var overrides, префикс NIFI_MCP_ |
| `test_nifi_registry.py` | ConnectionInfo, ConnectionRegistry (add/remove/get/save/load) |
| `test_nifi_client_manager.py` | URL-нормализация, connect/disconnect, session routing, cleanup |
| `test_nifi_client.py` | NiFiClient REST wrappers (GET/PUT/POST/DELETE), version detection |
| `test_nifi_auth.py` | KnoxAuthFactory — все методы аутентификации |
| `test_tools_admin.py` | connect_nifi, disconnect_nifi, switch_nifi, list/status/test |
| `test_tools_read.py` | 25 read-only MCP tools, redact sensitive, error handling |
| `test_tools_write.py` | 42 write MCP tools, readonly guard, tool dispatch |
| `test_mcp_server.py` | list_tools, call_tool dispatch, error handling |
| `test_server.py` | /health endpoint, OAuth endpoints, auth detection |
| `test_best_practices.py` | NiFiBestPractices, analyze_flow_request, SetupGuide |

### Требования

Тесты используют только `pytest` и `pytest-asyncio` (уже установлены в dev-окружении). Все HTTP-запросы к NiFi заменены mock-объектами.

```bash
pip install pytest pytest-asyncio
```

## Стек

- **Python 3.12** + requests + Starlette + uvicorn
- **MCP SDK** >= 1.9.0 (Streamable HTTP transport)
- **Docker** — single container, ~150 MB

## Troubleshooting

### MCP не появляется в `/mcp`

```bash
# Проверить, запущен ли контейнер
docker ps | grep nifi-mcp

# Проверить health endpoint
curl http://localhost:8085/health

# Просмотреть логи контейнера
docker compose logs nifi-mcp-gateway

# Проверить список MCP серверов в Claude Code
claude mcp list

# Перерегистрировать вручную
claude mcp remove nifi-universal -s user 2>/dev/null || true
claude mcp add --transport http -s user nifi-universal http://localhost:8085/mcp
```

### Ошибка подключения к NiFi

- Проверьте URL (включая порт): `https://nifi.example.com:8443` или `http://nifi.example.com:8080`
- Проверьте метод аутентификации — он должен совпадать с настройкой NiFi
- Проверьте доступность NiFi: `curl -k https://nifi.example.com:8443/nifi-api/system-diagnostics`

### SSL certificate error

Если NiFi использует самоподписанный сертификат:

```
connect_nifi(
  name="dev",
  url="https://nifi.internal:8443",
  auth_method="basic",
  username="admin",
  password="secret",
  verify_ssl=false
)
```

Или передайте CA-сертификат через Dashboard (поле "CA Certificate").

### Контейнер не стартует

```bash
# Посмотреть логи
docker compose logs

# Посмотреть статус
docker ps -a | grep nifi-mcp

# Пересобрать и перезапустить
docker compose down && docker compose up -d --build
```

### После перезагрузки не работает

```bash
# Убедиться, что контейнер запущен
docker ps | grep nifi-mcp

# Если не запущен — запустить вручную
docker compose up -d

# На Linux — включить автозапуск Docker
sudo systemctl enable docker
```

### Порт 8085 занят

Откройте `.env` и измените порт:

```bash
# .env
NIFI_MCP_PORT=8086
```

Затем перезапустите:

```bash
docker compose down
./setup.sh
```

### Зависла очередь flowfiles

```
empty_connection_queue(connection_id="...")
```

> Write-операции (`empty_connection_queue`, `start_processor` и др.) доступны только если подключение создано с `readonly=false`.

---

## Благодарности

За основу взят [NiFi-MCP-Server](https://github.com/AlekseiSeleznev/NiFi-MCP-Server) — MCP-сервер для Apache NiFi.

## Лицензия

[MIT](LICENSE)
