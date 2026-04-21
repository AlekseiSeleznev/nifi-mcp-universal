# Инструкции для AI-ассистентов (Claude Code / Codex / Cursor)

Протокол работы AI-ассистента с `nifi-mcp-universal`. Claude Code автоматически подхватывает `CLAUDE.md` при открытии репозитория; Codex читает `AGENTS.md`.

---

## TL;DR

Любая задача по Apache NiFi (инспекция потока, создание/обновление/удаление процессоров и контроллер-сервисов, диагностика очередей, работа с параметр-контекстами) **делается через MCP-сервер `nifi-mcp-universal`** (`http://localhost:8085/mcp`).

**Не гадай пути API и имена свойств процессоров из памяти. Сначала вызывай MCP. Если инструмент недоступен — скажи об этом пользователю, не имитируй ответ.**

---

## Распознавание намерения — когда маршрутизировать сюда

**Фразы, пинящие сессию на этот MCP:**
- «NiFi / Apache NiFi / нифи», «используем NiFi `<имя>`», «работаем с NiFi `<имя>`», «подключись к NiFi `<имя>`», «в NiFi `<имя>`», «switch to NiFi `<name>`».

**NiFi-терминология — любой маркер ниже → этот MCP:**
processor (в dataflow-контексте), process group / PG, controller service, flowfile, bulletin, relationship, queue backlog, parameter context, provenance, имена процессоров (GetFile, PutFile, GenerateFlowFile, InvokeHTTP, ListenHTTP, ConsumeKafka).

**Типовые имена регистраций:** `prod-nifi`, `dev-nifi`, `<env>-nifi`, `nifi-<cluster>`. URL NiFi обычно заканчивается на `/nifi-api` (порты 8080/9443).

**Что делать, когда пользователь назвал инстанс** («используем NiFi prod»):
1. `list_nifi_connections` — если `prod` есть → `switch_nifi name=prod`.
2. Если нет — спросить URL + auth и вызвать `connect_nifi` (по умолчанию `readonly=true`).

**Если пользователь сказал просто «X»** без явного указания системы — вызови `list_nifi_connections` здесь; если `X` есть — работаем с ним, если нет — честно сообщи «в NiFi-MCP такой регистрации нет» и попроси уточнения. Не выдумывай подключение.

---

## Pre-flight перед любой задачей

1. `list_nifi_connections` — есть ли зарегистрированное соединение.
2. Если пусто — запросить у пользователя URL и метод аутентификации, вызвать `connect_nifi` с `readonly=true` (безопасный дефолт).
3. `test_nifi_connection` — перед тяжёлой операцией.
4. `get_root_process_group` — любая навигация начинается здесь; запомни id корневого PG для последующих `list_*`.

---

## Инспекция потока

`list_processors`, `list_connections`, `list_input_ports`, `list_output_ports`, `get_processor_details` (**всегда забирай `version` — нужен для безопасных update'ов**), `check_connection_queue`, `get_bulletins`, `get_flow_health_status`, `get_flow_summary`, `search_flow`.

---

## Запись / модификация (только при `readonly=false`)

- **Создать процессор:** сначала `get_processor_types`, потом `create_processor`.
- **Создать controller service:** сначала `find_controller_services_by_type` (избежать дублей), затем `create_controller_service`.
- **Обновить процессор / controller-service:** получить `*_details`, взять `version`, потом `update_processor_config` / `update_controller_service_properties` с этим `version`. Если вернулся conflict — перечитать details и повторить один раз.
- **Проектировать новый flow по запросу:** сначала `analyze_flow_build_request` — возвращает AI-friendly план.

---

## Опасные (необратимые) операции — всегда запрашивать явное подтверждение

- `empty_connection_queue`
- `delete_processor`, `delete_connection`, `delete_controller_service`, `delete_process_group`
- `delete_input_port`, `delete_output_port`
- `start_all_processors_in_group`, `stop_all_processors_in_group`, `enable_all_controller_services_in_group`

Показать пользователю что именно будет сделано (список id/имён), попросить «да», только потом вызвать.

---

## Категории инструментов

| Категория | Инструменты |
|---|---|
| Соединения | `connect_nifi`, `disconnect_nifi`, `switch_nifi`, `list_nifi_connections`, `test_nifi_connection`, `get_server_status` |
| Чтение | `get_nifi_version`, `get_root_process_group`, `list_processors`, `list_connections`, `list_input_ports`, `list_output_ports`, `get_bulletins`, `list_parameter_contexts`, `get_parameter_context_details`, `get_controller_services`, `find_controller_services_by_type`, `get_controller_service_details`, `get_processor_types`, `get_processor_details`, `get_processor_state`, `get_connection_details`, `check_connection_queue`, `search_flow`, `get_flow_summary`, `get_flow_health_status`, `analyze_flow_build_request`, `get_setup_instructions`, `check_configuration`, `get_best_practices_guide`, `get_recommended_workflow` |
| Процессоры | `start_processor`, `stop_processor`, `create_processor`, `update_processor_config`, `delete_processor`, `terminate_processor` |
| Групповые операции | `start_all_processors_in_group`, `stop_all_processors_in_group`, `enable_all_controller_services_in_group` |
| Соединения (связи) | `create_connection`, `delete_connection`, `empty_connection_queue` |
| Контроллер-сервисы | `create_controller_service`, `update_controller_service_properties`, `enable_controller_service`, `disable_controller_service`, `delete_controller_service` |
| Process Groups | `start_new_flow`, `create_process_group`, `update_process_group_name`, `delete_process_group` |
| Порты | `create_input_port`, `create_output_port`, `update_input_port`, `update_output_port`, `delete_input_port`, `delete_output_port`, `start_input_port`, `stop_input_port`, `start_output_port`, `stop_output_port` |
| Параметр-контексты | `create_parameter_context`, `update_parameter_context`, `delete_parameter_context`, `apply_parameter_context_to_process_group` |

---

## Готовые MCP-prompts

Сервер отдаёт `prompts/list`:

- **connect_and_inspect** — подключиться (или переиспользовать) и показать обзор.
- **diagnose_flow_health** — триаж: bulletins, очереди, invalid-сервисы, остановленные процессоры.
- **build_flow_from_request** (arg: `request`) — дизайн нового flow по описанию пользователя.
- **safe_processor_update** (arg: `processor_id`) — безопасное обновление с капчей `version`.
- **stop_all_safely** (arg: `pg_id`) — массовая остановка с подтверждением.

---

## Частые ошибки (не наступать)

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

---

## Поведение при сбоях

| Ситуация | Поведение |
|---|---|
| `list_nifi_connections` пуст | Запросить у пользователя URL/auth, вызвать `connect_nifi` |
| `test_nifi_connection` упал | Сообщить ошибку + первопричину (сеть/сертификат/креды), не гадать |
| Write-операция вернула 403 / readonly | Сказать пользователю: «соединение в readonly-режиме; переподключиться через `connect_nifi(..., readonly=false)`» |
| Update вернул version conflict | Один раз перечитать details и повторить с новым version |
| `get_server_status` показывает красное | Указать конкретный бэкенд и ссылку на дашборд |
