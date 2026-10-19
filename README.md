# VpnChecker

## EN

**Automated OpenVPN server checker powered by GitHub Actions.**

VpnChecker periodically tests OpenVPN server configurations, identifies working connections, reports check results to the API, and publishes the list of working servers to the `main` branch.

## Features

- **Automated checks** — runs every 6 hours using GitHub Actions.
- **Manual execution** — start a check workflow whenever needed.
- **OpenVPN connection testing** — verifies whether a VPN connection can be established.
- **API integration** — reports successful and failed checks using an API key.
- **Automatic publishing** — updates `servers.json` in the `main` branch with working servers.
- **Configuration validation** — rejects configurations containing certain potentially unsafe directives.
- **Failure protection** — preserves the previous output if no working servers are found.
- **Authentication support** — supports OpenVPN configurations requiring a username and password.

## How It Works

1. Add or update server entries in `servers.json` on the `dev` branch.
2. GitHub Actions starts the checker when the source files change, on a scheduled run, or through manual execution.
3. VpnChecker downloads each server's OpenVPN configuration and validates it.
4. OpenVPN attempts to establish a connection, subject to the configured timeout.
5. The result of each attempted check is reported to the API.
6. Working servers are written to `servers.json` in the output workspace.
7. GitHub Actions automatically commits and pushes the updated file to the `main` branch.

## Repository Structure

```text
VpnChecker/
├── .github/
│   └── workflows/
│       └── check-vpn.yml
├── servers.json
└── vpn_checker.py
```

- `servers.json` — source list of servers to check.
- `vpn_checker.py` — downloads configurations, tests connections, and reports results.
- `check-vpn.yml` — automates checks and publishes the results.

## Server List Format

The input `servers.json` file contains a `type` field and a `servers` array.

```json
{
  "type": "openvpn",
  "servers": [
    {
      "id": 123,
      "country": "Japan",
      "vpnConfigUrl": "https://example.com/server.ovpn",
      "userName": "",
      "userPassword": ""
    }
  ]
}
```

Each server entry can include:

| Field | Description |
|---|---|
| `id` | Server identifier used for API reporting |
| `country` | Server location or display name |
| `vpnConfigUrl` | URL of the OpenVPN configuration |
| `userName` | Optional VPN username |
| `userPassword` | Optional VPN password |

The root-level `type` value is included in API result reports and preserved in the generated output.

## Configuration

### GitHub Actions Secret

Add the following repository secret under **Settings → Secrets and variables → Actions**:

| Secret | Description |
|---|---|
| `API_KEY` | API key used to authorize requests to the VpnChecker backend |

The workflow passes this secret to the Python checker through the `API_KEY` environment variable.

**Never commit API keys or passwords directly to the repository.**

### Automated Schedule

The workflow uses the following cron expression:

```yaml
schedule:
  - cron: "0 */6 * * *"
```

This schedules checks every six hours at 00:00, 06:00, 12:00, and 18:00 UTC. GitHub Actions may delay scheduled runs.

## Requirements

The GitHub Actions runner installs the required dependencies automatically:

- Python 3
- `requests`
- OpenVPN

The workflow uses `ubuntu-latest` as its execution environment.

## Output

The `main` branch contains the generated `servers.json` file with servers that successfully established an OpenVPN connection during the latest successful check.

If no working servers are found, the checker preserves the previous output instead of replacing it with an empty list.

A successful connection does not necessarily guarantee that internet access through the VPN is available.

## Security Notes

- OpenVPN configurations are obtained from external sources and must be treated as untrusted input.
- The checker rejects certain directives that may execute commands or load additional configuration files.
- The GitHub Actions workflow runs the checker with elevated privileges to permit OpenVPN to create a TUN/TAP interface. Review and isolate untrusted configurations carefully.
- Keep API credentials and VPN passwords out of logs and source control.

## License

See the repository for license information.

-------

## RU

# VpnChecker

**Автоматическая проверка OpenVPN-серверов с помощью GitHub Actions.**

VpnChecker периодически проверяет конфигурации OpenVPN-серверов, определяет доступность VPN-подключений, отправляет результаты проверок в API и публикует список работающих серверов в ветке `main`.

## Возможности

