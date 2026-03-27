# Dial Fields -- справочник полей

Целевая версия: sing-box 1.14.x
Только поля, поддерживаемые на Windows.

Dial Fields используются во всех outbound'ах и DNS-серверах.

## Структура

```json
{
  "detour": "",
  "bind_interface": "",
  "inet4_bind_address": "",
  "inet6_bind_address": "",
  "connect_timeout": "",
  "tcp_fast_open": false,
  "tcp_multi_path": false,
  "disable_tcp_keep_alive": false,
  "tcp_keep_alive": "5m",
  "tcp_keep_alive_interval": "75s",
  "udp_fragment": false,
  "reuse_addr": false,
  "domain_resolver": ""
}
```

## Поля

### detour

| | |
|---|---|
| Тип | `string` |

Тег вышестоящего outbound. Если задан, все остальные dial-поля игнорируются. Используется DNS-серверами для маршрутизации запросов через прокси.

### bind_interface

| | |
|---|---|
| Тип | `string` |

Привязка к конкретному сетевому интерфейсу (имя адаптера).

### inet4_bind_address

| | |
|---|---|
| Тип | `string` |

IPv4-адрес для привязки исходящего соединения.

**Важно для hybrid mode:** значение `"127.0.0.1"` не даёт `auto_detect_interface` привязать SOCKS-relay к физическому адаптеру, предотвращая петлю маршрутизации.

### inet6_bind_address

| | |
|---|---|
| Тип | `string` |

IPv6-адрес для привязки исходящего соединения.

### connect_timeout

| | |
|---|---|
| Тип | `string` (duration) |

Тайм-аут установки соединения. Формат: golang duration (см. раздел ниже).

### tcp_fast_open

| | |
|---|---|
| Тип | `bool` |
| По умолчанию | `false` |

Включить TCP Fast Open (TFO).

### tcp_multi_path

| | |
|---|---|
| Тип | `bool` |
| По умолчанию | `false` |

Включить Multipath TCP (MPTCP). Требуется Go 1.21+.

### disable_tcp_keep_alive

| | |
|---|---|
| Тип | `bool` |
| По умолчанию | `false` |
| С версии | 1.13.0 |

Отключить TCP keepalive.

### tcp_keep_alive

| | |
|---|---|
| Тип | `string` (duration) |
| По умолчанию | `"5m"` |
| С версии | 1.13.0 |

Начальный период TCP keepalive.

### tcp_keep_alive_interval

| | |
|---|---|
| Тип | `string` (duration) |
| По умолчанию | `"75s"` |
| С версии | 1.13.0 |

Интервал между TCP keepalive-пакетами.

### udp_fragment

| | |
|---|---|
| Тип | `bool` |
| По умолчанию | `false` |

Включить фрагментацию UDP.

### reuse_addr

| | |
|---|---|
| Тип | `bool` |
| По умолчанию | `false` |

Повторное использование адреса слушателя (`SO_REUSEADDR`).

### domain_resolver

| | |
|---|---|
| Тип | `string` или `object` |
| С версии | 1.12.0 |
| Обязательно в 1.14 | да, для outbound с доменным адресом сервера |

Резолвер для разрешения доменных имён. Строковое значение эквивалентно полю `server` в объектной форме. Объектная форма совпадает с форматом DNS route action без поля `"action"`.

| Тип outbound | Что резолвит |
|--------------|--------------|
| `direct` | Домен из запроса |
| остальные | Домен из адреса сервера |

Пример (строка):
```json
{ "domain_resolver": "bootstrap-dns" }
```

Пример (объект):
```json
{ "domain_resolver": { "server": "bootstrap-dns", "strategy": "ipv4_only" } }
```

## Формат длительности (duration)

Строка из десятичных чисел с суффиксом единицы измерения.

| Единица | Суффикс |
|---------|---------|
| наносекунды | `ns` |
| микросекунды | `us` |
| миллисекунды | `ms` |
| секунды | `s` |
| минуты | `m` |
| часы | `h` |

Примеры: `"300ms"`, `"5s"`, `"1m"`, `"2h45m"`.

## Не поддерживается на Windows

| Поле | Платформа / причина |
|------|---------------------|
| `routing_mark` | Linux (netfilter) |
| `netns` | Linux (network namespaces, 1.12) |
| `bind_address_no_port` | Linux (1.13) |
| `network_strategy` | Android / Apple (графические клиенты) |
| `network_type` | Android / Apple (графические клиенты) |
| `fallback_network_type` | Android / Apple (графические клиенты) |
| `fallback_delay` | Android / Apple (графические клиенты) |
| `domain_strategy` | удалено в 1.14, заменено на `domain_resolver` |
