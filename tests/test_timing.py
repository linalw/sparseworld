from sparseworld_p0.timing import analyze_stream, analyze_interstream


def test_sequence_gap_rate_and_monotonicity_are_measured():
    samples = [
        {"seq": 0, "timestamp_ns": 0},
        {"seq": 1, "timestamp_ns": 33_000_000},
        {"seq": 3, "timestamp_ns": 70_000_000},
    ]
    result = analyze_stream(samples)
    assert result["missing_sequences"] == 1
    assert result["nonmonotonic_timestamps"] == 0
    assert result["observed_rate_hz"] == 3 / 0.07


def test_interstream_offsets_require_compatible_frame_numbers():
    rgb = [{"frame_number": 1, "timestamp_ns": 100}, {"frame_number": 2, "timestamp_ns": 200}]
    depth = [{"frame_number": 1, "timestamp_ns": 150}, {"frame_number": 9, "timestamp_ns": 1000}]
    result = analyze_interstream({"rgb": rgb, "depth": depth})
    assert result["offsets_ns"]["rgb-depth"] == [50]
    assert result["pairing_status"] == "measured"


def test_interstream_does_not_pair_arbitrary_nearest_timestamps():
    result = analyze_interstream({
        "rgb": [{"timestamp_ns": 100}],
        "depth": [{"timestamp_ns": 101}],
    })
    assert result["pairing_status"] == "not_measured"
    assert result["offsets_ns"] == {}


def test_inadequate_stream_data_is_not_measured():
    result = analyze_stream([{"seq": 0, "timestamp_ns": 1}])
    assert result["status"] == "not_measured"
    assert result["observed_rate_hz"] is None
