# Architecture

Этот документ описывает устройство Web/Yandex-порта Pingus на уровне, достаточном для безопасной поддержки и релизов.

## Общая схема

```text
Original Pingus 0.7.6
        │
        ▼
Source/data patches
        │
        ├── browser runtime
        ├── Yandex Games integration
        ├── localization/content audit
        ├── performance fixes
        └── Web UI/input fixes
        │
        ▼
Emscripten build
        │
        ▼
self-contained pingus.js
        │
        ├── index.html
        ├── bootstrap.js
        └── pingus.css
        │
        ▼
CSP postprocess + source package
        │
        ▼
Smoke tests
        │
        ▼
Yandex Games ZIP
```

## Runtime layers

### 1. Native Pingus layer

Оригинальный C++ код игры компилируется Emscripten. На этом уровне находятся игровой цикл, уровни, персонажи, физика, world map, меню, локализация tinygettext и software rendering.

### 2. Browser bridge

Web-обвязка отвечает за то, чего нет в обычной desktop-версии:

- `<canvas>` и его масштабирование;
- состояние вкладки/страницы;
- паузу и возобновление аудио;
- IDBFS;
- browser input;
- декоративное заполнение пространства вокруг 4:3 framebuffer;
- первый готовый кадр и loading UI.

### 3. Yandex Games bridge

Yandex-слой не должен менять основную игровую механику. Его задачи:

- инициализировать SDK;
- сообщать Game Ready;
- управлять Gameplay API;
- ставить игру на platform pause;
- показывать interstitial только в логических паузах;
- синхронизировать прогресс через Player Data;
- получать язык платформы.

## Сохранения

Pingus продолжает работать с собственными save-файлами. Порт добавляет два уровня хранения:

```text
Native save files
   │
   ├── IDBFS -> IndexedDB
   │
   └── cloud mirror -> Yandex Player Data
```

Локальное хранение является fallback. Облачная синхронизация не должна приводить к потере уже завершённых уровней.

## Реклама

Запрос interstitial инициируется экраном результата уровня, а не таймером внутри активного геймплея. Между показами действует cooldown.

При открытии рекламы:

1. игровой runtime получает platform pause;
2. аудио останавливается;
3. текущее состояние синхронизируется;
4. после закрытия/ошибки состояние восстанавливается.

## Локализация

Английский остаётся исходным языком оригинала. Для русского языка pipeline:

1. готовит ограниченный релизный PO-каталог;
2. добавляет Web/Yandex-safe строки;
3. устраняет конфликтующие записи;
4. проверяет реально достижимые player-facing строки;
5. добавляет Web-only кириллические glyph atlas там, где оригинальных bitmap-глифов недостаточно.

## CSP

Финальный архив проходит postprocess, чтобы работать под nonce-based Content-Security-Policy платформы. Inline script/style/event handlers не должны оставаться в итоговом `index.html`.

## Производительность

Pingus использует software rendering, поэтому Web-сборка содержит точечные оптимизации:

- ограничение catch-up update;
- сокращение лишних offscreen операций;
- упрощённые minimap updates;
- оптимизации большого количества пингусов;
- фиксированный логический framebuffer 800×600.

## Принцип изменений

Приоритет проекта:

> Сначала сохранить оригинальное поведение Pingus, затем исправлять только то, что требуется браузером, производительностью или правилами платформы.

Изменения оригинальной графики, уровней и игровой логики должны быть минимальными и иметь понятную причину.
