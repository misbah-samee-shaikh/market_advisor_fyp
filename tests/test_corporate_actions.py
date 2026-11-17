"""Quick local regression tests for split handling (standard unittest)."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.corporate_actions import CorporateActionError, ensure_split_adjusted


class SplitSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "data" / "psx" / "LUCK.csv"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        dates = pd.DatetimeIndex(
            list(pd.bdate_range("2025-03-20", "2025-04-18"))
            + list(pd.bdate_range("2025-04-28", "2025-05-30"))
        )
        n_pre = (dates < pd.Timestamp("2025-04-28")).sum()
        pre = 500 * (1 + np.arange(n_pre) * 0.0005)
        post = 100 * (1 + np.arange(len(dates)-n_pre) * 0.0005)
        raw = np.r_[pre, post]
        self.raw = pd.DataFrame({
            "Open": raw * 0.995,
            "High": raw * 1.01,
            "Low": raw * 0.99,
            "Close": raw,
            "Volume": np.where(np.arange(len(dates)) < n_pre, 1000, 5000),
        }, index=dates)
        self.raw.index.name = "Date"
        self.raw.to_csv(self.path)

    def test_luck_fix_and_second_run_is_noop(self):
        corrected = ensure_split_adjusted("psx", "LUCK", self.raw, self.path)
        before = corrected.index < pd.Timestamp("2025-04-28")
        np.testing.assert_allclose(corrected.loc[before, "Close"], self.raw.loc[before, "Close"] / 5)
        np.testing.assert_allclose(corrected.loc[before, "Volume"], self.raw.loc[before, "Volume"] * 5)
        np.testing.assert_allclose(corrected.loc[~before, "Close"], self.raw.loc[~before, "Close"])
        self.assertAlmostEqual(float(corrected["Close"].pct_change().abs().max()), 0.011, delta=0.01)
        csv_bytes = self.path.read_bytes()
        backed_up = list((self.root / "data" / "backups" / "psx").glob("*.csv"))
        self.assertEqual(len(backed_up), 1)
        reread = pd.read_csv(self.path, index_col=0, parse_dates=True)
        ensure_split_adjusted("psx", "LUCK", reread, self.path)
        self.assertEqual(self.path.read_bytes(), csv_bytes, "Adjusted file must not change twice")
        self.assertEqual(len(list((self.root / "data" / "backups" / "psx").glob("*.csv"))), 1)

    def test_unknown_big_jump_blocks_without_changing(self):
        other = self.root / "data" / "psx" / "OTHER.csv"
        self.raw.to_csv(other)
        original = other.read_bytes()
        with self.assertRaisesRegex(CorporateActionError, "UNVERIFIED"):
            ensure_split_adjusted("psx", "OTHER", self.raw, other)
        self.assertEqual(other.read_bytes(), original)

    def test_ambiguous_ratio_blocks_without_changing(self):
        ambiguous = self.raw.copy()
        before = ambiguous.index < pd.Timestamp("2025-04-28")
        ambiguous.loc[before, ["Open", "High", "Low", "Close"]] /= 2.4
        ambiguous.to_csv(self.path)
        old = self.path.read_bytes()
        with self.assertRaisesRegex(CorporateActionError, "ambiguous"):
            ensure_split_adjusted("psx", "LUCK", ambiguous, self.path)
        self.assertEqual(self.path.read_bytes(), old)

    def test_crypto_unmodified(self):
        kept = ensure_split_adjusted("crypto", "BTC-USD", self.raw, self.path)
        pd.testing.assert_frame_equal(kept, self.raw)

    def test_custom_verified_event(self):
        extra = self.root / "actions.json"
        extra.write_text(json.dumps({"psx": {"OTHER": [{
            "date": "2025-04-28", "factor": 5,
            "source": "https://example.org/official-confirmation"
        }]}}))
        other_path = self.root / "data" / "psx" / "OTHER.csv"
        self.raw.to_csv(other_path)
        result = ensure_split_adjusted("psx", "OTHER", self.raw, other_path, registry_path=extra)
        self.assertLess(result["Close"].pct_change().abs().max(), 0.10)


if __name__ == "__main__":
    unittest.main()
