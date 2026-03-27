# TLS -- справочник полей

Целевая версия: sing-box 1.14.x
Документирована только клиентская сторона (outbound TLS).

---

## Структура

```json
{
  "enabled": true,
  "disable_sni": false,
  "server_name": "example.com",
  "insecure": false,
  "alpn": ["h2", "http/1.1"],
  "min_version": "1.2",
  "max_version": "1.3",
  "cipher_suites": [],
  "curve_preferences": [],
  "certificate": "",
  "certificate_path": "",
  "certificate_public_key_sha256": [],
  "client_certificate": [],
  "client_certificate_path": "",
  "client_key": [],
  "client_key_path": "",
  "fragment": false,
  "fragment_fallback_delay": "500ms",
  "record_fragment": false,
  "utls": {
    "enabled": false,
    "fingerprint": ""
  },
  "reality": {
    "enabled": false,
    "public_key": "",
    "short_id": ""
  },
  "ech": {
    "enabled": false,
    "config": [],
    "config_path": "",
    "query_server_name": ""
  }
}
```

---

## Основные поля

| Поле | Тип | Описание | Значения / По умолчанию |
|------|-----|----------|-------------------------|
| `enabled` | bool | Включить TLS | По умолчанию `false` |
| `disable_sni` | bool | Не отправлять имя сервера в ClientHello | По умолчанию `false` |
| `server_name` | string | Имя сервера для проверки сертификата и SNI. Если адрес -- IP, необходимо указать явно | строка |
| `insecure` | bool | Принимать любой сертификат сервера (небезопасно) | По умолчанию `false` |
| `alpn` | string[] | Список протоколов ALPN в порядке предпочтения | `["h2", "http/1.1"]` и т.д. |
| `min_version` | string | Минимальная версия TLS | `1.0`, `1.1`, `1.2`, `1.3`. По умолчанию `1.2` для клиента |
| `max_version` | string | Максимальная версия TLS | `1.0`, `1.1`, `1.2`, `1.3`. По умолчанию `1.3` |
| `cipher_suites` | string[] | Список допустимых cipher suites (TLS 1.0-1.2). Порядок не имеет значения. TLS 1.3 не настраивается | см. таблицу ниже |
| `curve_preferences` | string[] | Механизмы обмена ключами (с 1.13). Порядок не имеет значения, Go выбирает внутренний приоритет | `P256`, `P384`, `P521`, `X25519`, `X25519MLKEM768` |
| `certificate` | string | Сертификат CA в формате PEM (для pin-проверки) | строка PEM |
| `certificate_path` | string | Путь к файлу сертификата CA в формате PEM | путь к файлу |
| `certificate_public_key_sha256` | string[] | SHA-256 хеши публичных ключей сервера в base64 (certificate pinning, с 1.13) | массив base64-строк |
| `client_certificate` | string[] | Клиентский сертификат (mTLS, с 1.13), PEM | массив строк PEM |
| `client_certificate_path` | string | Путь к клиентскому сертификату (mTLS, с 1.13) | путь к файлу |
| `client_key` | string[] | Приватный ключ клиента (mTLS, с 1.13), PEM | массив строк PEM |
| `client_key_path` | string | Путь к приватному ключу клиента (mTLS, с 1.13) | путь к файлу |

---

## uTLS

Библиотека для имитации TLS-отпечатков браузеров. Подменяет структуру ClientHello.

> **Предупреждение:** uTLS неоднократно оказывалась уязвимой к обнаружению
> исследователями. Браузеры используют другие TLS-стеки (Chrome -- BoringSSL,
> Firefox -- NSS), поведение которых невозможно полностью воспроизвести копированием
> формата хендшейка. Используйте uTLS как дополнительную меру, а не как основную
> защиту от DPI.

| Поле | Тип | Описание | Значения / По умолчанию |
|------|-----|----------|-------------------------|
| `utls.enabled` | bool | Включить uTLS | По умолчанию `false` |
| `utls.fingerprint` | string | Отпечаток браузера | см. таблицу ниже. По умолчанию `chrome` (если пустая строка) |

**Таблица fingerprint:**

| Значение | Описание |
|----------|----------|
| `chrome` | Google Chrome (используется, если поле пустое) |
| `firefox` | Mozilla Firefox |
| `edge` | Microsoft Edge |
| `safari` | Apple Safari |
| `360` | 360 Browser |
| `qq` | QQ Browser |
| `ios` | iOS Safari |
| `android` | Android |
| `random` | Случайный из списка |
| `randomized` | Рандомизированный отпечаток |

