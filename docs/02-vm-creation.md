# Создание Linux VM

Создать виртуальную машину, развернуть Linux и выполнить базовую настройку.

## 1. Creating VM

Предпочтительный вариант - развертывание из поддерживаемого шаблона.

Шаблон должен:

- содержать поддерживаемую версию ОС;
- быть обновленным;
- содержать guest tools;
- поддерживать `cloud-init` или guest customization;
- не содержать уникальные SSH host keys;
- не содержать клонированный `machine-id`;
- не содержать пароли и внутренние секреты;
- иметь известную дату и версию сборки.

Установка с ISO допустима, когда пригодного шаблона нет.

## 2. Virtual machine parameters

При создании указываются:

- имя VM;
- папка или проект;
- кластер или resource pool;
- datastore;
- guest OS type;
- CPU и RAM;
- системный и дополнительные диски;
- сетевые интерфейсы;
- port groups;
- теги среды, владельца и сервиса.

После создания нужно проверить доступ Linux Operations к консоли VM.

## 3. Initial configuration with cloud-init

Для первоначальной конфигурации Ubuntu VM может использоваться `cloud-init`.

Конфигурация должна быть подготовлена и передана виртуальной машине **до первого запуска**, поскольку `cloud-init` выполняет основные действия во время первоначальной загрузки системы.

 [`../examples/cloud-init.yaml`](../examples/cloud-init.yaml)

### Обязательное условие для cloud-init

Пример `cloud-init.yaml` из этого репозитория можно использовать только если рабочая сеть передается VM **до первого запуска** через:

- cloud-init network-data;
- guest customization гипервизора;
- другой заранее согласованный механизм.

До первого запуска должны быть известны и переданы:

- IP/prefix;
- gateway;
- DNS;
- search domain;
- необходимые static routes.

Если сеть будет настраиваться вручную только после первого запуска, пример `cloud-init.yaml` использовать без изменений нельзя, поскольку установка пакетов требует доступа к репозиториям.

В таком случае сначала загрузить VM через консоль гипервизора, настроить сеть в разделе Networking, проверить DNS и доступ к репозиториям и только после этого устанавливать пакеты и выполнять остальные действия первоначальной настройки.

При использовании примера `cloud-init.yaml` он выполняет следующие действия:

- настройку hostname и FQDN;
- создание временной bootstrap-учетной записи;
- настройку SSH-доступа по публичному ключу;
- отключение парольной SSH-аутентификации;
- запрет прямого входа под `root`;
- установку базовых пакетов;
- запуск `chrony` и SSH;
- создание информационного system banner.

> Перед использованием необходимо заменить тестовый SSH-ключ и адаптировать параметры под целевую инфраструктуру. Пароли, токены и приватные ключи не должны храниться в `cloud-init.yaml`.

Если `cloud-init` не используется, соответствующие параметры настраиваются вручную на следующих этапах.

## 4. First launch

```bash
sudo cloud-init status --wait
cat /etc/os-release
uname -r
systemctl --failed
```

## 5. Hostname

Если hostname не был задан через `cloud-init` или guest customization, настроить его вручную:

```bash
sudo hostnamectl set-hostname linux-vm-01.corp.example.com
```

Проверить результат:

```bash
hostnamectl
hostname --fqdn
```

Если hostname уже был задан через `cloud-init`, на этом этапе достаточно выполнить проверку.

Имя должно быть согласовано между VM, Linux, DNS, CMDB, monitoring и backup.

`/etc/hosts` не должен использоваться как замена корректному DNS.

## 6. Networking for Ubuntu

Сначала определить имя интерфейса:

```bash
ip -brief link
ip -brief address
```

Пример статической конфигурации:

```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    ens160:
      dhcp4: false
      addresses:
        - 192.0.2.20/24
      nameservers:
        search:
          - corp.example.com
        addresses:
          - 192.0.2.53
          - 192.0.2.54
      routes:
        - to: default
          via: 192.0.2.1
```

Перед применением:

```bash
sudo netplan generate
sudo netplan try
sudo netplan apply
netplan status --all
```

Готовые примеры:

- [`../examples/netplan-single-nic.yaml`](../examples/netplan-single-nic.yaml)
- [`../examples/netplan-dual-nic.yaml`](../examples/netplan-dual-nic.yaml)

При удаленном изменении сети должен быть доступ к web-консоли гипервизора.

## 7. Networking for RHEL-compatible OS

Для современных RHEL-подобных систем использовать NetworkManager:

