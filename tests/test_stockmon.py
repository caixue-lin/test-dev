import io
import json
import unittest
from contextlib import redirect_stdout

from stockmon.alerts import Alert, evaluate
from stockmon.cli import main
from stockmon.display import render_table, sparkline
from stockmon.providers import ProviderError, Quote, SimulatedProvider, YahooProvider


def q(price, prev=100.0, sym="AAPL"):
    return Quote(sym, price, prev)


class TestQuote(unittest.TestCase):
    def test_change(self):
        self.assertAlmostEqual(q(110).change, 10)
        self.assertAlmostEqual(q(90).change_pct, -10)
        self.assertEqual(Quote("X", 5, 0).change_pct, 0.0)


class TestAlerts(unittest.TestCase):
    def test_parse(self):
        a = Alert.parse(" aapl > 200.5 ")
        self.assertEqual((a.symbol, a.op, a.value), ("AAPL", ">", 200.5))
        self.assertTrue(Alert.parse("TSLA%-5").signed)
        self.assertFalse(Alert.parse("TSLA%5").signed)
        self.assertEqual(Alert.parse("BRK.B<400").symbol, "BRK.B")
        for bad in ["AAPL", "AAPL=5", ">5", "AAPL>abc"]:
            with self.assertRaises(ValueError):
                Alert.parse(bad)

    def test_above_below(self):
        self.assertTrue(Alert.parse("AAPL>105").condition(q(106)))
        self.assertFalse(Alert.parse("AAPL>105").condition(q(105)))
        self.assertTrue(Alert.parse("AAPL<95").condition(q(94)))

    def test_percent(self):
        self.assertTrue(Alert.parse("AAPL%5").condition(q(94)))
        self.assertTrue(Alert.parse("AAPL%5").condition(q(106)))
        self.assertFalse(Alert.parse("AAPL%+5").condition(q(94)))
        self.assertTrue(Alert.parse("AAPL%-5").condition(q(94)))
        self.assertFalse(Alert.parse("AAPL%-5").condition(q(106)))

    def test_fires_once_then_rearms(self):
        a = Alert.parse("AAPL>105")
        self.assertIsNotNone(a.check(q(110)))
        self.assertIsNone(a.check(q(111)))  # still above: no repeat
        self.assertIsNone(a.check(q(100)))  # drops: re-arm
        self.assertIsNotNone(a.check(q(106)))

    def test_evaluate_ignores_missing(self):
        alerts = [Alert.parse("AAPL>1"), Alert.parse("MSFT>1")]
        msgs = evaluate(alerts, {"AAPL": q(5)})
        self.assertEqual(len(msgs), 1)
        self.assertIn("AAPL is above 1", msgs[0])


class TestProviders(unittest.TestCase):
    def test_simulated_deterministic(self):
        a = SimulatedProvider(seed=1).get_quotes(["aapl", "msft"])
        b = SimulatedProvider(seed=1).get_quotes(["AAPL", "MSFT"])
        self.assertEqual({k: v.price for k, v in a.items()}, {k: v.price for k, v in b.items()})
        self.assertEqual(set(a), {"AAPL", "MSFT"})

    def test_yahoo_parse(self):
        data = {"chart": {"result": [{"meta": {
            "regularMarketPrice": 190.5, "chartPreviousClose": 188.0,
            "currency": "USD", "regularMarketTime": 1700000000}}], "error": None}}
        quote = YahooProvider.parse("aapl", data)
        self.assertEqual((quote.symbol, quote.price, quote.previous_close), ("AAPL", 190.5, 188.0))

    def test_yahoo_parse_error(self):
        data = {"chart": {"result": None, "error": {"description": "No data found"}}}
        with self.assertRaises(ProviderError):
            YahooProvider.parse("ZZZZ", data)


class TestDisplay(unittest.TestCase):
    def test_sparkline(self):
        self.assertEqual(sparkline([1]), "")
        self.assertEqual(sparkline([1, 2, 3]), "▁▄█")

    def test_table(self):
        out = render_table({"AAPL": q(110)}, ["AAPL", "MSFT"], color=False)
        self.assertIn("110.00", out)
        self.assertIn("+10.00%", out)
        self.assertIn("MSFT", out)
        self.assertNotIn("\033[", out)


class TestCLI(unittest.TestCase):
    def run_cli(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(list(argv))
        return code, buf.getvalue()

    def test_once_simulated(self):
        code, out = self.run_cli("AAPL", "msft", "-p", "simulated", "--seed", "3", "--once", "--no-color")
        self.assertEqual(code, 0)
        self.assertIn("AAPL", out)
        self.assertIn("MSFT", out)

    def test_alert_fires_and_adds_symbol(self):
        code, out = self.run_cli("-p", "simulated", "--seed", "3", "--once", "--no-color", "-a", "NVDA>0")
        self.assertEqual(code, 0)
        self.assertIn("ALERT: NVDA is above 0", out)

    def test_config_and_errors(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "c.json")
            csv = os.path.join(d, "q.csv")
            with open(cfg, "w") as fh:
                json.dump({"symbols": ["IBM"], "provider": "simulated", "interval": 0}, fh)
            code, out = self.run_cli("-c", cfg, "-n", "2", "--no-color", "--csv", csv)
            self.assertEqual(code, 0)
            self.assertEqual(out.count("IBM"), 2)
            with open(csv) as fh:
                self.assertEqual(len(fh.readlines()), 3)  # header + 2 rows
        with redirect_stdout(io.StringIO()), unittest.mock.patch("sys.stderr", io.StringIO()):
            self.assertEqual(main(["-p", "simulated", "--once"]), 2)
            self.assertEqual(main(["X", "-a", "bad", "--once"]), 2)


import unittest.mock  # noqa: E402

if __name__ == "__main__":
    unittest.main()
