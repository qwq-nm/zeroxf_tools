#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""geshell 最小回归自测（unittest）。"""
import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ai import cli_runner  # noqa: E402
from ai import fuzzy  # noqa: E402


class TestNormalize(unittest.TestCase):
    def test_case_space_dash_underscore(self):
        self.assertEqual(fuzzy.normalize_name("Nmap Scan"), "nmapscan")
        self.assertEqual(fuzzy.normalize_name("  SQL-注入_检测  "), "sql注入检测")

    def test_alias_style(self):
        self.assertEqual(fuzzy.normalize_name("CobaltStrike 4.9"), "cobaltstrike4.9")


class TestFindTool(unittest.TestCase):
    def setUp(self):
        self.tools = [
            {"name": "nmap", "category": "信息收集", "type": "命令行", "path": "nmap",
             "description": "端口扫描", "aliases": ["nmap-rs"]},
            {"name": "SQL 注入检测", "category": "漏洞扫描", "type": "命令行", "path": "sqlmap",
             "description": "SQLMap 注入", "aliases": ["sqlmap"]},
        ]

    def test_exact(self):
        self.assertEqual(fuzzy.find_tool(self.tools, "nmap")["name"], "nmap")

    def test_alias(self):
        self.assertEqual(fuzzy.find_tool(self.tools, "sqlmap")["name"], "SQL 注入检测")

    def test_case_and_space(self):
        self.assertEqual(fuzzy.find_tool(self.tools, "NMap")["name"], "nmap")
        self.assertEqual(fuzzy.find_tool(self.tools, "n map")["name"], "nmap")

    def test_not_found(self):
        self.assertIsNone(fuzzy.find_tool(self.tools, "zzz_not_exist"))


class TestBuildCommand(unittest.TestCase):
    def test_cli_bare_command(self):
        built = cli_runner.build_command(
            {"name": "nmap", "type": "命令行", "path": "nmap"}, ["-sV", "127.0.0.1"])
        self.assertEqual(built["kind"], "cmd")
        self.assertEqual(built["cmd"][0], "nmap")
        self.assertIn("-sV", built["cmd"])

    def test_cli_pre_post_params(self):
        built = cli_runner.build_command(
            {"name": "x", "type": "命令行", "path": "tool", "params_pre": "-a -b", "params": "-c"}, ["-d"])
        self.assertEqual(built["cmd"], ["tool", "-a", "-b", "-c", "-d"])

    def test_web(self):
        built = cli_runner.build_command({"name": "x", "type": "网页", "url": "http://t.com"}, [])
        self.assertEqual(built["kind"], "web")

    def test_gui(self):
        built = cli_runner.build_command(
            {"name": "x", "type": "GUI应用", "path": "C:/tools/a.exe"}, [])
        self.assertEqual(built["kind"], "gui")


class TestConfig(unittest.TestCase):
    def test_load(self):
        import config
        self.assertIsInstance(config.load_tools(), list)
        self.assertIsInstance(config.load_categories(), list)


if __name__ == "__main__":
    unittest.main(verbosity=2)
