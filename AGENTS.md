# AGENTS.md

Нейтральная инструкция для подключения любого MCP-клиента к `nifi-mcp-universal`.

Этот файл описывает ручной onboarding без привязки к конкретному бренду клиента.

## 1. Что должен поддерживать клиент

Нужен клиент, который умеет работать со streamable HTTP transport для Model Context Protocol.

MCP URL:

```text
http://localhost:8085/mcp
```

Дополнительные URL:

```text
http://localhost:8085/health
http://localhost:8085/dashboard
http://localhost:8085/dashboard/docs
```

## 2. Как установить сам gateway

### Linux / macOS

```bash
git clone https://github.com/AlekseiSeleznev/nifi-mcp-universal.git
cd nifi-mcp-universal
./setup.sh
```

### Windows

```powershell
git clone https://github.com/AlekseiSeleznev/nifi-mcp-universal.git
cd nifi-mcp-universal
.\install.ps1
```

Если нужен только runtime без helper-скриптов, можно поднять gateway напрямую:

```bash
cp .env.example .env
docker compose up -d --build
```

На Windows:

```powershell
docker compose -f docker-compose.yml -f docker-compose.windows.yml up -d --build
```

## 3. Что передать клиенту

Минимальная конфигурация:

- server name: `nifi-universal`
- transport type: streamable HTTP
- MCP URL: `http://localhost:8085/mcp`

Если клиент поддерживает отдельную настройку Bearer token, включайте её только когда в `.env` задан `NIFI_MCP_API_KEY`.

## 4. Режим без Bearer auth

По умолчанию `NIFI_MCP_API_KEY` пустой. В этом режиме достаточно одного URL:

```text
http://localhost:8085/mcp
```

## 5. Режим с Bearer auth

Если в `.env` задано:

```text
NIFI_MCP_API_KEY=your-secret
```

то клиент должен отправлять:

```text
Authorization: Bearer your-secret
```

Это относится и к dashboard API endpoints:

- `/api/status`
- `/api/connections`
- `/api/connect`
- `/api/disconnect`
- `/api/edit`
- `/api/switch`
- `/api/test`

HTML dashboard остаётся доступным, но API без Bearer token вернут `401`.

## 6. Что ещё проверить

- Docker daemon действительно запущен;
- `http://localhost:8085/health` отвечает `200`;
- порт из `NIFI_MCP_PORT` доступен клиенту;
- на Linux используется host networking;
- на Windows/macOS нужен bridge mode и проброс порта;
- если включён `NIFI_MCP_API_KEY`, клиент реально умеет отправлять Bearer token для streamable HTTP MCP.

## 7. Диагностика

```bash
docker compose logs nifi-mcp-gateway
curl http://localhost:8085/health
curl http://localhost:8085/dashboard
```

Если клиент не коннектится:

1. проверьте, что endpoint `/mcp` достижим;
2. проверьте, не включён ли `NIFI_MCP_API_KEY`;
3. проверьте Bearer token, если auth включён;
4. убедитесь, что gateway уже поднят и отвечает на `/health`.

## 8. Cleanup и удаление

Linux/macOS:

```bash
./uninstall.sh
```

Windows:

```powershell
.\uninstall.ps1
```

Если вы поднимали gateway вручную без helper-скриптов, достаточно project-scoped cleanup:

```bash
docker compose down -v --remove-orphans --rmi local || true
docker image rm nifi-mcp-gateway 2>/dev/null || true
```

## 9. Работа с NiFi после подключения

После регистрации MCP-сервера в вашем клиенте:

- откройте dashboard и добавьте connection к NiFi;
- либо вызовите `connect_nifi(...)`;
- для безопасного старта оставляйте `readonly=true`;
- write-операции включайте только там, где это действительно нужно.

## 10. Agent protocol (правила работы для AI-клиента)

Этот раздел — самодостаточный source of truth для любого AI-клиента. Те же правила gateway также публикует в `initialize.instructions`; текст хранится в `gateway/gateway/mcp_server.py::AGENT_INSTRUCTIONS`.

Коротко:

