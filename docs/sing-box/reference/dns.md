# DNS -- справочник полей

Целевая версия: **sing-box 1.14.x** | Платформа: **Windows**

---

## DNS (верхний уровень)

### Структура

```json
{
  "dns": {
    "servers": [],
    "rules": [],
    "final": "",
    "strategy": "",
    "disable_cache": false,
    "disable_expire": false,
    "independent_cache": false,
    "cache_capacity": 0,
    "reverse_mapping": false,
    "client_subnet": "",
    "fakeip": {}
  }
}
```

### Поля

| Поле | Тип | Описание | По умолчанию |
|------|-----|----------|--------------|
| `servers` | `Server[]` | Список DNS-серверов | `[]` |
| `rules` | `Rule[]` | Список DNS-правил | `[]` |
| `final` | `string` | Тег DNS-сервера по умолчанию; если пусто -- первый сервер | `""` |
| `strategy` | `string` | Стратегия: `prefer_ipv4`, `prefer_ipv6`, `ipv4_only`, `ipv6_only` | `""` |
| `disable_cache` | `bool` | Отключить DNS-кеш | `false` |
| `disable_expire` | `bool` | Не удалять записи из кеша по TTL | `false` |
| `independent_cache` | `bool` | Отдельный кеш для каждого сервера (немного снижает производительность) | `false` |
| `cache_capacity` | `int` | Размер LRU-кеша; значения < 1024 игнорируются (с 1.11) | `0` |
| `reverse_mapping` | `bool` | Хранить маппинг IP -- домен для маршрутизации | `false` |
| `client_subnet` | `string` | EDNS0-subnet OPT-запись (IP или префикс) (с 1.9) | `""` |
| `fakeip` | `object` | Конфигурация FakeIP (см. раздел ниже) | `{}` |

> **Осторожно:** `reverse_mapping` может работать некорректно на Windows из-за системного DNS-кеша и проксирования DNS.

---

## DNS-серверы

### udp

DNS через UDP. Простейший и быстрый вариант.

```json
{
  "type": "udp",
  "tag": "bootstrap",
  "server": "1.1.1.1",
  "server_port": 53
}
```

| Поле | Тип | Описание | По умолчанию |
|------|-----|----------|--------------|
| `server` | `string` | Адрес DNS-сервера (обязательно) | -- |
| `server_port` | `int` | Порт | `53` |

Поддерживает Dial Fields (`domain_resolver`, `bind_interface` и др.).

### tcp

DNS через TCP. Надёжнее UDP для больших ответов.

```json
{
  "type": "tcp",
  "tag": "tcp-dns",
  "server": "1.1.1.1",
  "server_port": 53
}
```

| Поле | Тип | Описание | По умолчанию |
|------|-----|----------|--------------|
| `server` | `string` | Адрес DNS-сервера (обязательно) | -- |
| `server_port` | `int` | Порт | `53` |

Поддерживает Dial Fields.

### tls (DoT)

DNS over TLS -- шифрованные запросы.

```json
{
  "type": "tls",
  "tag": "dot-dns",
  "server": "1.1.1.1",
  "server_port": 853,
  "tls": {}
}
```

| Поле | Тип | Описание | По умолчанию |
|------|-----|----------|--------------|
| `server` | `string` | Адрес DNS-сервера (обязательно) | -- |
| `server_port` | `int` | Порт | `853` |
| `tls` | `object` | Конфигурация TLS | `{}` |

Поддерживает Dial Fields.

### https (DoH)

DNS over HTTPS -- шифрованные запросы через HTTP/2.

```json
{
  "type": "https",
  "tag": "doh-dns",
  "server": "1.1.1.1",
  "server_port": 443,
  "path": "/dns-query",
  "headers": {},
  "tls": {}
}
```

| Поле | Тип | Описание | По умолчанию |
|------|-----|----------|--------------|
| `server` | `string` | Адрес DNS-сервера (обязательно) | -- |
| `server_port` | `int` | Порт | `443` |
| `path` | `string` | URL-путь запроса | `"/dns-query"` |
| `headers` | `object` | Дополнительные HTTP-заголовки | `{}` |
| `tls` | `object` | Конфигурация TLS | `{}` |

Поддерживает Dial Fields.

### local

Использует системный DNS-резолвер Windows.

```json
{
  "type": "local",
  "tag": "local-dns"
}
```

Дополнительных обязательных полей нет. Поддерживает Dial Fields.

### hosts

Поиск в hosts-файлах и предопределённых записях.

