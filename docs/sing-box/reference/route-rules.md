# Route -- справочник полей

Целевая версия: **sing-box 1.14.x** | Платформа: **Windows**

---

## Route (верхний уровень)

### Структура

```json
{
  "route": {
    "rules": [],
    "rule_set": [],
    "final": "",
    "auto_detect_interface": false,
    "default_interface": "",
    "default_domain_resolver": "",
    "find_process": false
  }
}
```

### Поля

| Поле | Тип | Описание | По умолчанию |
|------|-----|----------|--------------|
| `rules` | `Rule[]` | Список правил маршрутизации | `[]` |
| `rule_set` | `RuleSet[]` | Список наборов правил (inline/local/remote) | `[]` |
| `final` | `string` | Тег outbound по умолчанию; если пусто -- первый outbound | `""` |
| `auto_detect_interface` | `bool` | Привязка к NIC по умолчанию; предотвращает петли при TUN | `false` |
| `default_interface` | `string` | Привязка к конкретному NIC (альтернатива `auto_detect_interface`) | `""` |
| `default_domain_resolver` | `string` или `object` | DNS-резолвер для outbound по умолчанию (с 1.12) | `""` |
| `find_process` | `bool` | Поиск процесса для логов, когда нет process-правил | `false` |

### Rule-set (краткая справка)

