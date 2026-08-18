# Ввод Linux VM в домен

Подключить Linux-сервер к AD и разрешить доступ только согласованным пользователям или группам.

Этап выполняется, когда:

- пользователи входят с доменными учетными записями;
- административные группы управляются в AD;
- сервису требуется Kerberos;
- сервер используется как Samba member server.

Если доменная интеграция не нужна, этап пропускается.

## SSSD and Winbind

### SSSD

Рекомендуется для обычной аутентификации Linux-пользователей через AD.

### Winbind

Используется, когда сервер предоставляет Samba-сервисы или этого требует существующая архитектура.

SSSD и Winbind нельзя смешивать без отдельного технического решения.

## Prerequisites

Проверить:

- hostname;
- FQDN;
- прямой DNS;
- обратный DNS;
- SRV-записи AD;
- синхронизацию времени;
- сетевые порты;
- OU;
- делегированные права;
- аварийную локальную учетную запись.

```bash
hostname --fqdn
timedatectl
resolvectl status 2>/dev/null || cat /etc/resolv.conf
getent hosts linux-vm-01.corp.example.com
getent hosts 192.0.2.20
````

Перед продолжением необходимо убедиться, что:

* FQDN соответствует подготовленным данным;
* прямое DNS-разрешение работает;
* обратное DNS-разрешение работает;
* системное время синхронизировано;
* VM использует ожидаемые DNS-серверы.

`realm discover` на этом этапе не выполняется. Сначала должны быть установлены пакеты `realmd`, `sssd` и остальные зависимости для соответствующего дистрибутива.

## Preparing an object in AD

Объект компьютера может создаваться заранее, если:

* права join делегированы только на конкретную OU;
* naming policy требует предварительного контроля;
* внутренний процесс требует CMDB/AD-согласования.

Это не универсальное обязательное требование.

## Ubuntu: realmd + SSSD

Установить необходимые пакеты:

```bash
sudo apt update
sudo apt install sssd-ad sssd-tools realmd adcli
```

После установки пакетов проверить обнаружение домена:

```bash
sudo realm -v discover corp.example.com
```

Если домен не обнаруживается, продолжать присоединение нельзя. Необходимо устранить проблемы DNS, времени, сетевой доступности или конфигурации AD.

Присоединение:

```bash
sudo realm join corp.example.com -U ad-join-user
```

Если computer account должен быть создан в определенной OU:

```bash
sudo realm join corp.example.com \
  --computer-ou="OU=Linux,OU=Servers,DC=corp,DC=example,DC=com" \
  -U ad-join-user
