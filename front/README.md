# GAIA UI

React + TypeScript + Vite + TailwindCSS + TanStack Query.

## Структура

```
src/
  api/           — HTTP-клиент для Core API
  components/
    layout/      — Sidebar и общий layout
    ui/          — Базовые UI (Button, Card, Badge, Input)
    agents/     — Компоненты для агентов
  pages/         — Страницы (Dashboard, Agents, AgentDetail)
  hooks/         — Кастомные React-хуки
  lib/           — Утилиты (cn, formatRelativeTime)
  types/         — TypeScript-типы из API
```

## Локальная разработка

```bash
cd frontend
npm install
npm run dev
```

Откроется на `http://localhost:3000`, проксирует `/api` на `http://localhost:8000` (Core).

## Production

Запуск через docker-compose:

```yaml
services:
  core:
    build: .
    ports: ["8000:8000"]

  ui:
    build: ./frontend
    ports: ["80:80"]
    depends_on: [core]
```

После сборки фронт хостится в nginx, проксирующем `/api/*` на Core.
UI доступен на `http://server/`, API docs — на `http://server/docs`.

## Что готово в MVP

- **Dashboard** — статистика по агентам, проблемные машины, список семей
- **Agents** — таблица с фильтрами по семье и hostname, поиск
- **Agent detail** — табы:
  - Overview — метаданные, статус, текущая версия
  - History — история применений конфигов
  - Files — управляемые файлы со статусом синхронизации
  - Snapshot — последний JSON-снимок состояния
  - Read file — live-чтение произвольного файла через `/exec/read-file`
- **Auto-refresh** — все списки обновляются каждые 10-15 сек
- **Dark mode** — кнопка в шапке sidebar

## Что добавим следующими итерациями

- Families page — список семей, массовый пуш конфигов
- Config editor — редактор конфигов с подсветкой синтаксиса YAML/JSON
- Diff view — визуальное сравнение версий конфигов
- Commands page — история ad-hoc команд
- Bulk actions — выделить агентов → применить конфиг
- AD/SSO авторизация
