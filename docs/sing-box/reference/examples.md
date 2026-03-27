# Примеры конфигураций sing-box

Целевая версия: **sing-box 1.14.x**

Все примеры ниже — полные, синтаксически валидные JSON-конфиги для Windows.
Каждый пример содержит секции `log`, `inbounds`, `outbounds`, `route`, `dns`
и `experimental`.

Структура и имена полей точно соответствуют тому, что генерирует
`xray_fluent/singbox_config_builder.py`.

---

## 1. VLESS + Reality + TUN (native, default = direct)

Типичный сценарий: VLESS с Reality TLS и flow XTLS-Vision.
TUN-адаптер перехватывает весь трафик. По умолчанию трафик идёт напрямую
(`final: "direct"`), а через прокси проходят только домены из явных правил.

Ключевые моменты:

- `interface_name` генерируется приложением случайно (`xftun` + hex-суффикс);
  здесь дан статический пример.
- `stack: "mixed"` — гибридный режим стека (system + gvisor), рекомендуется
  на Windows.
- Правило `sniff` идёт первым — оно не финальное и добавляет метаданные
  (SNI, HTTP host) для последующих правил.
- `hijack-dns` перенаправляет DNS-запросы в DNS-движок sing-box.
- Защищённые процессы (`xray.exe`, `sing-box.exe`) всегда идут напрямую,
  чтобы не попасть в петлю маршрутизации.
- `domain_resolver` на outbound `proxy` указывает серверу резолвить домены
  через `proxy-dns` (см. `dns.servers`).

```json
{
  "log": {
    "level": "warn",
    "timestamp": true
  },
  "inbounds": [
    {
      "type": "tun",
      "tag": "tun-in",
      "interface_name": "xftun0a1b2c",
      "address": ["172.19.0.1/30"],
      "auto_route": true,
      "strict_route": false,
      "stack": "mixed"
    }
  ],
  "outbounds": [
    {
      "type": "vless",
      "tag": "proxy",
      "server": "example.com",
      "server_port": 443,
      "uuid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "flow": "xtls-rprx-vision",
      "tls": {
        "enabled": true,
        "server_name": "www.microsoft.com",
        "utls": {
          "enabled": true,
          "fingerprint": "chrome"
        },
        "reality": {
          "enabled": true,
          "public_key": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
          "short_id": "0123456789abcdef"
        }
      },
      "domain_resolver": "proxy-dns"
    },
    {
      "type": "direct",
      "tag": "direct",
      "domain_resolver": "bootstrap-dns"
    },
    {
      "type": "block",
      "tag": "block"
    }
  ],
  "route": {
    "auto_detect_interface": true,
    "default_domain_resolver": "proxy-dns",
    "final": "direct",
    "rules": [
      { "action": "sniff" },
      { "protocol": "dns", "action": "hijack-dns" },
      { "process_name": ["xray.exe", "sing-box.exe"], "outbound": "direct" },
      { "domain": ["example.com"], "outbound": "direct" },
      { "ip_is_private": true, "outbound": "direct" },
      { "domain_suffix": [".youtube.com", ".google.com"], "outbound": "proxy" }
    ]
  },
  "dns": {
    "servers": [
      {
        "tag": "bootstrap-dns",
        "type": "udp",
        "server": "1.1.1.1"
      },
      {
        "tag": "proxy-dns",
        "type": "tcp",
        "server": "8.8.8.8",
        "detour": "proxy"
      }
    ],
    "final": "proxy-dns"
  },
  "experimental": {
    "clash_api": {
      "external_controller": "127.0.0.1:19090"
    }
  }
}
```

Правило `{"domain": ["example.com"], "outbound": "direct"}` предотвращает
петлю: трафик к самому прокси-серверу идёт мимо TUN. Приложение добавляет
это автоматически на основе `Node.server`.

Подробнее о TLS-полях: [tls.md](tls.md).

---

## 2. Trojan + TLS + WebSocket (native, default = proxy)

Режим полного прокси — весь трафик идёт через прокси по умолчанию
(`final: "proxy"`). Системные процессы и LAN отправляются напрямую.

Ключевые отличия от примера 1:

