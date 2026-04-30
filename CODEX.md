# CODEX.md

Руководство по подключению `nifi-mcp-universal` к Codex.

> **Правила работы AI-ассистента** (какие инструменты в каком порядке вызывать, когда отказываться вместо выдумывания) описаны в [`AGENTS.md`](AGENTS.md) (секция «Agent protocol»). MCP-сервер также возвращает агрегированный `instructions`-блок при `initialize`, поэтому современные MCP-клиенты подмешивают те же правила в системный контекст автоматически. Ниже — только Codex-специфичные шаги развёртывания.

Этот файл описывает Codex-специфичную часть. Базовая установка gateway теперь не требует `codex` и может выполняться отдельно.

## Распознавание намерения — когда маршрутизировать сюда

- **Триггер-фразы**: «NiFi / Apache NiFi / нифи», «используем NiFi `<имя>`», «работаем с NiFi `<имя>`», «подключись к NiFi `<имя>`», «в NiFi `<имя>`», «switch to NiFi `<name>`».
- **NiFi-терминология**: processor (в dataflow-контексте), process group / PG, controller service, flowfile, bulletin, relationship, queue backlog, parameter context, provenance, имена процессоров (GetFile, PutFile, GenerateFlowFile, InvokeHTTP, ListenHTTP, ConsumeKafka).
- **Типовые имена регистраций**: `prod-nifi`, `dev-nifi`, `<env>-nifi`, `nifi-<cluster>`. URL NiFi обычно заканчивается на `/nifi-api` (порты 8080/9443).
- **Когда пользователь назвал инстанс**: `list_nifi_connections` → если есть, `switch_nifi`; иначе попросить URL + auth и `connect_nifi` (по умолчанию `readonly=true`).
- **«X» без указания системы** — `list_nifi_connections` здесь; если есть — работаем, если нет — честно сказать «в NiFi-MCP такой регистрации нет» и попросить уточнение. Не выдумывать.

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

## 1. Что нужно иметь

- установленный gateway;
- `codex` в `PATH`;
- доступный MCP URL:

```text
http://localhost:8085/mcp
```

Проверьте:

```bash
docker compose ps
codex --version
curl http://localhost:8085/health
```

## 2. Базовая установка gateway

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

Если `codex` уже установлен, установщик попытается зарегистрировать сервер автоматически. Если `codex` отсутствует, gateway всё равно установится. Bundled skill `nifi-flow-layout` устанавливается отдельно от MCP-регистрации, простым копированием в локальный каталог Codex skills.

## 3. Проверка после установки

```bash
curl http://localhost:8085/health
curl http://localhost:8085/dashboard
codex mcp get nifi-universal --json
python3 ~/.codex/skills/nifi-flow-layout/scripts/nifi_layout.py --mode self-test
```

Если `codex mcp get` падает, это означает только то, что Codex-регистрация не была выполнена автоматически. Gateway при этом может быть полностью исправен. Если self-test skill падает, переустановите bundled skills командой `./tools/install-codex-skills.sh`.

## 4. Bundled skill `nifi-flow-layout`

`nifi-flow-layout` — универсальный Codex skill для визуальной нормализации Apache NiFi process groups. Он не содержит NiFi hosts, токенов, сертификатов, group-id или customer-specific defaults. Все параметры передаются при запуске.

Установка:

```bash
./tools/install-codex-skills.sh
```

Windows:

```powershell
.\tools\install-codex-skills.ps1
```

По умолчанию файлы копируются в:

```text
~/.codex/skills/nifi-flow-layout
```

Путь можно переопределить:

```bash
CODEX_SKILLS_DIR=/custom/codex/skills ./tools/install-codex-skills.sh
```

Self-test:

```bash
python3 ~/.codex/skills/nifi-flow-layout/scripts/nifi_layout.py --mode self-test
```

После установки перезапустите или обновите Codex session, чтобы клиент увидел новый skill.

