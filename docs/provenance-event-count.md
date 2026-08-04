# Безопасный подсчёт provenance-событий

`get_provenance_event_count` — read-only MCP tool для подсчёта событий одного
NiFi-компонента за ограниченное окно времени.

## Вход

Разрешены только следующие поля:

- `component_id` — идентификатор компонента;
- `start_time` и `end_time` — обязательные ISO-8601 timestamps с timezone,
  образующие положительное окно не более 24 часов;
- `event_type` — необязательный allowlist-тип provenance-события.

Произвольный `raw_search`, filename, FlowFile UUID, URI, payload и другие
поисковые поля не поддерживаются.

## Жизненный цикл

Gateway формирует ограниченный запрос с фильтрами `ProcessorID`, `EventType`
(если задан), `startDate` и `endDate`, а также с `summarize=true` и
`incrementalResults=false`. Затем он выполняет ровно один HTTP-attempt для
каждого шага:

1. `POST /provenance`;
2. bounded `GET /provenance/{query_id}` polling до `finished=true`;
3. `DELETE /provenance/{query_id}` в `finally` после получения безопасного
   query id, включая timeout и ошибки polling.

POST/GET/DELETE этого lifecycle не используют автоматические retries. GET —
только явный bounded polling. Gateway не скачивает и не воспроизводит content,
не запрашивает lineage и не возвращает события.

В POST всегда передаётся обязательный для NiFi 2.8 `maxResults=1000`. Значение
зафиксировано внутри gateway и не является входом MCP: это положительный bounded
лимит, достаточный для безопасного gate `0`/`nonzero`. Поэтому `total_count`
ограничивается `1000` (NiFi представляет такой результат как `1000+`), и
инструмент не обещает точное значение выше этого лимита.

Публичные `start_time` и `end_time` остаются ISO-8601 с timezone. Для NiFi 2.8
gateway принимает только whole-second timestamps: явное `.000` допустимо, но
любая ненулевая fractional second отклоняется fail-closed до HTTP, без тихого
усечения значимой границы. Перед POST каждый timestamp переводится в формат
NiFi 2.x `MM/dd/yyyy HH:mm:ss GMT±HH:MM`, сохраняя исходный offset и абсолютный
момент времени. Каждый status GET явно передаёт `summarize=true` и
`incrementalResults=false`, как это делает интерфейс NiFi 2.8.

## Результат и fail-closed

Наружу возвращаются только:

```json
{
  "finished": true,
  "total_count": 0,
  "error_count": 0,
  "cleanup_status": "success"
}
```

При incomplete/timeout/auth/API-ошибке или неоднозначном cleanup значения
счётчиков остаются `null`, а не превращаются в нули. Возможные безопасные
статусы cleanup: `success`, `failure`, `unknown`, `not_attempted`.
Query id, URI, provenance events, attributes, filenames, URLs, payload/content,
employee data и raw errors наружу не выдаются.

## Требуемые NiFi policies

При включённой авторизации пользователю нужны:

- API policy **Read `/provenance`** для REST lifecycle запроса;
- global policy **query provenance**;
- component policy **view provenance** для компонента, создавшего событие.

Policy **view the data** для этого инструмента не нужна: он не получает детали
событий, FlowFile attributes или content. Подробности см. в официальном
[NiFi REST API](https://nifi.apache.org/docs/nifi-docs/rest-api/) и
[NiFi User Guide, Data Provenance](https://nifi.apache.org/nifi-docs/user-guide.html#data-provenance).