```

Пароль должен вводиться интерактивно. Его нельзя передавать в Git, shell script, inventory или CI-логи.

Проверка:

```bash
realm list
getent passwd 'user@corp.example.com'
id 'user@corp.example.com'
sssctl domain-status corp.example.com
```

## RHEL-compatible system: realmd + SSSD

Установить необходимые пакеты:

```bash
sudo dnf install samba-common-tools realmd oddjob oddjob-mkhomedir sssd sssd-tools adcli krb5-workstation
```

После установки пакетов проверить обнаружение домена:

```bash
sudo realm -v discover corp.example.com
```

Если домен не обнаруживается, продолжать присоединение нельзя.

Присоединение:

```bash
sudo realm join corp.example.com -U ad-join-user
```

Проверка:

```bash
realm list
id 'user@corp.example.com'
sssctl domain-status corp.example.com
```

Для новых систем не использовать старый `authconfig`.

## Access restriction

Не следует автоматически разрешать вход всем пользователям домена.

Пример:

```bash
sudo realm deny --all
sudo realm permit -g 'linux-admins@corp.example.com'
```

Перед применением:

- проверить точное имя группы;
- сохранить активную локальную root/sudo-сессию;
- проверить аварийный доступ;
- протестировать вход отдельным пользователем.

## Home directories

Для Ubuntu при использовании SSSD автоматическое создание home directory можно включить через PAM:

```bash
sudo pam-auth-update --enable mkhomedir
```

После изменения проверить вход тестовой доменной учетной записью и убедиться, что home directory создается только при первом успешном входе.

Если автоматическое создание home directory не требуется политикой организации, этот шаг пропускается.

## Winbind option

Winbind используется только в тех случаях, когда этого требует архитектура сервера, например для Samba member server.

Настройка Winbind зависит от дистрибутива, версии ОС и выбранного механизма ID mapping. Поэтому универсальная конфигурация Winbind в рамках этого runbook не применяется.

Перед использованием Winbind необходимо отдельно определить:

- необходимые Samba и Winbind packages;
- NSS и PAM integration;
- ID mapping backend и диапазоны UID/GID;
- правила создания home directories;
- требования к Samba services;
- формат доменных имен пользователей и групп.

SSSD и Winbind не должны одновременно использоваться как основной механизм доменной идентификации без отдельного архитектурного решения.

Для обычной аутентификации Linux-пользователей через Active Directory в этом runbook используется SSSD.

## Login verification

Сначала проверить, что тестовая доменная учетная запись корректно определяется через SSSD:

```bash
id 'user@corp.example.com'
getent passwd 'user@corp.example.com'
```

Обе команды должны успешно вернуть данные доменного пользователя.

Затем необходимо выполнить реальный SSH-вход тестовой доменной учетной записью с использованием способа SSH-аутентификации, согласованного на этапе Preparation.

Сам по себе `realm join` настраивает доменную интеграцию, но не предоставляет доменному пользователю SSH-ключ и не определяет способ его SSH-аутентификации.

Если используется SSH public key, ключ тестового пользователя должен быть доставлен на сервер согласованным корпоративным механизмом до выполнения SSH-теста.

Если используется GSSAPI/Kerberos или другой корпоративный механизм, он должен быть отдельно настроен и проверен до завершения этого этапа.

Не включать `PasswordAuthentication yes` только ради прохождения проверки, если парольная SSH-аутентификация запрещена принятой политикой.

Проверить эффективную конфигурацию SSH:

```bash
sudo sshd -T | grep -E '^(pubkeyauthentication|passwordauthentication|kbdinteractiveauthentication|gssapiauthentication)'
```

После этого с отдельной клиентской машины выполнить реальный SSH-вход:

```bash
ssh -l 'user@corp.example.com' linux-vm-01.corp.example.com
```

После успешного входа проверить:

```bash
id
groups
pwd
```

Если пользователь входит в административную группу, дополнительно проверить:

```bash
sudo -l
```

Успешный `realm join` еще не гарантирует:

- разрешение доменного пользователя;
- корректный SSH-вход;
- создание home directory;
- правильную обработку доменных групп;
- корректную работу `sudo`.

Если реальный SSH-вход согласованной доменной учетной записью не работает, этап Domain integration не считается завершенным.

## Rollback

При неудачном вводе в домен сначала удалить локальную конфигурацию членства:

```bash
sudo realm leave corp.example.com
```
Если необходимо также удалить computer account из AD и у УЗ есть соответствующие права:
```bash
sudo realm leave --remove corp.example.com -U ad-join-user
```

Затем:

- проверить локальный вход;
- удалить или отключить ошибочный объект компьютера;
- удалить временные правила доступа;
- восстановить предыдущие конфигурации;
- проверить DNS;
- проверить PAM/NSS/SSSD;
- убедиться, что локальный sudo работает.

## Troubleshooting

### Домен не обнаруживается

```bash
resolvectl status 2>/dev/null || true
realm discover corp.example.com
```

Чаще всего причина - неправильный DNS.

### Ошибка Kerberos

```bash
timedatectl
chronyc tracking 2>/dev/null || true
```

Частая причина - рассинхронизация времени.

### Пользователь находится, но не входит

```bash
realm list
id 'user@corp.example.com'
journalctl -u sssd --since -30min
journalctl -u sshd --since -30min
```

Также проверить access policy и SSH-конфигурацию.

## Stage result

Ввод в домен завершен, когда:

- сервер присутствует в нужном домене;
- объект находится в правильной OU;
- DNS и время корректны;
- доменная учетная запись определяется;
- SSH-вход проверен;
- разрешены только согласованные группы;
- sudo проверен;
- локальный аварийный доступ сохранен;
- monitoring не показывает ошибок SSSD или Winbind.
