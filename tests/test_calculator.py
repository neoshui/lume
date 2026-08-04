"""Regression tests for Lume's calculator command."""

import unittest

from lume.search import _safe_eval, search_commands


class CalculatorTests(unittest.TestCase):
    def test_basic_arithmetic(self):
        self.assertEqual(_safe_eval("42 * 10"), "420")
        self.assertEqual(_safe_eval("(2 + 3) ** 3"), "125")
        self.assertEqual(_safe_eval("7 / 2"), "3.5")

    def test_supported_functions(self):
        self.assertEqual(_safe_eval("round(10 / 3, 2)"), "3.33")
        self.assertEqual(_safe_eval("sum([1, 2, 3])"), "6")
        self.assertEqual(_safe_eval("max(3, abs(-8))"), "8")

    def test_rejects_python_execution_features(self):
        unsafe = (
            "__import__('os').getcwd()",
            "().__class__.__base__.__subclasses__()",
            "(lambda: 1)()",
            "[x for x in range(3)]",
            "open('/tmp/lume-test', 'w')",
        )
        for expression in unsafe:
            with self.subTest(expression=expression):
                self.assertIsNone(_safe_eval(expression))

    def test_rejects_resource_abuse(self):
        self.assertIsNone(_safe_eval("2 ** 1000"))
        self.assertIsNone(_safe_eval("1" * 201))
        self.assertIsNone(_safe_eval("1 / 0"))

    def test_invalid_command_still_returns_feedback(self):
        result = search_commands("=__import__('os')")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "表达式无效")


if __name__ == "__main__":
    unittest.main()