- `final: "proxy"` — непрошедший правила трафик идёт в прокси.
- Transport `ws` (WebSocket) с путём и заголовком `Host`.
- TLS без Reality — обычный TLS с `server_name` и `utls` fingerprint.
- Добавлены правила для системных процессов Windows, которые не должны
  ходить через прокси.

```json
{
  "log": {
    "level": "warn",
    "timestamp": true
  },
  "inbounds": [
    {
      "type": "tun",
      "tag": "tun-in",
      "interface_name": "xftund4e5f6",
      "address": ["172.19.0.1/30"],
      "auto_route": true,
      "strict_route": false,
      "stack": "mixed"
    }
  ],
  "outbounds": [
    {
      "type": "trojan",
      "tag": "proxy",
      "server": "trojan.example.com",
      "server_port": 443,
      "password": "my-trojan-password",
      "tls": {
        "enabled": true,
        "server_name": "trojan.example.com",
        "utls": {
          "enabled": true,
          "fingerprint": "chrome"
        }
      },
      "transport": {
        "type": "ws",
        "path": "/ws-path",
        "headers": {
          "Host": "trojan.example.com"
        }
      },
      "domain_resolver": "proxy-dns"
    },
    {
      "type": "direct",
      "tag": "direct",
      "domain_resolver": "bootstrap-dns"
    },
    {
      "type": "block",
      "tag": "block"
    }
  ],
  "route": {
    "auto_detect_interface": true,
    "default_domain_resolver": "proxy-dns",
    "final": "proxy",
    "rules": [
      { "action": "sniff" },
      { "protocol": "dns", "action": "hijack-dns" },
      { "process_name": ["xray.exe", "sing-box.exe"], "outbound": "direct" },
      { "domain": ["trojan.example.com"], "outbound": "direct" },
      { "ip_is_private": true, "outbound": "direct" },
      {
        "process_name": ["svchost.exe", "wuauclt.exe", "usoclient.exe"],
        "outbound": "direct"
      }
    ]
  },
  "dns": {
    "servers": [
      {
        "tag": "bootstrap-dns",
        "type": "udp",
        "server": "1.1.1.1"
      },
      {
        "tag": "proxy-dns",
        "type": "tcp",
        "server": "8.8.8.8",
        "detour": "proxy"
      }
    ],
    "final": "proxy-dns"
  },
  "experimental": {
    "clash_api": {
      "external_controller": "127.0.0.1:19090"
    }
  }
}
```

Подробнее о транспортах: [transport.md](transport.md).

---

## 3. VMess + TLS + gRPC (native, split routing)

Раздельная маршрутизация — конкретные приложения через прокси, остальной
трафик напрямую. Типичный сценарий: браузер через прокси, всё остальное
без прокси.

Ключевые моменты:

- `final: "direct"` — по умолчанию трафик идёт напрямую.
- Правила `process_name` направляют конкретные процессы в прокси.
- Правило `domain_suffix` направляет определённые домены в прокси.
- gRPC-транспорт с `service_name`.
- VMess использует поля `alter_id` и `security`, отличающие его от VLESS.

```json
{
  "log": {
    "level": "warn",
    "timestamp": true
  },
  "inbounds": [
    {
      "type": "tun",
      "tag": "tun-in",
      "interface_name": "xftun7a8b9c",
      "address": ["172.19.0.1/30"],
      "auto_route": true,
      "strict_route": false,
      "stack": "mixed"
    }
  ],
  "outbounds": [
    {
      "type": "vmess",
      "tag": "proxy",
      "server": "vmess.example.com",
      "server_port": 443,
      "uuid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "alter_id": 0,
      "security": "auto",
      "tls": {
        "enabled": true,
        "server_name": "vmess.example.com",
        "utls": {
          "enabled": true,
          "fingerprint": "chrome"
        }
      },
      "transport": {
        "type": "grpc",
        "service_name": "my-grpc-service"
      },
      "domain_resolver": "proxy-dns"
    },
    {
      "type": "direct",
      "tag": "direct",
      "domain_resolver": "bootstrap-dns"
    },
    {
      "type": "block",
      "tag": "block"
    }
  ],
  "route": {
    "auto_detect_interface": true,
    "default_domain_resolver": "proxy-dns",
    "final": "direct",
    "rules": [
      { "action": "sniff" },
      { "protocol": "dns", "action": "hijack-dns" },
      { "process_name": ["xray.exe", "sing-box.exe"], "outbound": "direct" },
      { "domain": ["vmess.example.com"], "outbound": "direct" },
      { "ip_is_private": true, "outbound": "direct" },
      {
        "process_name": ["chrome.exe", "firefox.exe", "msedge.exe"],
        "outbound": "proxy"
      },
      {
        "domain_suffix": [".google.com", ".youtube.com", ".github.com"],
        "outbound": "proxy"
      }
    ]
  },
  "dns": {
    "servers": [
      {
        "tag": "bootstrap-dns",
        "type": "udp",
        "server": "1.1.1.1"
      },
      {
        "tag": "proxy-dns",
        "type": "tcp",
        "server": "8.8.8.8",
        "detour": "proxy"
      }
    ],
    "final": "proxy-dns"
  },
  "experimental": {
    "clash_api": {
      "external_controller": "127.0.0.1:19090"
    }
  }
}
```