```json
{
  "type": "hosts",
  "tag": "hosts-dns",
  "path": ["C:\\Windows\\System32\\Drivers\\etc\\hosts"],
  "predefined": {
    "my-server.local": "192.168.1.100"
  }
}
```

| Поле | Тип | Описание | По умолчанию |
|------|-----|----------|--------------|
| `path` | `string[]` | Пути к hosts-файлам | Windows: `C:\Windows\System32\Drivers\etc\hosts` |
| `predefined` | `object` | Предопределённые записи (домен -- IP или массив IP) | `{}` |

### fakeip

Виртуальная выдача IP-адресов. Требует секцию `dns.fakeip`.

```json
{
  "type": "fakeip",
  "tag": "fakeip-dns"
}
```

Дополнительных полей нет. Диапазоны адресов задаются в `dns.fakeip`.

---

## DNS-правила

### Match-условия

Условия аналогичны route rules (см. route-rules.md) плюс специфичные для DNS:

| Поле | Тип | Описание | С версии |
|------|-----|----------|----------|
| `query_type` | `string[] / int[]` | Тип DNS-запроса: `"A"`, `"AAAA"`, `"HTTPS"` или числовой код | -- |
| `domain`, `domain_suffix`, `domain_keyword`, `domain_regex` | `string[]` | Совпадение по домену запроса | -- |
| `process_name`, `process_path`, `process_path_regex` | `string[]` | Совпадение по процессу (Windows) | -- |
| `rule_set` | `string[]` | Теги rule-set | 1.8 |
| `clash_mode` | `string` | Режим Clash API | -- |
| `inbound` | `string[]` | Теги inbound | -- |
| `port`, `port_range`, `source_port`, `source_port_range` | | Порты | -- |
| `source_ip_cidr`, `source_ip_is_private` | | Источник | -- |

> Поле `outbound` удалено в 1.14. Используйте `domain_resolver` на outbound вместо него.

### Фильтры по адресу ответа

Эти поля фильтруют DNS-ответы. Если ответ не совпадает -- правило пропускается.
Работают только для запросов типа A/AAAA/HTTPS.

| Поле | Тип | Описание | С версии |
|------|-----|----------|----------|
| `ip_cidr` | `string[]` | Совпадение IP в DNS-ответе с CIDR | 1.9 |
| `ip_is_private` | `bool` | Совпадение с приватным IP в ответе | 1.9 |
| `ip_accept_any` | `bool` | Совпадение с любым IP в ответе | 1.12 |
| `rule_set_ip_cidr_accept_empty` | `bool` | Принимать пустой ответ при IP-матче из rule-set | 1.10 |
| `rule_set_ip_cidr_match_source` | `bool` | IP-правила из rule-set матчат source IP | 1.10 |

> Для кеширования результатов включите `experimental.cache_file.store_rdrc`.

### Действия

#### route

Направляет DNS-запрос к указанному серверу.

```json
{
  "action": "route",
  "server": "bootstrap",
  "strategy": "prefer_ipv4",
  "disable_cache": false,
  "rewrite_ttl": null,
  "client_subnet": null
}
```

| Поле | Тип | Описание | По умолчанию |
|------|-----|----------|--------------|
| `server` | `string` | Тег DNS-сервера (обязательно) | -- |
| `strategy` | `string` | `prefer_ipv4`, `prefer_ipv6`, `ipv4_only`, `ipv6_only` (с 1.12) | из `dns.strategy` |
| `disable_cache` | `bool` | Отключить кеш | `false` |
| `rewrite_ttl` | `int?` | Перезаписать TTL | `null` |
| `client_subnet` | `string?` | EDNS0-subnet | `null` |

#### route-options

Устанавливает опции без смены сервера.

```json
{
  "action": "route-options",
  "disable_cache": false,
  "rewrite_ttl": null,
  "client_subnet": null
}
```

#### reject

Отклонение DNS-запроса.

```json
{
  "action": "reject",
  "method": "default",
  "no_drop": false
}
```

| Поле | Тип | Описание | По умолчанию |
|------|-----|----------|--------------|
| `method` | `string` | `"default"` (REFUSED) или `"drop"` (тихо) | `"default"` |
| `no_drop` | `bool` | Если `false`, после 50 срабатываний за 30 сек переключается на `"drop"` | `false` |

#### predefined (с 1.12)

Ответ предопределёнными DNS-записями.

```json
{
  "action": "predefined",
  "rcode": "NOERROR",
  "answer": ["localhost. IN A 127.0.0.1"],
  "ns": [],
  "extra": []
}
```

