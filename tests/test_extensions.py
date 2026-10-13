import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from finops import pricing


def test_cache_break_even_reads():
    # Large model: write $3.75, read base $3.00, discount 10% (saves $2.70 per read)
    # 3.75 / 2.70 = ~1.39 reads
    be = pricing.cache_break_even_reads(3.75, 3.00, 0.10)
    assert abs(be - 1.39) < 0.05

    # Small model: write $0.25, read base $0.20, discount 10% (saves $0.18 per read)
    # 0.25 / 0.18 = ~1.39 reads
    be_small = pricing.cache_break_even_reads(0.25, 0.20, 0.10)
    assert abs(be_small - 1.39) < 0.05


def test_cache_is_worth_it():
    # 3 reads exceeds break-even (1.39) -> should be True
    assert pricing.cache_is_worth_it(3.0, write_cost_per_m=3.75, read_base_cost_per_m=3.00) is True

    # 1 read does not exceed break-even (1.39) -> should be False
    assert pricing.cache_is_worth_it(1.0, write_cost_per_m=3.75, read_base_cost_per_m=3.00) is False

    # Edge cases
    assert pricing.cache_is_worth_it(0.0) is False