```bash
nmcli device status
nmcli connection show
```

Пример:
- [`../examples/rhel-network-nmcli.sh`](../examples/rhel-network-nmcli.sh)

Пример запуска:
```bash
sudo bash ../examples/rhel-network-nmcli.sh
```

Перед запуском заменить тестовые параметры.

Legacy-файлы `ifcfg-*` и каталог `network-scripts` не должны быть основным способом настройки новых систем.

## 8. Time and DNS

```bash
timedatectl
chronyc tracking 2>/dev/null || true
getent hosts linux-vm-01.corp.example.com
```

Корректные DNS и время обязательны для Kerberos и доменной аутентификации.

## 9. Updates

Ubuntu:

```bash
sudo apt update
sudo apt upgrade
```

RHEL-совместимая система:

```bash
sudo dnf upgrade --refresh
```

Нельзя всегда выбирать один и тот же ответ в диалогах обновления конфигурационных файлов. Требуется сравнить текущую и новую версию.

Перезагрузка выполняется только при необходимости:

```bash
sudo systemctl reboot
```

## 10. Basic security

Минимальный набор:

- отключить прямой SSH-вход под `root`;
- использовать персональные учетные записи;
- использовать SSH-ключи;
- ограничить sudo;
- включить firewall;
- проверить SELinux или AppArmor;
- настроить журналирование;
- установить security-agent;
- проверить критические уязвимости;
- удалить временные учетные записи и файлы.

Пример sudoers:

```sudoers
%linux-admins ALL=(ALL:ALL) ALL
```

Проверка:

```bash
sudo visudo -f /etc/sudoers.d/linux-admins
sudo visudo -c
```

## 11. Additional disks

Для каждого диска определить:

- назначение;
- filesystem;
- mount point;
- owner и permissions;
- параметры mount;
- необходимость LVM;
- необходимость backup;
- требования к расширению.

Перед форматированием:

```bash
lsblk
blkid
```
## 12. Domain integration

Если сервер должен использовать доменную аутентификацию, выполнить отдельный этап ввода в Active Directory перед подключением monitoring, backup и финальными приемочными проверками.

Перед переходом необходимо убедиться, что:

- hostname и FQDN настроены корректно;
- прямой и обратный DNS работают;
- время синхронизировано;
- локальный административный доступ сохранен;
- известны домен, OU и разрешенные группы;
- есть учетная запись с необходимыми правами для domain join.

Перейти к инструкции:

[Ввод Linux VM в домен →](03-domain-join.md)

После успешного ввода в домен вернуться к этому документу и продолжить с раздела Monitoring и backup.

Если доменная интеграция не требуется, перейти сразу к следующему разделу.

## 13. Monitoring и backup

После установки monitoring-agent проверить:

```bash
systemctl status monitoring-agent
systemctl is-enabled monitoring-agent
```

Также проверить поступление метрик и тестового alert.

После подключения backup выполнить тестовый job и убедиться, что retention и перечень данных соответствуют требованиям.

Snapshot VM не является полноценным backup.

## 14. Acceptance checks

```bash
hostnamectl
ip -brief address
ip route
getent hosts linux-vm-01.corp.example.com
getent hosts 192.0.2.20
timedatectl
systemctl --failed
journalctl -p err -b --no-pager
```

### Automated validation

Для повторяемой проверки состояния VM можно использовать read-only скрипт:

[`../scripts/validate_vm.py`](../scripts/validate_vm.py)

Из корня репозитория:

```bash
sudo python3 scripts/validate_vm.py \
  --expected-fqdn linux-vm-01.corp.example.com \
  --expected-ip 192.0.2.20
```

Если сервер должен быть присоединен к Active Directory:

```bash
sudo python3 scripts/validate_vm.py \
  --expected-fqdn linux-vm-01.corp.example.com \
  --expected-ip 192.0.2.20 \
  --domain corp.example.com
```

Скрипт не изменяет конфигурацию системы и используется только для проверки состояния.

Проверить:

- правильный hostname;
- ожидаемые IP;
- отсутствие лишних default routes;
- прямой и обратный DNS;
- доступность репозиториев;
- синхронизацию времени;
- отсутствие failed services;
- отсутствие критических ошибок.

## 15. Stage result

VM готова, когда:

- ОС загружается;
- сеть работает;
- DNS работает;
- hostname корректный;
- время синхронизировано;
- обновления установлены;
- базовая безопасность применена;
- monitoring и backup подключены или запланированы;
- доступ Linux Operations подтвержден.