Подробнее об outbound-полях: [outbounds.md](outbounds.md).

---

## 4. Hybrid mode (xhttp через Xray sidecar)

Гибридный режим используется, когда нода использует транспорт `xhttp`,
который sing-box не поддерживает нативно. В этом режиме sing-box управляет
TUN и маршрутизацией, а Xray обрабатывает исходящий прокси-трафик.

Архитектура:

```
Приложение -> TUN (sing-box) -> SOCKS relay -> Xray -> xhttp -> сервер
                                                  |
                               Xray dialerProxy --+--> SS protect (sing-box) -> direct
```

Ниже показаны оба конфига, которые приложение генерирует одновременно.

### 4a. sing-box (TUN + relay)

Два inbound: TUN для перехвата трафика и Shadowsocks protect для
обратной связи от Xray (петлевая защита через `dialerProxy`).

Outbound `proxy` — это SOCKS-релей к локальному Xray на порту 11808.
Поле `inet4_bind_address: "127.0.0.1"` гарантирует, что соединение
к Xray идёт через loopback и не попадает обратно в TUN.

Правило `{"inbound": ["tun-protect"], "outbound": "direct"}` обеспечивает,
чтобы трафик от Xray через SS-protect выходил напрямую.

```json
{
  "log": {
    "level": "warn",
    "timestamp": true
  },
  "inbounds": [
    {
      "type": "tun",
      "tag": "tun-in",
      "interface_name": "xftune1f2a3",
      "address": ["172.19.0.1/30"],
      "auto_route": true,
      "strict_route": false,
      "stack": "mixed"
    },
    {
      "type": "shadowsocks",
      "tag": "tun-protect",
      "listen": "127.0.0.1",
      "listen_port": 19200,
      "method": "chacha20-ietf-poly1305",
      "password": "Abc123RandomPassword4567"
    }
  ],
  "outbounds": [
    {
      "type": "socks",
      "tag": "proxy",
      "server": "127.0.0.1",
      "server_port": 11808,
      "inet4_bind_address": "127.0.0.1"
    },
    {
      "type": "direct",
      "tag": "direct",
      "domain_resolver": "bootstrap-dns"
    },
    {
      "type": "block",
      "tag": "block"
    }
  ],
  "route": {
    "auto_detect_interface": true,
    "default_domain_resolver": "proxy-dns",
    "final": "direct",
    "rules": [
      { "action": "sniff" },
      { "protocol": "dns", "action": "hijack-dns" },
      { "process_name": ["xray.exe", "sing-box.exe"], "outbound": "direct" },
      { "inbound": ["tun-protect"], "outbound": "direct" },
      { "ip_is_private": true, "outbound": "direct" }
    ]
  },
  "dns": {
    "servers": [
      {
        "tag": "bootstrap-dns",
        "type": "udp",
        "server": "1.1.1.1"
      },
      {
        "tag": "proxy-dns",
        "type": "tcp",
        "server": "8.8.8.8",
        "detour": "proxy"
      }
    ],
    "final": "proxy-dns"
  },
  "experimental": {
    "clash_api": {
      "external_controller": "127.0.0.1:19090"
    }
  }
}
```

### 4b. Xray (SOCKS inbound + xhttp outbound)