| Поле | Тип | Описание | По умолчанию |
|------|-----|----------|--------------|
| `rcode` | `string` | Код ответа: `NOERROR`, `FORMERR`, `SERVFAIL`, `NXDOMAIN`, `NOTIMP`, `REFUSED` | `"NOERROR"` |
| `answer` | `string[]` | Записи-ответы (формат: `name. IN TYPE value`) | `[]` |
| `ns` | `string[]` | NS-записи | `[]` |
| `extra` | `string[]` | Дополнительные записи | `[]` |

---

## FakeIP

### Структура

```json
{
  "dns": {
    "fakeip": {
      "enabled": true,
      "inet4_range": "198.18.0.0/15",
      "inet6_range": "fc00::/18"
    }
  }
}
```

### Поля

| Поле | Тип | Описание | По умолчанию |
|------|-----|----------|--------------|
| `enabled` | `bool` | Включить FakeIP | `false` |
| `inet4_range` | `string` | IPv4 диапазон для виртуальных адресов | `"198.18.0.0/15"` |
| `inet6_range` | `string` | IPv6 диапазон для виртуальных адресов | `"fc00::/18"` |

> Для сохранения FakeIP-маппингов между перезапусками включите `experimental.cache_file.store_fakeip`.

---

## Паттерн "bootstrap + proxy"

В TUN-режиме DNS-запросы проходят через тот же TUN-интерфейс, что создаёт петлю маршрутизации:
DNS -> TUN -> DNS-модуль -> DNS-сервер -> TUN -> ...

Решение -- два DNS-сервера:

1. **bootstrap** -- без detour, для резолва домена прокси-сервера. Использует IP-адрес напрямую.
2. **proxy** -- с detour через прокси, для всего остального трафика.

```json
{
  "dns": {
    "servers": [
      {
        "type": "udp",
        "tag": "bootstrap",
        "server": "1.1.1.1",
        "server_port": 53
      },
      {
        "type": "tcp",
        "tag": "proxy-dns",
        "server": "8.8.8.8",
        "server_port": 53,
        "detour": "proxy"
      }
    ],
    "rules": [
      {
        "domain_suffix": ".proxy-server.com",
        "action": "route",
        "server": "bootstrap"
      }
    ],
    "final": "proxy-dns"
  },
  "route": {
    "auto_detect_interface": true
  }
}
```

**Обязательно** включайте `auto_detect_interface: true` в секции `route` при использовании TUN.

---

## Примеры

### 1. Стандартная двухсерверная конфигурация

```json
{
  "dns": {
    "servers": [
      {
        "type": "udp",
        "tag": "bootstrap",
        "server": "1.1.1.1",
        "server_port": 53
      },
      {
        "type": "tcp",
        "tag": "proxy-dns",
        "server": "8.8.8.8",
        "server_port": 53,
        "detour": "proxy"
      }
    ],
    "final": "proxy-dns",
    "strategy": "prefer_ipv4"
  }
}
```

### 2. DoH bootstrap + DoT proxy

```json
{
  "dns": {
    "servers": [
      {
        "type": "https",
        "tag": "bootstrap",
        "server": "1.1.1.1",
        "server_port": 443,
        "path": "/dns-query"
      },
      {
        "type": "tls",
        "tag": "proxy-dns",
        "server": "8.8.8.8",
        "server_port": 853,
        "detour": "proxy"
      }
    ],
    "final": "proxy-dns"
  }
}
```

### 3. DNS с FakeIP

```json
{
  "dns": {
    "servers": [
      {
        "type": "udp",
        "tag": "bootstrap",
        "server": "1.1.1.1"
      },
      {
        "type": "fakeip",
        "tag": "fakeip-dns"
      }
    ],
    "rules": [
      {
        "query_type": ["A", "AAAA"],
        "action": "route",
        "server": "fakeip-dns"
      }
    ],
    "final": "bootstrap",
    "fakeip": {
      "enabled": true,
      "inet4_range": "198.18.0.0/15",
      "inet6_range": "fc00::/18"
    }
  }
}
```

### 4. DNS-правило: конкретные домены на bootstrap

```json
{
  "domain_suffix": [".ru", ".su"],
  "action": "route",
  "server": "bootstrap"
}
```

### 5. DNS-правило: блокировка рекламных доменов

```json
{
  "rule_set": "adblock-domains",
  "action": "reject",
  "method": "default"
}
```
