# Changelog

## v1.0.0 (2026-04-16)

- Стартовый публичный выпуск репозитория.
- В состав релиза входят:
  - streamable HTTP MCP gateway для Apache NiFi;
  - dashboard для подключения и переключения NiFi-инстансов;
  - `66` MCP tools;
  - нейтральный install flow для Linux/macOS/Windows;
  - `CODEX.md` для Codex и `AGENTS.md` для других MCP-клиентов;
  - non-root Docker runtime;
  - multi-arch GHCR publish workflow;
  - test suite с покрытием `100%` line + branch.
- В стартовое состояние также включены обязательные security-фиксы:
  - `hmac.compare_digest` для Bearer auth и `/oauth/token`;
  - whitelist для dashboard `lang`;
  - `chmod 600` для временных и загружаемых cert/key файлов;
  - атомарная запись state-файла;
  - ограничение размера request body для dashboard API;
  - sanitization клиентских сообщений об ошибках.
