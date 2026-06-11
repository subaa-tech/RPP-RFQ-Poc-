from validation.benchmark import score_lengths


def test_length_scoring_within_tolerance():
    gt = [{"sheet": "M-101", "dimension": "24x12", "length_ft_expected": 50.0, "length_tolerance_ft": 2.0}]
    got = [{"sheet": "M-101", "dimension": "24x12", "length_ft": 51.0}]
    acc = score_lengths(gt, got)
    assert acc == 1.0
