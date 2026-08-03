#!/usr/bin/python

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: sr_fingerprint
short_description: Write role fingerprint data to syslog and optionally to a JSONL log file.
description:
    - Collects role fingerprint data into a canonical record and writes it to
      syslog using Ansible C(module.log) as C(key=value) pairs.
    - Optionally appends the same record as a JSON line to a log file
      (one JSON object per line, JSONL format), by default
      C(/var/log/sysroles.jsonl).
    - Playbook variables are not available inside modules automatically. Roles
      pass C(role_name), C(role_path), C(ansible_play_hosts_all), and
      C(ansible_facts) from the task.
    - C(ansible_check_mode) is collected from the module execution context.
    - Intended for role-internal or diagnostic use.
author: Rich Megginson (@richm)
options:
    status:
        description: Role execution status.
        type: str
        required: true
        choices:
            - begin
            - success
    write_log_file:
        description: >-
            If C(true), append fingerprint data to the JSONL log file.
            Defaults to C(false).
        type: bool
        default: false
    log_file:
        description: Path to the JSONL log file.
        type: path
        default: /var/log/sysroles.jsonl
    role_name:
        description: Name of the role, typically C({{ role_name }}).
        type: str
        required: true
    role_path:
        description: Path to the role, typically C({{ role_path }}).
        type: path
        required: true
    ansible_play_hosts_all:
        description: >-
            All hosts in the play, typically C({{ ansible_play_hosts_all }}).
            Used to derive C(play_hosts_number).
        type: list
        elements: str
        required: true
    ansible_facts:
        description: >-
            Facts from the playbook for the current managed host, typically
            C({{ ansible_facts }}).
        type: dict
        required: true
"""

EXAMPLES = """
- name: Record role begin fingerprint to syslog only (not log file)
  sr_fingerprint:
    status: begin
    role_name: bootloader
    role_path: "{{ role_path }}"
    ansible_play_hosts_all: "{{ ansible_play_hosts_all }}"
    ansible_facts: "{{ ansible_facts }}"
    write_log_file: false

- name: Record role success fingerprint
  sr_fingerprint:
    status: success
    role_name: bootloader
    role_path: "{{ role_path }}"
    ansible_play_hosts_all: "{{ ansible_play_hosts_all }}"
    ansible_facts: "{{ ansible_facts }}"
    write_log_file: true
"""

RETURN = r""" # """

from ansible.module_utils.basic import AnsibleModule

import datetime
import errno
import json
import os

DEFAULT_LOG_FILE = "/var/log/sysroles.jsonl"

FINGERPRINT_FIELDS = (
    "date",
    "role_name",
    "role_path",
    "status",
    "ansible_version",
    "managed_node_distro",
    "play_hosts_number",
    "ansible_check_mode",
)

FINGERPRINT_SYSLOG_SEPARATOR = " "


def _local_iso8601_no_microseconds():
    """System local wall clock with local tz offset, ISO 8601, seconds only."""
    try:
        utc = datetime.timezone.utc
    except AttributeError:
        import time

        return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())
    # Prefer the local clock interpreted in the system timezone (not UTC displayed).
    now = datetime.datetime.now()
    astimezone = getattr(now, "astimezone", None)
    if astimezone is not None:
        try:
            return astimezone().replace(microsecond=0).isoformat()
        except (OSError, TypeError, ValueError):
            pass
    return datetime.datetime.now(utc).astimezone().replace(microsecond=0).isoformat()


def _ensure_parent_dir(path):
    parent = os.path.dirname(path)
    if not parent:
        return
    if os.path.isdir(parent):
        return
    try:
        os.makedirs(parent)
    except OSError as exc:
        if exc.errno != errno.EEXIST or not os.path.isdir(parent):
            raise


def _format_fingerprint_jsonl(record):
    """Format the canonical fingerprint record as a single JSON line."""
    return json.dumps(record, separators=(",", ":"), sort_keys=False)


def _write_jsonl_log(log_file, record):
    _ensure_parent_dir(log_file)
    with open(log_file, "a") as log_fd:
        log_fd.write(_format_fingerprint_jsonl(record) + "\n")


def _get_managed_node_distro(facts):
    distribution = facts.get("distribution")
    distribution_version = facts.get("distribution_version")
    if distribution and distribution_version:
        return "%s-%s" % (distribution, distribution_version)
    return "unknown"


def _get_play_hosts_number(play_hosts_all):
    return len(play_hosts_all)


def _get_ansible_version(module):
    version = getattr(module, "ansible_version", None)
    if version:
        return version
    return "unknown"


def _get_check_mode(module):
    return bool(getattr(module, "check_mode", False))


def _collect_fingerprint_record(module, status):
    """Build the canonical fingerprint record used by all output formatters."""
    return {
        "date": _local_iso8601_no_microseconds(),
        "role_name": module.params["role_name"],
        "role_path": module.params["role_path"],
        "status": status,
        "ansible_version": _get_ansible_version(module),
        "managed_node_distro": _get_managed_node_distro(module.params["ansible_facts"]),
        "play_hosts_number": _get_play_hosts_number(
            module.params["ansible_play_hosts_all"]
        ),
        "ansible_check_mode": _get_check_mode(module),
    }


def _fingerprint_record_items(record):
    return [(field, record[field]) for field in FINGERPRINT_FIELDS]


def _format_fingerprint_key_value(field, value):
    text = "" if value is None else str(value)
    if any(char in text for char in ' "='):
        return '%s="%s"' % (field, text.replace('"', '""'))
    return "%s=%s" % (field, text)


def _format_fingerprint_syslog(record):
    """Format the canonical fingerprint record as key=value syslog text."""
    pairs = [
        _format_fingerprint_key_value(field, value)
        for field, value in _fingerprint_record_items(record)
    ]
    return FINGERPRINT_SYSLOG_SEPARATOR.join(pairs)


def run_module():
    module_args = dict(
        status=dict(type="str", required=True, choices=["begin", "success"]),
        write_log_file=dict(type="bool", default=False),
        log_file=dict(type="path", default=DEFAULT_LOG_FILE),
        role_name=dict(type="str", required=True),
        role_path=dict(type="path", required=True),
        ansible_play_hosts_all=dict(type="list", elements="str", required=True),
        ansible_facts=dict(type="dict", required=True, no_log=True),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    fingerprint_record = _collect_fingerprint_record(module, module.params["status"])
    log_message = _format_fingerprint_syslog(fingerprint_record)

    if module.check_mode:
        result = dict(
            changed=False,
            message="Check mode: message not logged - [%s]" % log_message,
            fingerprint=fingerprint_record,
        )
        if module.params["write_log_file"]:
            result["jsonl_row"] = _format_fingerprint_jsonl(fingerprint_record)
            result["log_file"] = module.params["log_file"]
        module.exit_json(**result)

    module.log(log_message)

    if module.params["write_log_file"]:
        log_file = module.params["log_file"]
        try:
            _write_jsonl_log(log_file, fingerprint_record)
        except (IOError, OSError) as exc:
            module.fail_json(
                msg="Failed to write fingerprint log file %s: %s"
                % (log_file, exc)
            )

    # we don't actually change anything, so we're not changed - writing a log message
    # is not considered a change
    # also, we don't want to report changed every time the role runs
    module.exit_json(changed=False, fingerprint=fingerprint_record)


def main():
    run_module()


if __name__ == "__main__":
    main()
