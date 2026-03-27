# Multiplex — справочник полей

Целевая версия: sing-box 1.14.x
Только клиентская сторона (outbound multiplex).

Мультиплексирование позволяет пропускать несколько соединений через
одно TCP-соединение, снижая задержку handshake.

## Структура

```json
{
  "enabled": true,
  "protocol": "h2mux",
  "max_connections": 4,
  "min_streams": 4,
  "max_streams": 0,
  "padding": false,
  "brutal": {}
}
```

## Поля

### enabled

Включить мультиплексирование.

Тип: `bool`

### protocol

Протокол мультиплексирования.

| Протокол | Описание |
|----------|----------|
| smux     | [github.com/xtaci/smux](https://github.com/xtaci/smux) |
| yamux    | [github.com/hashicorp/yamux](https://github.com/hashicorp/yamux) |
| h2mux    | [golang.org/x/net/http2](https://golang.org/x/net/http2) |

По умолчанию используется `h2mux`.

### max_connections

Максимальное количество соединений.

Тип: `int`

Конфликтует с `max_streams`.

### min_streams

Минимальное количество потоков в соединении, прежде чем будет открыто
новое соединение.

Тип: `int`

Конфликтует с `max_streams`.

### max_streams

Максимальное количество потоков в соединении, прежде чем будет открыто
новое соединение.

Тип: `int`

Конфликтует с `max_connections` и `min_streams`.

### padding

Включить паддинг (дополнение пакетов). Требуется сервер sing-box
версии 1.3-beta9 или новее.

Тип: `bool`

### brutal

Настройка управления перегрузкой TCP Brutal. Подробности см. в
документации TCP Brutal. Необязательное поле для специфичных сценариев.

Тип: `object`

## Пример

Мультиплексирование с протоколом yamux:

```json
{
  "enabled": true,
  "protocol": "yamux",
  "max_connections": 4,
  "min_streams": 4,
  "padding": true
}
```
