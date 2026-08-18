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

Если VM была развернута с использованием `cloud-init`:

```bash
sudo cloud-init status --wait
```

Если `cloud-init status --wait` не завершился успешно, продолжать runbook нельзя. Необходимо устранить ошибку `cloud-init` и повторно проверить его состояние.

Затем для всех вариантов развертывания:

```bash
cat /etc/os-release
uname -r
ip -brief address
ip route
systemctl --failed
```

Перед переходом к следующему этапу необходимо убедиться, что:

- ОС загрузилась корректно;
- сетевые интерфейсы находятся в ожидаемом состоянии;
- присутствуют ожидаемые маршруты;
- отсутствуют критичные failed systemd units.

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

Перед переходом к следующему этапу необходимо применить и проверить согласованный security baseline.

### SSH

Проверить эффективную конфигурацию SSH:

```bash
sudo sshd -T | grep -E '^(permitrootlogin|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication)'
```

Если используется политика из примера `cloud-init.yaml`, ожидается как минимум:

* прямой SSH-вход под `root` запрещен;
* парольная SSH-аутентификация запрещена;
* public key authentication разрешена.

Если фактическая конфигурация не соответствует согласованной SSH-policy, продолжать runbook нельзя.

### Host firewall

Если по принятой security-policy на VM должен использоваться host firewall, он должен быть включен и содержать только согласованные правила.

Ubuntu с UFW:

```bash
sudo ufw status verbose
```

RHEL-compatible system с firewalld:

```bash
sudo firewall-cmd --state
sudo firewall-cmd --list-all
```

Если инфраструктура использует другой host firewall, проверить его состояние и правила соответствующим корпоративным способом.

Если host firewall обязателен, но не настроен, продолжать runbook нельзя.

### SELinux / AppArmor

Ubuntu:

```bash
sudo systemctl is-active apparmor
sudo aa-status
```

Если AppArmor используется принятой security-policy, его обязательные профили должны быть активны.

RHEL-compatible system:

```bash
getenforce
```

Ожидаемое состояние:

```text
Enforcing
```

Если SELinux должен быть `Enforcing`, но находится в `Permissive` или `Disabled`, продолжать runbook нельзя без согласованного исключения.

### System logging

Проверить работу локального журнала:

```bash
systemctl is-active systemd-journald
journalctl -p err -b --no-pager
```

`systemd-journald` должен быть активен.

Ошибки из текущей загрузки необходимо просмотреть и убедиться, что среди них нет неисправностей, блокирующих эксплуатацию VM.

Если по требованиям используется централизованный logging или security agent, его установка и подключение должны быть завершены и проверены до финальной приемки.

### Vulnerability / security check

Если для VM обязателен vulnerability scan или другой корпоративный security check, он должен быть выполнен до перевода VM в READY.

Критические или блокирующие findings должны быть устранены либо иметь согласованное исключение.

### Exit criteria

Этап Basic security считается завершенным только если:

* SSH соответствует согласованной policy;
* обязательный host firewall настроен и проверен;
* SELinux/AppArmor находится в требуемом состоянии;
* системное логирование работает;
* обязательные security agents подключены;
* обязательный vulnerability/security check выполнен;
* отсутствуют незакрытые блокирующие security findings.

Если хотя бы одно обязательное требование не выполнено, продолжать runbook нельзя.

## 11. Additional disks

Если дополнительные диски для VM не запрошены, этот раздел пропускается.

Если дополнительные диски запрошены, для каждого диска на этапе Preparation должны быть заранее определены:

* назначение;
* размер;
* filesystem;
* mount point;
* используется ли LVM или обычный partitioning;
* mount options.

Если storage design для дополнительного диска не определен, продолжать provisioning нельзя.

### Проверка доступных устройств

Перед любыми изменениями определить системный диск и дополнительные устройства:

```bash
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS,UUID
sudo blkid
findmnt /
```

Не выполнять partitioning, `pvcreate`, `mkfs` или другие разрушающие операции, пока не подтверждено, какое устройство является дополнительным диском.

**Системный диск форматировать запрещено.**

### Настройка дополнительных дисков

Для каждого дополнительного диска выполнить partitioning/LVM и создание filesystem в соответствии с согласованным storage design.

После создания filesystem определить его UUID:

```bash
sudo blkid
```

Создать требуемый mount point, например:

```bash
sudo mkdir -p /data
```

Постоянное монтирование добавить в `/etc/fstab`.

Перед изменением сохранить резервную копию:

```bash
sudo cp -a /etc/fstab /etc/fstab.bak
```

Для постоянного mount использовать `UUID`, а не имя устройства `/dev/sdX`, если инфраструктура не требует другого механизма.

Пример записи:

```text
UUID=<filesystem-uuid> /data <filesystem> <mount-options> 0 <fsck-pass>
```

Значения `<filesystem-uuid>`, `/data`, `<filesystem>`, `<mount-options>` и `<fsck-pass>` должны соответствовать согласованному storage design и используемому filesystem.

### Проверка

После изменения `/etc/fstab` выполнить:

```bash
sudo findmnt --verify
sudo mount -a
lsblk -f
findmnt
df -hT
```

После успешного монтирования настроить владельца и permissions корня смонтированного filesystem в соответствии с согласованным storage design.

Например:

```bash
sudo chown <owner>:<group> /data
sudo chmod <mode> /data
```

`findmnt --verify` и `mount -a` должны завершиться без ошибок.

Проверить, что каждый обязательный filesystem:

* смонтирован в правильный mount point;
* имеет ожидаемый filesystem type;
* имеет ожидаемые mount options;
* имеет правильного владельца и permissions.

После этого выполнить перезагрузку:

```bash
sudo reboot
```

После загрузки повторно проверить:

```bash
lsblk -f
findmnt
df -hT
sudo findmnt --verify
```

Все обязательные filesystem должны автоматически смонтироваться после перезагрузки.

Если запрошенный дополнительный диск не настроен, отсутствует в `/etc/fstab`, не монтируется автоматически или `findmnt --verify` сообщает ошибку, продолжать runbook нельзя.

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

После успешного ввода в домен вернуться к этому документу и продолжить с раздела Bootstrap account cleanup.

Если доменная интеграция не требуется, перейти сразу к следующему разделу.

Да, мой косяк. Вот **нормальный блок для редактирования с Markdown-оформлением**, чтобы ты целиком заменил текущий раздел `12.1`.

## 12.1 Bootstrap account cleanup

`bootstrap-admin` является временной учетной записью и не должен оставаться на готовой VM.

До удаления `bootstrap-admin` должен существовать и быть проверен постоянный административный способ доступа.

Если VM введена в Active Directory, таким доступом может быть проверенная доменная учетная запись из разрешенной административной группы.

Если Active Directory не используется и другого постоянного административного доступа еще нет, создать отдельную локальную административную учетную запись.

В примерах ниже используется имя `linux-admin`. В реальной инфраструктуре необходимо использовать согласованное имя учетной записи.

### Создание локальной административной учетной записи

```bash
sudo useradd -m -s /bin/bash linux-admin
sudo install -d -m 700 -o linux-admin -g linux-admin /home/linux-admin/.ssh
```

Добавить согласованный публичный SSH-ключ администратора:

```bash
sudo touch /home/linux-admin/.ssh/authorized_keys
sudoedit /home/linux-admin/.ssh/authorized_keys
```

После этого установить владельца и права:

```bash
sudo chown linux-admin:linux-admin /home/linux-admin/.ssh/authorized_keys
sudo chmod 600 /home/linux-admin/.ssh/authorized_keys
```

На RHEL-compatible системе с SELinux дополнительно выполнить:

```bash
sudo restorecon -RFv /home/linux-admin/.ssh
```

Предоставить административные права.

Ubuntu:

```bash
sudo usermod -aG sudo linux-admin
```

RHEL-compatible system:

```bash
sudo usermod -aG wheel linux-admin
```

Если действующая sudo-policy требует пароль пользователя, установить его интерактивно:

```bash
sudo passwd linux-admin
```

Наличие локального пароля для `sudo` не требует включения парольной SSH-аутентификации. `PasswordAuthentication` в SSH специально для этой учетной записи включать не нужно.

### Проверка постоянного административного доступа

До удаления `bootstrap-admin` открыть **новую отдельную SSH-сессию** постоянной административной учетной записью.

В новой сессии выполнить:

```bash
id
sudo -v
sudo id
sudo -l
```

Команды должны выполняться успешно в соответствии с назначенными правами.

Если используется Active Directory, дополнительно убедиться, что административная доменная учетная запись определяется системой:

```bash
id 'user@corp.example.com'
```

Реальный SSH-вход этой доменной учетной записью должен быть успешно проверен на этапе Domain integration.

Если постоянный административный доступ не работает, удалять `bootstrap-admin` нельзя.

Сессию `bootstrap-admin` можно закрывать только после успешной проверки новой административной сессии.

### Удаление bootstrap-доступа

Из проверенной постоянной административной сессии найти sudo-правила, связанные с `bootstrap-admin`:

```bash
sudo grep -Rns 'bootstrap-admin' /etc/sudoers /etc/sudoers.d 2>/dev/null
```

Удалить только правила, относящиеся к `bootstrap-admin`.

Файлы sudoers необходимо изменять через `visudo`, например:

```bash
sudo visudo
```

или для отдельного файла:

```bash
sudo visudo -f /etc/sudoers.d/<имя-файла>
```

После изменения проверить всю конфигурацию sudo:

```bash
sudo visudo -c
```

Если `visudo -c` сообщает ошибку, продолжать нельзя.

После успешной проверки закрыть все оставшиеся SSH-сессии `bootstrap-admin`.

Проверить, что от его имени не осталось процессов:

```bash
pgrep -a -u bootstrap-admin
```

Если процессы остались, завершить пользовательскую сессию:

```bash
sudo loginctl terminate-user bootstrap-admin
```

Повторная команда:

```bash
pgrep -a -u bootstrap-admin
```

не должна возвращать процессов.

После этого удалить временную учетную запись:

```bash
sudo userdel -r bootstrap-admin
```

### Финальная проверка

Проверить отсутствие учетной записи:

```bash
id bootstrap-admin
```

Ожидаемый результат — пользователь не существует.

Проверить отсутствие sudo-правил:

```bash
sudo grep -Rns 'bootstrap-admin' /etc/sudoers /etc/sudoers.d 2>/dev/null
```

Команда не должна находить правил для `bootstrap-admin`.

Проверить sudoers:

```bash
sudo visudo -c
```

После удаления `bootstrap-admin` открыть еще одну новую SSH-сессию постоянной административной учетной записью и выполнить:

```bash
sudo -v
sudo id
```

Если постоянный административный доступ после удаления `bootstrap-admin` не работает, VM не считается готовой.

Если учетная запись `bootstrap-admin` или ее sudo-права остались на системе, VM не считается готовой.

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

Для финальной приемки допустим только exit code `0`.

- `0` - все автоматизированные проверки успешно пройдены;
- `1` - обнаружена ошибка;
- `2` - состояние VM не удалось полностью подтвердить, присутствуют предупреждения.

При exit code `1` или `2` продолжать приемку и переводить VM в готовое состояние нельзя.

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