Подробные команды `audit`, `dry-run`, `apply`, Playwright screenshot/DOM validation и layout conventions описаны в [docs/nifi-flow-layout.md](docs/nifi-flow-layout.md).

## 5. Ручная регистрация в Codex

### Без Bearer auth

```bash
codex mcp remove nifi-universal || true
codex mcp add nifi-universal --url http://localhost:8085/mcp
codex mcp get nifi-universal --json
```

### С Bearer auth

Если в `.env` задан:

```text
NIFI_MCP_API_KEY=your-secret
```

то перед регистрацией экспортируйте тот же ключ:

```bash
export NIFI_MCP_API_KEY='your-secret'
codex mcp remove nifi-universal || true
codex mcp add nifi-universal \
  --url http://localhost:8085/mcp \
  --bearer-token-env-var NIFI_MCP_API_KEY
codex mcp get nifi-universal --json
```

Если ключ задан в `.env`, но не экспортирован в shell, `setup.sh` и `install.ps1` не будут валить установку gateway, а просто пропустят автоматическую Codex-регистрацию.

## 6. Что именно регистрируется в Codex

Минимальный конфиг без auth:

```json
{
  "mcpServers": {
    "nifi-universal": {
      "type": "streamable_http",
      "url": "http://localhost:8085/mcp"
    }
  }
}
```

С Bearer auth:

```json
{
  "mcpServers": {
    "nifi-universal": {
      "type": "streamable_http",
      "url": "http://localhost:8085/mcp",
      "bearer_token_env_var": "NIFI_MCP_API_KEY"
    }
  }
}
```

## 7. Linux: что переживает перезагрузку

- контейнер запускается с `restart: always`;
- `setup.sh` устанавливает и сразу запускает Linux unit `nifi-mcp-universal` без forced rebuild на boot;
- ожидаемый статус `systemctl status nifi-mcp-universal`: `active (exited)`, потому что unit одноразово вызывает `docker compose up -d`, а сам gateway живёт внутри контейнера;
- Codex registration хранится в локальной конфигурации Codex.

Полезные команды:

```bash
systemctl status nifi-mcp-universal
sudo systemctl restart nifi-mcp-universal
```

## 8. Windows: особенности

- штатный путь установки: `install.ps1`;
- Docker Desktop должен быть запущен;
- `install.ps1` вызывает `tools/ensure-docker-autostart-windows.ps1`;
- Git Bash и WSL больше не являются обязательным единственным вариантом для Windows.

## 9. Cleanup и полное удаление

### Минимальный cleanup для Codex

```bash
codex mcp remove nifi-universal || true
```

### Project-scoped cleanup gateway

Linux/macOS:

```bash
./uninstall.sh
```

Windows:

```powershell
.\uninstall.ps1
```

Скрипты удаляют проектовые Docker-артефакты, Linux unit, generated override и локальную Codex-регистрацию, если `codex` доступен.

## 10. Fresh install / destroy-reclone loop

Linux/macOS:

```bash
./uninstall.sh
cd ..
rm -rf nifi-mcp-universal
git clone https://github.com/AlekseiSeleznev/nifi-mcp-universal.git
cd nifi-mcp-universal
./setup.sh
codex mcp get nifi-universal --json
cd gateway
python3 -m pytest tests/ -v --cov=gateway --cov-branch --cov-report=term-missing --cov-fail-under=100
```

Windows:

```powershell
.\uninstall.ps1
Set-Location ..
Remove-Item -Recurse -Force nifi-mcp-universal
git clone https://github.com/AlekseiSeleznev/nifi-mcp-universal.git
cd nifi-mcp-universal
.\install.ps1
codex mcp get nifi-universal --json
cd gateway
python -m pytest tests/ -v --cov=gateway --cov-branch --cov-report=term-missing --cov-fail-under=100
```

## 11. Когда использовать AGENTS.md

Если вы подключаете не Codex, используйте [AGENTS.md](AGENTS.md). Этот файл нужен только для Codex-specific onboarding и cleanup.