Xray принимает трафик от sing-box через SOCKS на порту 11808 и отправляет
его к серверу через VLESS + xhttp. Исходящие соединения Xray проходят
через `dialerProxy`, который указывает на Shadowsocks protect outbound
(`tun-protect-out`), замыкая петлю обратно в sing-box.

Порт и пароль SS-protect совпадают с sing-box inbound из примера 4a.

```json
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "tag": "socks-in",
      "protocol": "socks",
      "listen": "127.0.0.1",
      "port": 11808,
      "settings": {
        "auth": "noauth",
        "udp": true
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"],
        "routeOnly": true
      }
    }
  ],
  "outbounds": [
    {
      "tag": "proxy",
      "protocol": "vless",
      "settings": {
        "vnext": [
          {
            "address": "example.com",
            "port": 443,
            "users": [
              {
                "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                "encryption": "none"
              }
            ]
          }
        ]
      },
      "streamSettings": {
        "network": "xhttp",
        "security": "tls",
        "tlsSettings": {
          "serverName": "example.com",
          "fingerprint": "chrome"
        },
        "xhttpSettings": {
          "path": "/xhttp-path"
        },
        "sockopt": {
          "dialerProxy": "tun-protect-out"
        }
      }
    },
    {
      "tag": "direct",
      "protocol": "freedom",
      "settings": {}
    },
    {
      "tag": "block",
      "protocol": "blackhole",
      "settings": {}
    },
    {
      "tag": "tun-protect-out",
      "protocol": "shadowsocks",
      "settings": {
        "servers": [
          {
            "address": "127.0.0.1",
            "port": 19200,
            "method": "chacha20-ietf-poly1305",
            "password": "Abc123RandomPassword4567"
          }
        ]
      }
    }
  ],
  "routing": {
    "rules": [
      {
        "type": "field",
        "inboundTag": ["api"],
        "outboundTag": "api"
      }
    ]
  }
}
```

При горячей замене ноды (hot-swap) sing-box не перезапускается — приложение
пересобирает и перезапускает только Xray-конфиг с теми же `protect_port`
и `protect_password`.

---

## 5. Расширенный DNS (DoH + DoT)

Продвинутая DNS-конфигурация с DNS-over-HTTPS (bootstrap) и DNS-over-TLS
(proxy). Показан также вариант с FakeIP для ускорения резолва.

DNS-серверы в sing-box 1.14 используют поле `type` для указания протокола:

- `udp` — классический DNS (по умолчанию)
- `tcp` — DNS over TCP
- `tls` — DNS-over-TLS (порт 853 по умолчанию)
- `https` — DNS-over-HTTPS

### 5a. DoH + DoT

```json
{
  "log": {
    "level": "warn",
    "timestamp": true
  },
  "inbounds": [
    {
      "type": "tun",
      "tag": "tun-in",
      "interface_name": "xftunb4c5d6",
      "address": ["172.19.0.1/30"],
      "auto_route": true,
      "strict_route": false,
      "stack": "mixed"
    }
  ],
  "outbounds": [
    {
      "type": "vless",
      "tag": "proxy",
      "server": "example.com",
      "server_port": 443,
      "uuid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "flow": "xtls-rprx-vision",
      "tls": {
        "enabled": true,
        "server_name": "www.microsoft.com",
        "utls": {
          "enabled": true,
          "fingerprint": "chrome"
        },
        "reality": {
          "enabled": true,
          "public_key": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
          "short_id": "0123456789abcdef"
        }
      },
      "domain_resolver": "proxy-dns"
    },
    {
      "type": "direct",
      "tag": "direct",
      "domain_resolver": "bootstrap-dns"
    },
    {
      "type": "block",
      "tag": "block"
    }
  ],
  "route": {
    "auto_detect_interface": true,
    "default_domain_resolver": "proxy-dns",
    "final": "direct",
    "rules": [
      { "action": "sniff" },
      { "protocol": "dns", "action": "hijack-dns" },
      { "process_name": ["xray.exe", "sing-box.exe"], "outbound": "direct" },
      { "domain": ["example.com"], "outbound": "direct" },
      { "ip_is_private": true, "outbound": "direct" }
    ]
  },
  "dns": {
    "servers": [
      {
        "tag": "bootstrap-dns",
        "type": "https",
        "server": "1.1.1.1",
        "server_port": 443,
        "path": "/dns-query"
      },
      {
        "tag": "proxy-dns",
        "type": "tls",
        "server": "8.8.8.8",
        "server_port": 853,
        "detour": "proxy"
      }
    ],
    "final": "proxy-dns"
  },
  "experimental": {
    "clash_api": {
      "external_controller": "127.0.0.1:19090"
    }
  }
}
```

