#!/usr/bin/env python3
"""Read-only validation checks for a provisioned Linux VM."""

import argparse
import ipaddress
import shutil
import socket
import subprocess
import sys

RESULTS = []


def result(level, check, details=""):
    RESULTS.append((level, check, details))


def run(cmd):
    try:
        process = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )
        return (
            process.returncode,
            process.stdout.strip(),
            process.stderr.strip(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 255, "", str(exc)


def exists(command):
    return shutil.which(command) is not None


def get_fqdn():
    rc, out, _ = run(["hostname", "--fqdn"])

    if rc == 0 and out:
        return out.splitlines()[0]

    return socket.getfqdn()


def get_ipv4_addresses():
    if not exists("ip"):
        return []

    rc, out, _ = run(
        ["ip", "-o", "-4", "addr", "show", "scope", "global"]
    )

    if rc != 0:
        return []

    addresses = []

    for line in out.splitlines():
        parts = line.split()

        if "inet" not in parts:
            continue

        cidr = parts[parts.index("inet") + 1]

        try:
            addresses.append(
                str(ipaddress.ip_interface(cidr).ip)
            )
        except ValueError:
            pass

    return addresses


def check_hostname(expected):
    current_fqdn = get_fqdn()

    if expected and current_fqdn.lower() != expected.lower():
        result(
            "FAIL",
            "Hostname/FQDN",
            f"got {current_fqdn}, expected {expected}",
        )

    elif (
        "." not in current_fqdn
        or current_fqdn in {"localhost", "localhost.localdomain"}
    ):
        result(
            "WARN",
            "Hostname/FQDN",
            f"{current_fqdn} does not look like an FQDN",
        )

    else:
        result(
            "PASS",
            "Hostname/FQDN",
            current_fqdn,
        )

    return current_fqdn


def check_ipv4(expected):
    addresses = get_ipv4_addresses()

    if not addresses:
        result(
            "FAIL",
            "IPv4 address",
            "no global IPv4 address found",
        )
        return None

    if expected and expected not in addresses:
        result(
            "FAIL",
            "IPv4 address",
            f"found {', '.join(addresses)}, expected {expected}",
        )

    else:
        result(
            "PASS",
            "IPv4 address",
            expected or ", ".join(addresses),
        )

    return expected or addresses[0]


def check_routes():
    if not exists("ip"):
        result(
            "WARN",
            "Default route",
            "'ip' command is not available",
        )
        return

    rc, out, err = run(
        ["ip", "-4", "route", "show", "default"]
    )

    if rc != 0:
        result(
            "FAIL",
            "Default route",
            err or "unable to read routing table",
        )
        return

    routes = [
        line
        for line in out.splitlines()
        if line.strip()
    ]

    if len(routes) == 1:
        result(
            "PASS",
            "Default route",
            routes[0],
        )

    elif len(routes) == 0:
        result(
            "WARN",
            "Default route",
            "no IPv4 default route found",
        )

    else:
        result(
            "FAIL",
            "Default route",
            f"{len(routes)} IPv4 default routes found",
        )


def check_resolution(hostname, address):
    if not exists("getent"):
        result(
            "WARN",
            "Name resolution",
            "'getent' command is not available",
        )
        return

    rc, out, _ = run(
        ["getent", "hosts", hostname]
    )

    if rc != 0 or not out:
        result(
            "FAIL",
            "Forward name resolution",
            f"{hostname} was not resolved",
        )

    elif address:
        resolved_ips = []

        for line in out.splitlines():
            for token in line.split():
                try:
                    ipaddress.ip_address(token)
                    resolved_ips.append(token)
                    break
                except ValueError:
                    continue

        if address in resolved_ips:
            result(
                "PASS",
                "Forward name resolution",
                f"{hostname} -> {address}",
            )
        else:
            result(
                "FAIL",
                "Forward name resolution",
                (
                    f"{hostname} resolved to "
                    f"{', '.join(resolved_ips) or 'unknown'}, "
                    f"expected {address}"
                ),
            )

    else:
        result(
            "PASS",
            "Forward name resolution",
            hostname,
        )

    if address:
        rc, out, _ = run(
            ["getent", "hosts", address]
        )

        expected_name = hostname.rstrip(".").lower()
        resolved_names = []

        if rc == 0 and out:
            for line in out.splitlines():
                parts = line.split()

                if len(parts) > 1:
                    resolved_names.extend(
                        name.rstrip(".").lower()
                        for name in parts[1:]
                    )

        if expected_name in resolved_names:
            result(
                "PASS",
                "Reverse name resolution",
                f"{address} -> {hostname}",
            )

        elif rc == 0 and out:
            result(
                "FAIL",
                "Reverse name resolution",
                (
                    f"{address} resolved to "
                    f"{', '.join(resolved_names) or 'unknown'}, "
                    f"expected {hostname}"
                ),
            )

        else:
            result(
                "WARN",
                "Reverse name resolution",
                f"no PTR/NSS result for {address}",
            )


def check_time():
    if not exists("timedatectl"):
        result(
            "WARN",
            "Time synchronization",
            "'timedatectl' is not available",
        )
        return

    rc, out, _ = run(
        [
            "timedatectl",
            "show",
            "-p",
            "NTPSynchronized",
            "--value",
        ]
    )

    if rc == 0 and out.lower() == "yes":
        result(
            "PASS",
            "Time synchronization",
            "NTPSynchronized=yes",
        )

    elif rc == 0 and out.lower() == "no":
        result(
            "FAIL",
            "Time synchronization",
            "NTPSynchronized=no",
        )

    else:
        result(
            "WARN",
            "Time synchronization",
            "unable to confirm synchronization",
        )


def check_cloud_init():
    if not exists("cloud-init"):
        result(
            "INFO",
            "cloud-init",
            "not installed",
        )
        return

    rc, out, err = run(
        ["cloud-init", "status"]
    )

    text = f"{out}\n{err}".strip().lower()

    if rc == 0 and "done" in text:
        result(
            "PASS",
            "cloud-init",
            "completed",
        )

    elif "running" in text:
        result(
            "WARN",
            "cloud-init",
            "still running",
        )

    else:
        result(
            "FAIL",
            "cloud-init",
            text or f"exit code {rc}",
        )


def check_systemd():
    if not exists("systemctl"):
        result(
            "WARN",
            "Failed systemd services",
            "'systemctl' is not available",
        )
        return

    rc, out, err = run(
        [
            "systemctl",
            "--failed",
            "--no-legend",
            "--no-pager",
        ]
    )

    if rc != 0:
        result(
            "WARN",
            "Failed systemd services",
            err or "unable to query systemd",
        )

    elif out:
        result(
            "FAIL",
            "Failed systemd services",
            f"{len(out.splitlines())} failed unit(s)",
        )

    else:
        result(
            "PASS",
            "Failed systemd services",
            "none",
        )


def check_ssh():
    sshd = shutil.which("sshd")

    if not sshd:
        result(
            "INFO",
            "SSH security",
            "sshd is not installed",
        )
        return

    rc, out, err = run(
        [sshd, "-T"]
    )

    if rc != 0:
        result(
            "WARN",
            "SSH security",
            err or "unable to read effective sshd configuration",
        )
        return

    settings = {}

    for line in out.splitlines():
        key, _, value = line.partition(" ")
        settings[key.lower()] = value.strip().lower()

    root_login = settings.get("permitrootlogin")
    password_auth = settings.get("passwordauthentication")

    result(
        "PASS" if root_login == "no" else "FAIL",
        "SSH root login",
        f"PermitRootLogin={root_login or 'unknown'}",
    )

    result(
        "PASS" if password_auth == "no" else "FAIL",
        "SSH password authentication",
        f"PasswordAuthentication={password_auth or 'unknown'}",
    )


def check_sudoers():
    if not exists("visudo"):
        result(
            "WARN",
            "sudoers syntax",
            "'visudo' is not available",
        )
        return

    rc, out, err = run(
        ["visudo", "-c"]
    )

    result(
        "PASS" if rc == 0 else "FAIL",
        "sudoers syntax",
        (
            "valid"
            if rc == 0
            else err or out or f"exit code {rc}"
        ),
    )


def check_realm(expected_domain):
    if not exists("realm"):
        result(
            "FAIL" if expected_domain else "INFO",
            "Active Directory",
            (
                "realmd is not installed"
                if not expected_domain
                else (
                    f"realmd is not installed; "
                    f"expected domain is {expected_domain}"
                )
            ),
        )
        return

    rc, out, err = run(
        ["realm", "list", "--name-only"]
    )

    if rc != 0:
        result(
            "FAIL" if expected_domain else "WARN",
            "Active Directory",
            err or "realm list failed",
        )
        return

    realms = [
        line.strip()
        for line in out.splitlines()
        if line.strip()
    ]

    if not realms:
        result(
            "FAIL" if expected_domain else "INFO",
            "Active Directory",
            (
                f"not joined to {expected_domain}"
                if expected_domain
                else "not configured"
            ),
        )
        return

    if expected_domain:
        expected = expected_domain.rstrip(".").lower()

        normalized_realms = {
            realm.rstrip(".").lower()
            for realm in realms
        }

        if expected in normalized_realms:
            result(
                "PASS",
                "Active Directory",
                expected_domain,
            )
        else:
            result(
                "FAIL",
                "Active Directory",
                (
                    f"joined to {', '.join(realms)}, "
                    f"expected {expected_domain}"
                ),
            )

    else:
        result(
            "PASS",
            "Active Directory",
            ", ".join(realms),
        )


def report():
    print("Linux VM Validation")
    print("===================")
    print()

    for level, check, details in RESULTS:
        suffix = f": {details}" if details else ""
        print(f"[{level}] {check}{suffix}")

    failures = sum(
        level == "FAIL"
        for level, _, _ in RESULTS
    )

    warnings = sum(
        level == "WARN"
        for level, _, _ in RESULTS
    )

    print()

    if failures:
        print(
            f"Result: FAIL "
            f"({failures} failed, {warnings} warning)"
        )
        return 1

    if warnings:
    print(
        f"Result: INCOMPLETE "
        f"({warnings} warning)"
    )
    return 2

    print("Result: PASS")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Read-only validation checks "
            "for a provisioned Linux VM."
        )
    )

    parser.add_argument(
        "--expected-fqdn",
        help="Expected VM FQDN",
    )

    parser.add_argument(
        "--expected-ip",
        help="Expected VM IPv4 address",
    )

    parser.add_argument(
        "--domain",
        help="Expected Active Directory domain",
    )

    args = parser.parse_args()

    hostname = check_hostname(
        args.expected_fqdn
    )

    address = check_ipv4(
        args.expected_ip
    )

    check_routes()

    check_resolution(
        args.expected_fqdn or hostname,
        args.expected_ip or address,
    )

    check_time()
    check_cloud_init()
    check_systemd()
    check_ssh()
    check_sudoers()
    check_realm(args.domain)

    sys.exit(report())


if __name__ == "__main__":
    main()