---

## Reality

Протокол маскировки TLS, использующий ключевую пару вместо сертификатов.
Ниже описаны только клиентские поля.

| Поле | Тип | Обязательное | Описание | Значения / По умолчанию |
|------|-----|:---:|----------|-------------------------|
| `reality.enabled` | bool | нет | Включить Reality | По умолчанию `false` |
| `reality.public_key` | string | да | Публичный ключ сервера, сгенерированный `sing-box generate reality-keypair` | base64 строка |
| `reality.short_id` | string | нет | Короткий идентификатор, hex-строка от 0 до 8 символов | например `"0123456789abcdef"` |

---

## ECH

ECH (Encrypted Client Hello) -- расширение TLS, шифрующее первую часть
ClientHello, включая SNI. Скрывает имя целевого сервера от промежуточных узлов.

| Поле | Тип | Описание | Значения / По умолчанию |
|------|-----|----------|-------------------------|
| `ech.enabled` | bool | Включить ECH | По умолчанию `false` |
| `ech.config` | string[] | Конфигурация ECH в формате PEM. Если пуст -- загружается из DNS (HTTPS-запись) | массив строк PEM |
| `ech.config_path` | string | Путь к файлу конфигурации ECH в PEM. Если пуст -- загружается из DNS | путь к файлу |
| `ech.query_server_name` | string | Переопределяет домен для HTTPS-запроса ECH-конфигурации (с 1.13). Если пуст -- используется `server_name` | строка |

---

## TLS Fragment (обход DPI)

Фрагментация TLS-хендшейка для обхода простых DPI-фильтров, работающих
на основе сопоставления пакетов в открытом виде. Доступно с sing-box 1.12.

| Поле | Тип | Описание | Значения / По умолчанию |
|------|-----|----------|-------------------------|
| `fragment` | bool | Фрагментация TLS-хендшейка на уровне TCP | По умолчанию `false` |
| `fragment_fallback_delay` | string (duration) | Фиксированная задержка, если автоопределение времени ожидания невозможно | По умолчанию `500ms` |
| `record_fragment` | bool | Фрагментация хендшейка на уровне TLS-записей (лучше производительность, чем `fragment`) | По умолчанию `false` |

> **Рекомендация:** сначала попробуйте `record_fragment` -- он эффективнее и меньше
> влияет на скорость. Используйте `fragment` только если `record_fragment` не помогает.

> **Windows:** при наличии прав администратора время ожидания определяется автоматически.
> Если фактическое время меньше 20мс, sing-box считает цель локальной и переключается
> на фиксированную задержку `fragment_fallback_delay`.

---

## Таблица cipher suites

Настраиваются только для TLS 1.0-1.2. Cipher suites TLS 1.3 управляются автоматически.

| Значение |
|----------|
| `TLS_RSA_WITH_AES_128_CBC_SHA` |
| `TLS_RSA_WITH_AES_256_CBC_SHA` |
| `TLS_RSA_WITH_AES_128_GCM_SHA256` |
| `TLS_RSA_WITH_AES_256_GCM_SHA384` |
| `TLS_AES_128_GCM_SHA256` |
| `TLS_AES_256_GCM_SHA384` |
| `TLS_CHACHA20_POLY1305_SHA256` |
| `TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA` |
| `TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA` |
| `TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA` |
| `TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA` |
| `TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256` |
| `TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384` |
| `TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256` |
| `TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384` |
| `TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256` |
| `TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256` |

---

## Примеры

### 1. Стандартный TLS + uTLS

```json
{
  "enabled": true,
  "server_name": "example.com",
  "alpn": ["h2", "http/1.1"],
  "utls": {
    "enabled": true,
    "fingerprint": "chrome"
  }
}
```

### 2. Reality

```json
{
  "enabled": true,
  "server_name": "www.microsoft.com",
  "utls": {
    "enabled": true,
    "fingerprint": "chrome"
  },
  "reality": {
    "enabled": true,
    "public_key": "jNXHt1yRo0vDuchQlIP6Z0ZvjT3KtzVI-T4E7RoLJS0",
    "short_id": "0123456789abcdef"
  }
}
```

### 3. TLS + record_fragment (обход DPI)

```json
{
  "enabled": true,
  "server_name": "example.com",
  "utls": {
    "enabled": true,
    "fingerprint": "chrome"
  },
  "record_fragment": true
}
```

### 4. ECH

```json
{
  "enabled": true,
  "server_name": "example.com",
  "ech": {
    "enabled": true
  }
}
```