### 5b. FakeIP

FakeIP ускоряет соединение: вместо реального резолва sing-box присваивает
временный IP из выделенного диапазона. Реальный DNS-резолв происходит уже
на стороне прокси-сервера.

Для FakeIP необходимо:

- Добавить DNS-сервер с `"type": "fakeip"`.
- Указать `fakeip` в `dns` с диапазонами адресов.
- В TUN-inbound добавить `"include_android_user"` не требуется (Windows).

```json
{
  "log": {
    "level": "warn",
    "timestamp": true
  },
  "inbounds": [
    {
      "type": "tun",
      "tag": "tun-in",
      "interface_name": "xftunf7a8b9",
      "address": [
        "172.19.0.1/30",
        "fdfe:dcba:9876::1/126"
      ],
      "auto_route": true,
      "strict_route": false,
      "stack": "mixed"
    }
  ],
  "outbounds": [
    {
      "type": "vless",
      "tag": "proxy",
      "server": "example.com",
      "server_port": 443,
      "uuid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "flow": "xtls-rprx-vision",
      "tls": {
        "enabled": true,
        "server_name": "www.microsoft.com",
        "utls": {
          "enabled": true,
          "fingerprint": "chrome"
        },
        "reality": {
          "enabled": true,
          "public_key": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
          "short_id": "0123456789abcdef"
        }
      },
      "domain_resolver": "proxy-dns"
    },
    {
      "type": "direct",
      "tag": "direct",
      "domain_resolver": "bootstrap-dns"
    },
    {
      "type": "block",
      "tag": "block"
    }
  ],
  "route": {
    "auto_detect_interface": true,
    "default_domain_resolver": "proxy-dns",
    "final": "direct",
    "rules": [
      { "action": "sniff" },
      { "protocol": "dns", "action": "hijack-dns" },
      { "process_name": ["xray.exe", "sing-box.exe"], "outbound": "direct" },
      { "domain": ["example.com"], "outbound": "direct" },
      { "ip_is_private": true, "outbound": "direct" }
    ]
  },
  "dns": {
    "servers": [
      {
        "tag": "bootstrap-dns",
        "type": "udp",
        "server": "1.1.1.1"
      },
      {
        "tag": "proxy-dns",
        "type": "tcp",
        "server": "8.8.8.8",
        "detour": "proxy"
      },
      {
        "tag": "fakeip-dns",
        "type": "fakeip"
      }
    ],
    "final": "proxy-dns",
    "fakeip": {
      "enabled": true,
      "inet4_range": "198.18.0.0/15",
      "inet6_range": "fc00::/18"
    }
  },
  "experimental": {
    "clash_api": {
      "external_controller": "127.0.0.1:19090"
    }
  }
}
```

При использовании FakeIP нужно учитывать, что `ip_is_private` правило
может не работать корректно для fakeip-адресов, так как реальный IP
неизвестен до момента соединения.

---

## Общие замечания

**Порядок правил маршрутизации** критически важен. Приложение генерирует
правила в следующем порядке (см. [runtime-config.md](../runtime-config.md)):

1. `sniff` (не финальное, добавляет метаданные)
2. `hijack-dns` (финальное для DNS-трафика)
3. Защищённые процессы -> `direct`
4. Bypass прокси-сервера -> `direct` (native) или protect inbound -> `direct` (hybrid)
5. LAN bypass (`ip_is_private`) -> `direct`
6. Правила процессов (preset и ручные)
7. Правила сервисов (preset-домены)
8. Правила доменов (direct, block, proxy)
9. `route.final` для оставшегося трафика

**Теги outbound** фиксированы: `proxy`, `direct`, `block`. Приложение
ожидает именно эти теги — переименование приведёт к ошибкам маршрутизации.

**Теги DNS** фиксированы: `bootstrap-dns`, `proxy-dns`. Поле
`default_domain_resolver` всегда указывает на `proxy-dns`.