```json
{
  "route": {
    "rule_set": [
      {
        "type": "remote",
        "tag": "geosite-ru",
        "format": "binary",
        "url": "https://example.com/geosite-ru.srs",
        "download_detour": "proxy",
        "update_interval": "24h"
      },
      {
        "type": "local",
        "tag": "my-rules",
        "format": "source",
        "path": "ruleset/my-rules.json"
      }
    ]
  }
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `type` | `string` | `"inline"` (с 1.10), `"local"`, `"remote"` |
| `tag` | `string` | Уникальный тег для ссылки из правил |
| `format` | `string` | `"source"` (JSON) или `"binary"` (SRS) |
| `path` | `string` | Путь к файлу (для `local`) |
| `url` | `string` | URL для скачивания (для `remote`) |
| `download_detour` | `string` | Outbound для скачивания |
| `update_interval` | `string` | Интервал обновления, например `"24h"` |

> Для кеширования remote rule-set необходимо `experimental.cache_file.enabled: true`.

---

## Правила маршрутизации (route rules)

### Структура правила

```json
{
  "route": {
    "rules": [
      {
        "domain_suffix": [".ru", ".su"],
        "action": "route",
        "outbound": "proxy"
      }
    ]
  }
}
```

### Формула матчинга

Внутри одной группы условий действует логика **OR** (любое совпадение).
Между группами действует логика **AND** (все группы должны совпасть).

```
(domain || domain_suffix || domain_keyword || domain_regex) &&
(ip_cidr || ip_is_private) &&
(port || port_range) &&
(source_ip_cidr || source_ip_is_private) &&
(source_port || source_port_range) &&
остальные_поля
```

Ветки внутри подключённого rule-set объединяются по OR, но каждая ветка мержится с внешним правилом.

### Match-условия (Windows)

| Поле | Тип | Описание | С версии |
|------|-----|----------|----------|
| `inbound` | `string[]` | Теги inbound | -- |
| `ip_version` | `int` | `4` или `6` | -- |
| `network` | `string[]` | `"tcp"`, `"udp"`, `"icmp"` (icmp с 1.13, только из TUN) | -- |
| `protocol` | `string[]` | Sniffed-протокол: `http`, `tls`, `quic`, `dns`, `stun`, `bittorrent`, `dtls`, `ssh`, `rdp`, `ntp` | -- |
| `client` | `string[]` | Sniffed-клиент: `chromium`, `safari`, `firefox`, `quic-go` | 1.10 |
| `domain` | `string[]` | Полное совпадение домена | -- |
| `domain_suffix` | `string[]` | Суффикс домена (`.ru`, `.example.com`) | -- |
| `domain_keyword` | `string[]` | Ключевое слово в домене | -- |
| `domain_regex` | `string[]` | Регулярное выражение для домена | -- |
| `ip_cidr` | `string[]` | CIDR назначения (`10.0.0.0/8`, `192.168.0.1`) | -- |
| `ip_is_private` | `bool` | Не-публичный IP назначения | 1.8 |
| `source_ip_cidr` | `string[]` | CIDR источника | -- |
| `source_ip_is_private` | `bool` | Не-публичный IP источника | 1.8 |
| `port` | `int[]` | Порт(ы) назначения | -- |
| `port_range` | `string[]` | Диапазон портов: `"1000:2000"`, `":3000"`, `"4000:"` | -- |
| `source_port` | `int[]` | Порт(ы) источника | -- |
| `source_port_range` | `string[]` | Диапазон портов источника | -- |
| `process_name` | `string[]` | Имя исполняемого файла (`chrome.exe`) | -- |
| `process_path` | `string[]` | Полный путь к исполняемому файлу | -- |
| `process_path_regex` | `string[]` | Regex для пути процесса | 1.10 |
| `clash_mode` | `string` | Режим Clash API (`direct`, `global`, `rule`) | -- |
| `interface_address` | `object` | Совпадение по адресу интерфейса `{"eth0": ["10.0.0.0/8"]}` | 1.13 |
| `default_interface_address` | `string[]` | Совпадение по адресу интерфейса по умолчанию | 1.13 |
| `rule_set` | `string[]` | Теги rule-set | 1.8 |
| `rule_set_ip_cidr_match_source` | `bool` | IP-правила в rule-set матчат source IP | 1.10 |
| `invert` | `bool` | Инвертировать результат матча | -- |

> Массивы с одним элементом можно писать как строку: `"domain": "example.com"`.

### Логические правила

```json
{
  "type": "logical",
  "mode": "and",
  "rules": [
    {"domain_suffix": ".example.com"},
    {"port": [80, 443]}
  ],
  "invert": false,
  "action": "route",
  "outbound": "proxy"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `type` | `string` | `"logical"` |
| `mode` | `string` | `"and"` или `"or"` (обязательно) |
| `rules` | `Rule[]` | Вложенные правила (обязательно) |
| `invert` | `bool` | Инвертировать результат |

---

## Действия (rule actions)

### route (финальное)

Маршрутизация к указанному outbound.

```json
{
  "action": "route",
  "outbound": "proxy"
}
```

| Поле | Тип | Описание | Обязательно |
|------|-----|----------|-------------|
| `outbound` | `string` | Тег outbound | да |

Может включать поля `route-options` (см. ниже) для inline-настроек.

### reject (финальное)

Отклонение соединения.

```json
{
  "action": "reject",
  "method": "default",
  "no_drop": false
}
```

| Поле | Тип | Описание | По умолчанию |
|------|-----|----------|--------------|
| `method` | `string` | TCP/UDP: `"default"` (RST + ICMP unreachable), `"drop"` (тихо). ICMP echo: `"default"` (unreachable), `"drop"`, `"reply"` (с 1.13) | `"default"` |
| `no_drop` | `bool` | Если `false`, после 50 срабатываний за 30 сек method переключается на `"drop"` | `false` |

### hijack-dns (финальное)

Перенаправляет DNS-запросы в DNS-модуль sing-box. Дополнительных полей нет.

```json
{
  "action": "hijack-dns"
}
```

### sniff (нефинальное)

Определение протокола соединения.

```json
{
  "action": "sniff",
  "sniffer": ["tls", "http", "quic"],
  "timeout": "300ms"
}
```

| Поле | Тип | Описание | По умолчанию |
|------|-----|----------|--------------|
| `sniffer` | `string[]` | Протоколы для определения; если пусто -- все включены | все |
| `timeout` | `string` | Таймаут определения | `"300ms"` |

### resolve (нефинальное)

Резолв домена в IP-адреса перед маршрутизацией.

```json
{
  "action": "resolve",
  "server": "bootstrap",
  "strategy": "prefer_ipv4",
  "disable_cache": false,
  "rewrite_ttl": null,
  "client_subnet": null
}
```

| Поле | Тип | Описание | По умолчанию |
|------|-----|----------|--------------|
| `server` | `string` | Тег DNS-сервера | `""` |
| `strategy` | `string` | `prefer_ipv4`, `prefer_ipv6`, `ipv4_only`, `ipv6_only` | из `dns.strategy` |
| `disable_cache` | `bool` | Отключить кеш для этого запроса (с 1.12) | `false` |
| `rewrite_ttl` | `int?` | Перезаписать TTL в ответе (с 1.12) | `null` |
| `client_subnet` | `string?` | EDNS0-subnet (с 1.12) | `null` |

### route-options (нефинальное)

Настройки маршрутизации. Можно использовать как самостоятельное действие или inline внутри `route`.

```json
{
  "action": "route-options",
  "override_address": "",
  "override_port": 0,
  "udp_disable_domain_unmapping": false,
  "udp_connect": false,
  "udp_timeout": "",
  "tls_fragment": false,
  "tls_fragment_fallback_delay": "500ms",
  "tls_record_fragment": ""
}
```

| Поле | Тип | Описание | По умолчанию |
|------|-----|----------|--------------|
| `override_address` | `string` | Подменить адрес назначения | `""` |
| `override_port` | `int` | Подменить порт назначения | `0` |
| `udp_disable_domain_unmapping` | `bool` | Отправлять оригинальный адрес пакета в UDP-ответе | `false` |
| `udp_connect` | `bool` | Подключаться к UDP-назначению вместо прослушивания | `false` |
| `udp_timeout` | `string` | Таймаут UDP-соединений | по протоколу |
| `tls_fragment` | `bool` | Фрагментация TLS handshake для обхода DPI (с 1.12) | `false` |
| `tls_fragment_fallback_delay` | `string` | Задержка, если авто-определение времени недоступно (с 1.12) | `"500ms"` |
| `tls_record_fragment` | `string` | Фрагментация на уровне TLS-записей -- лучше производительность (с 1.12) | `""` |

---

## Протоколы sniff

| Сеть | Протокол | Извлекаемая информация |
|------|----------|------------------------|
| TCP | `http` | Host header -- домен |
| TCP | `tls` | SNI -- домен |
| UDP | `quic` | SNI + тип клиента (chromium/safari/firefox/quic-go) -- домен |
| UDP | `stun` | STUN binding |
| TCP/UDP | `dns` | DNS-запрос |
| TCP/UDP | `bittorrent` | Info hash |
| UDP | `dtls` | DTLS fingerprint |
| TCP | `ssh` | SSH-протокол |
| TCP | `rdp` | RDP-протокол |
| UDP | `ntp` | NTP-протокол |

**UDP-таймауты по протоколу:** `dns`/`ntp`/`stun` -- 10s, `quic`/`dtls` -- 30s.
**Определение по порту (без sniff):** 53 -- dns, 123 -- ntp, 443 -- quic, 3478 -- stun.

---

## Не поддерживается на Windows

Следующие match-условия недоступны на Windows:

| Поле | Платформа |
|------|-----------|
| `user`, `user_id` | Linux |
| `package_name` | Android |
| `wifi_ssid`, `wifi_bssid` | Android / Apple / Linux |
| `network_type`, `network_is_expensive`, `network_is_constrained` | Android / Apple |
| `network_interface_address` | Android / Apple |
| `source_mac_address`, `source_hostname` | Linux / macOS (с 1.14) |
| `preferred_by` | WireGuard / Tailscale outbound (с 1.13) |

Недоступные поля верхнего уровня `route`:

| Поле | Платформа |
|------|-----------|
| `default_mark` | Linux |
| `override_android_vpn` | Android |
| `find_neighbor`, `dhcp_lease_files` | Linux / macOS (с 1.14) |
| `default_network_strategy`, `default_network_type`, `default_fallback_network_type`, `default_fallback_delay` | Android / Apple |

---

## Примеры

### 1. Sniff + DNS hijack (стандартные первые два правила)

```json
{
  "route": {
    "rules": [
      {"action": "sniff"},
      {"protocol": "dns", "action": "hijack-dns"}
    ]
  }
}
```

### 2. Обход для защищённого процесса (прокси-клиент не проксирует себя)

```json
{
  "process_name": ["xray.exe", "sing-box.exe"],
  "action": "route",
  "outbound": "direct"
}
```

### 3. Обход LAN-трафика

```json
{
  "ip_is_private": true,
  "action": "route",
  "outbound": "direct"
}
```

### 4. Маршрутизация по процессу

```json
{
  "process_name": "firefox.exe",
  "action": "route",
  "outbound": "proxy"
}
```

```json
{
  "process_path_regex": "^C:\\\\Program Files\\\\Google\\\\.*",
  "action": "route",
  "outbound": "proxy"
}
```

### 5. Маршрутизация по домену

```json
{
  "domain_suffix": [".ru", ".su"],
  "domain_keyword": ["yandex", "mail"],
  "action": "route",
  "outbound": "direct"
}
```

### 6. Логическое правило (AND)

```json
{
  "type": "logical",
  "mode": "and",
  "rules": [
    {"process_name": "chrome.exe"},
    {"port": [80, 443]}
  ],
  "action": "route",
  "outbound": "proxy"
}
```

### 7. Правило с TLS-фрагментацией (обход DPI)

```json
{
  "domain_suffix": ".blocked-site.com",
  "action": "route",
  "outbound": "proxy",
  "tls_fragment": true,
  "tls_fragment_fallback_delay": "400ms"
}
```
