import pandas as pd

from quant.data import gpw


def test_fw20_name_parsing():
    d = pd.Timestamp
    assert gpw.fw20_contract("FW20H5", d("2005-01-03")) == (2005, 3)
    assert gpw.fw20_contract("FW20U5", d("2005-01-03")) == (2005, 9)
    assert gpw.fw20_contract("FW20H6", d("2005-12-20")) == (2006, 3)
    assert gpw.fw20_contract("FW20Z10", d("2010-06-01")) == (2010, 12)
    assert gpw.fw20_contract("FW20H2220", d("2022-01-03")) == (2022, 3)
    assert gpw.fw20_contract("FW20Z2220", d("2022-01-03")) == (2022, 12)
    assert gpw.fw20_contract("FW20H2320", d("2022-12-30")) == (2023, 3)
    assert gpw.fw20_contract("FW40H5", d("2005-01-03")) is None


def test_parse_xls_rejects_html():
    assert gpw.parse_xls(b"<html>" + b" " * 2000).empty