- **Автоматические проверки** — запуск каждые 6 часов с помощью GitHub Actions.
- **Ручной запуск** — возможность запустить проверку в любое время.
- **Проверка OpenVPN-подключений** — определение возможности установить VPN-соединение.
- **Интеграция с API** — отправка результатов успешных и неудачных проверок с использованием API-ключа.
- **Автоматическая публикация** — обновление `servers.json` в ветке `main` списком работающих серверов.
- **Проверка безопасности конфигураций** — отклонение конфигураций с некоторыми потенциально опасными директивами.
- **Защита от потери данных** — сохранение предыдущего списка, если не найдено ни одного работающего сервера.
- **Поддержка авторизации** — возможность проверки VPN-серверов, требующих имя пользователя и пароль.

## Как это работает

1. Добавьте или измените записи серверов в файле `servers.json` в ветке `dev`.
2. GitHub Actions запускает проверку при изменении исходных файлов, по расписанию или вручную.
3. VpnChecker скачивает конфигурацию каждого сервера и проверяет её.
4. OpenVPN пытается установить соединение в пределах заданного времени ожидания.
5. Результат каждой выполненной проверки отправляется в API.
6. Рабочие серверы записываются в `servers.json` в рабочей директории публикации.
7. GitHub Actions автоматически создаёт коммит и отправляет обновлённый файл в ветку `main`.

## Структура репозитория

```text
VpnChecker/
├── .github/
│   └── workflows/
│       └── check-vpn.yml
├── servers.json
└── vpn_checker.py
```

- `servers.json` — исходный список серверов для проверки.
- `vpn_checker.py` — загрузка конфигураций, проверка подключений и отправка результатов в API.
- `check-vpn.yml` — автоматизация проверок и публикации результатов.

## Формат списка серверов

Исходный файл `servers.json` содержит поле `type` и массив `servers`.

```json
{
  "type": "openvpn",
  "servers": [
    {
      "id": 123,
      "country": "Japan",
      "vpnConfigUrl": "https://example.com/server.ovpn",
      "userName": "",
      "userPassword": ""
    }
  ]
}
```

Описание полей:

| Поле | Назначение |
|---|---|
| `id` | Идентификатор сервера, используемый при отправке результатов в API |
| `country` | Страна расположения сервера или его отображаемое название |
| `vpnConfigUrl` | URL-адрес конфигурации OpenVPN |
| `userName` | Имя пользователя для авторизации, если требуется |
| `userPassword` | Пароль для авторизации, если требуется |

Значение `type` в корне JSON передаётся в API вместе с результатом проверки и сохраняется в выходном файле.

## Настройка

### Секрет GitHub Actions

Добавьте следующий секрет в настройках репозитория:

**Settings → Secrets and variables → Actions**

| Секрет | Назначение |
|---|---|
| `API_KEY` | API-ключ для авторизации запросов к серверной части VpnChecker |

Workflow передаёт этот секрет Python-скрипту через переменную окружения `API_KEY`.

**Не храните API-ключи и пароли непосредственно в исходном коде репозитория.**

### Расписание проверок

В workflow используется следующее cron-выражение:

```yaml
schedule:
  - cron: "0 */6 * * *"
```

Проверки планируются каждые 6 часов: в 00:00, 06:00, 12:00 и 18:00 UTC.

GitHub Actions может запускать запланированные задания с задержкой.

## Требования

GitHub Actions автоматически устанавливает необходимые зависимости:

- Python 3
- `requests`
- OpenVPN

Для выполнения проверок используется окружение `ubuntu-latest`.

## Результат работы

Ветка `main` содержит сгенерированный файл `servers.json` со списком серверов, для которых удалось установить OpenVPN-соединение во время последней успешной проверки.

Если ни один сервер не работает, скрипт сохраняет предыдущий результат вместо перезаписи файла пустым списком.

Обратите внимание: успешное установление VPN-соединения не гарантирует доступность интернета через VPN-туннель.

## Безопасность

- Конфигурации OpenVPN загружаются из внешних источников и должны считаться потенциально недоверенными.
- Скрипт отклоняет некоторые директивы, которые могут запускать команды или подключать дополнительные конфигурационные файлы.
- Для создания сетевого интерфейса TUN/TAP проверка запускается с повышенными привилегиями. Поэтому важно тщательно проверять и изолировать обработку недоверенных конфигураций.
- Не допускайте попадания API-ключей и паролей VPN в логи и исходный код.

## Лицензия

Информация о лицензии будет доступна в соответствующем файле репозитория.

