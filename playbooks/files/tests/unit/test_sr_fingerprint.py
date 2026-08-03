# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Red Hat, Inc.
# SPDX-License-Identifier: MIT
"""Unit tests for sr_fingerprint module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import os
import tempfile
import unittest

import sr_fingerprint


class _FakeModule(object):
    ansible_version = "2.16.3"

    def __init__(self, params=None, check_mode=False):
        self.params = params or {}
        self.check_mode = check_mode


def _sample_fingerprint_record():
    return {
        "date": "2026-06-10T12:00:00+00:00",
        "role_name": "systemd",
        "role_path": "/usr/share/ansible/roles/systemd",
        "status": "begin",
        "ansible_version": "2.16.3",
        "managed_node_distro": "RedHat-9.4",
        "play_hosts_number": 3,
        "ansible_check_mode": False,
    }


class TestSrFingerprint(unittest.TestCase):
    def test_fingerprint_fields_match_record_keys(self):
        record = _sample_fingerprint_record()
        self.assertEqual(set(sr_fingerprint.FINGERPRINT_FIELDS), set(record.keys()))

    def test_format_fingerprint_syslog(self):
        record = _sample_fingerprint_record()
        message = sr_fingerprint._format_fingerprint_syslog(record)
        self.assertEqual(
            message,
            "date=2026-06-10T12:00:00+00:00 role_name=systemd "
            "role_path=/usr/share/ansible/roles/systemd status=begin "
            "ansible_version=2.16.3 managed_node_distro=RedHat-9.4 "
            "play_hosts_number=3 ansible_check_mode=False",
        )
        for field in sr_fingerprint.FINGERPRINT_FIELDS:
            self.assertIn("%s=" % field, message)

    def test_format_fingerprint_jsonl(self):
        record = _sample_fingerprint_record()
        line = sr_fingerprint._format_fingerprint_jsonl(record)
        parsed = json.loads(line)
        self.assertEqual(parsed, record)

    def test_collect_fingerprint_record_from_passed_inputs(self):
        module = _FakeModule(
            {
                "role_name": "systemd",
                "role_path": "/usr/share/ansible/roles/systemd",
                "ansible_play_hosts_all": ["host1", "host2", "host3"],
                "ansible_facts": {
                    "distribution": "RedHat",
                    "distribution_version": "9.4",
                },
            },
            check_mode=True,
        )
        record = sr_fingerprint._collect_fingerprint_record(module, "begin")
        self.assertEqual(record["role_name"], "systemd")
        self.assertEqual(record["role_path"], "/usr/share/ansible/roles/systemd")
        self.assertEqual(record["managed_node_distro"], "RedHat-9.4")
        self.assertEqual(record["play_hosts_number"], 3)
        self.assertTrue(record["ansible_check_mode"])
        self.assertEqual(
            set(record.keys()),
            set(sr_fingerprint.FINGERPRINT_FIELDS),
        )

    def test_get_managed_node_distro_from_facts(self):
        distro = sr_fingerprint._get_managed_node_distro(
            {"distribution": "Fedora", "distribution_version": "42"}
        )
        self.assertEqual(distro, "Fedora-42")

    def test_get_managed_node_distro_missing(self):
        self.assertEqual(sr_fingerprint._get_managed_node_distro({}), "unknown")

    def test_get_play_hosts_number(self):
        self.assertEqual(
            sr_fingerprint._get_play_hosts_number(["a", "b"]),
            2,
        )
        self.assertEqual(sr_fingerprint._get_play_hosts_number([]), 0)

    def test_format_fingerprint_syslog_quotes_values_with_spaces(self):
        record = _sample_fingerprint_record()
        record["role_path"] = "/usr/share/ansible/roles/systemd extra"
        message = sr_fingerprint._format_fingerprint_syslog(record)
        self.assertIn('role_path="/usr/share/ansible/roles/systemd extra"', message)

    def test_write_jsonl_log_appends_valid_json_lines(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
            log_file = tmp.name

        try:
            record = _sample_fingerprint_record()
            sr_fingerprint._write_jsonl_log(log_file, record)
            sr_fingerprint._write_jsonl_log(log_file, record)

            with open(log_file, "r") as log_fd:
                lines = log_fd.read().splitlines()

            self.assertEqual(len(lines), 2)
            for line in lines:
                parsed = json.loads(line)
                self.assertEqual(parsed, record)
        finally:
            os.unlink(log_file)

    def test_write_jsonl_log_creates_parent_dir(self):
        tmpdir = tempfile.mkdtemp()
        log_file = os.path.join(tmpdir, "subdir", "fingerprint.jsonl")

        try:
            record = _sample_fingerprint_record()
            sr_fingerprint._write_jsonl_log(log_file, record)

            with open(log_file, "r") as log_fd:
                parsed = json.loads(log_fd.readline())
            self.assertEqual(parsed["role_name"], "systemd")
        finally:
            os.unlink(log_file)
            os.rmdir(os.path.dirname(log_file))
            os.rmdir(tmpdir)

    def test_write_jsonl_log_preserves_types(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
            log_file = tmp.name

        try:
            record = _sample_fingerprint_record()
            sr_fingerprint._write_jsonl_log(log_file, record)

            with open(log_file, "r") as log_fd:
                parsed = json.loads(log_fd.readline())

            self.assertIsInstance(parsed["play_hosts_number"], int)
            self.assertIsInstance(parsed["ansible_check_mode"], bool)
        finally:
            os.unlink(log_file)

    def test_local_iso8601_no_microseconds_has_no_fraction(self):
        timestamp = sr_fingerprint._local_iso8601_no_microseconds()
        self.assertNotIn(".", timestamp)


if __name__ == "__main__":
    unittest.main()