- **Intent recognition.** Фразы «используем NiFi `<имя>`», «работаем с NiFi `<имя>`», «подключись к NiFi `<имя>`», «NiFi / Apache NiFi / нифи», любые NiFi-термины (processor в dataflow-контексте, process group, controller service, flowfile, bulletin, relationship, parameter context, имена GetFile/PutFile/InvokeHTTP/ConsumeKafka и т.п.) → **этот MCP**. При упоминании инстанса: `list_nifi_connections` → если есть, `switch_nifi`; иначе попросить URL+auth и `connect_nifi` (default `readonly=true`). Если пользователь сказал «X» без указания системы — `list_nifi_connections`; если есть — работаем, если нет — честно сказать «в NiFi-MCP такой регистрации нет», не выдумывать.
- **Все NiFi-задачи — через MCP `nifi-mcp-universal`** (`http://localhost:8085/mcp`). Не гадать REST-пути и имена свойств.
- **Pre-flight:** `list_nifi_connections` → если пусто, `connect_nifi` с `readonly=true` → `test_nifi_connection` → `get_root_process_group`.
- **Safe update:** всегда сначала `get_*_details` для взятия `version` (оптимистическая блокировка NiFi API).
- **Создание компонентов:** сначала тип (`get_processor_types`, `find_controller_services_by_type`), потом `create_*`.
- **Опасные операции** (`delete_*`, `empty_connection_queue`, `*_all_processors_in_group`) — ТОЛЬКО после явного «да» пользователя.
- **Fallback запрещён:** если backend недоступен или соединение не зарегистрировано — сообщить пользователю, не писать HTTP-вызовы руками.
- **Готовые сценарии** публикуются через `prompts/list`: `connect_and_inspect`, `diagnose_flow_health`, `build_flow_from_request`, `safe_processor_update`, `stop_all_safely`.

### Частые ошибки (не наступать)

1. **Читай `inputSchema` из `tools/list` перед первым вызовом.** Большинство tool-level ошибок (`'X' is a required property`) — из-за выдуманных имён аргументов.
2. **Optimistic locking NiFi API.** Все write-инструменты (`update_*`, `delete_*`, `start_*`, `stop_*`, `enable_*`, `disable_*`, `terminate_*`) требуют поле `version`. Протокол: сначала `get_processor_details` / `get_controller_service_details` / `get_connection_details` → взять `version` → передать его в write. При conflict — перечитать details и повторить ОДИН раз. Не выдумывай version.
3. **Навигация начинается с `get_root_process_group`**. Большинство list/create берут `process_group_id`, а меньшинство (`get_flow_health_status`, `start_all_processors_in_group`, `stop_all_processors_in_group`, `delete_process_group`, все `*_port`) — `pg_id`. Это **разные** поля — смотри schema, не путай.
4. **`update_processor_config.config`** — форма зависит от типа процессора; сначала `get_processor_details`, чтобы узнать реальные свойства. Ключи не угадывать.
5. **`create_connection`** требует И `source_type` И `destination_type` (`PROCESSOR`/`INPUT_PORT`/`OUTPUT_PORT`) И массив `relationships`. Без `relationships` — 400.
6. **`apply_parameter_context_to_process_group`** — нужен И `pg_version` И свежий `context_id` (обе версии актуальные).
7. **`readonly=true`** на подключении — все write вернут 403. При ошибке write проверь режим через `list_nifi_connections` и скажи пользователю «переподключиться с `readonly=false`».
8. **Активная регистрация — per-session** через `switch_nifi`. Параллельные сессии могут смотреть на разные NiFi-инстансы независимо.
9. **HTTP 404 или зависшая сессия** — gateway удалил устаревшую сессию. Переинициализируй (`initialize` + `notifications/initialized`), не ретраи со старым `Mcp-Session-Id`.
10. **Перед деструктивом** (`empty_connection_queue`, все `delete_*`, `start_all_processors_in_group`, `stop_all_processors_in_group`, `enable_all_controller_services_in_group`) — покажи пользователю полный план (id/имена) и дождись явного «да».
