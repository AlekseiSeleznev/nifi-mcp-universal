# Источник NiFi-клиента

Источник: [cloudera/NiFi-MCP-Server](https://github.com/cloudera/NiFi-MCP-Server).
Проверенная ревизия `main`:
[`9af7ce2930814e974d9c8b26330f7b2cb7431324`](https://github.com/cloudera/NiFi-MCP-Server/commit/9af7ce2930814e974d9c8b26330f7b2cb7431324).

На 4 октября 2026 года в опубликованном `main` нет более новых коммитов.
Открытые PR #1 (standalone authentication) и #2 (diagnostics/provenance)
не входят в принятую версию источника и в это обновление не включены.

Локальная версия содержит собственные доработки multi-NiFi, dashboard,
сертификатной аутентификации, изоляции сессий и ограниченного подсчёта
provenance. При обновлении нельзя заменять её файлами upstream целиком.
Нужно сравнить изменения между закреплённой ревизией и новым `main`, перенести
совместимые изменения и повторить тесты, включая проверки секретов и readonly.

Происхождение и лицензия заимствованного кода записаны в
[THIRD_PARTY_NOTICES.md](../gateway/THIRD_PARTY_NOTICES.md); лицензия также
включается в Docker-образ.

Для Windows CI выполняет `install.ps1` в Windows PowerShell 5.1 и PowerShell 7
с изолированными заглушками Docker, Codex и health endpoint. Проверяются
создание `.env`, сохранение заданных порта и Bearer-настроек, установка skill,
регистрация MCP и ошибки запуска/регистрации. Отдельно реальный Python gateway
проходит MCP handshake в Windows. Эти проверки не заменяют запуск Linux
контейнера внутри Docker Desktop на Windows: GitHub-hosted Windows runner
такую конфигурацию здесь не проверяет.
