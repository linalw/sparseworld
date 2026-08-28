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


def test_normalized_device_timestamps_are_canonical_and_do_not_guess_units():
    result = analyze_stream([
        {"seq": 0, "device_time_ns": 100, "host_receive_time_ns": 1_000},
        {"seq": 1, "device_time_ns": 200, "host_receive_time_ns": 1_100},
    ])
    assert result["status"] == "measured"
    assert result["observed_rate_hz"] == 20_000_000

    ambiguous = analyze_stream([{"seq": 0, "timestamp": 0}, {"seq": 1, "timestamp": 1}])
    assert ambiguous["status"] == "not_measured"


def test_ros_header_pairing_uses_explicit_header_time_ns():
    samples = {
        "rgb": [{"frame_number": 1, "device_time_ns": 100, "header_time_ns": 1_000}],
        "depth": [{"frame_number": 1, "device_time_ns": 150, "header_time_ns": 1_025}],
    }
    assert analyze_interstream(samples)["offsets_ns"]["rgb-depth"] == [50]
    assert analyze_interstream(samples, pairing_policy="ros_header_frame_number")["offsets_ns"]["rgb-depth"] == [25]


def test_duplicate_and_out_of_order_ids_are_reported_deterministically():
    result = analyze_stream([
        {"seq": "2", "device_time_ns": 20},
        {"seq": "1", "device_time_ns": 10},
        {"seq": "2", "device_time_ns": 30},
        {"seq": "4", "device_time_ns": 40},
    ])
    assert result["status"] == "not_measured"
    assert result["missing_sequences"] == 1
    assert result["duplicate_sequences"] == [2]
    assert result["out_of_order_sequences"] == 1

    paired = analyze_interstream({
        "rgb": [
            {"frame_number": "10", "device_time_ns": 100},
            {"frame_number": "2", "device_time_ns": 20},
            {"frame_number": "3", "device_time_ns": 30},
            {"frame_number": "3", "device_time_ns": 35},
        ],
        "depth": [
            {"frame_number": 2, "device_time_ns": 30},
            {"frame_number": 10, "device_time_ns": 130},
            {"frame_number": 3, "device_time_ns": 40},
        ],
    })
    assert paired["offsets_ns"]["rgb-depth"] == [10, 30]
    assert paired["duplicate_frame_ids"]["rgb"] == [3]


def test_zero_or_negative_timestamp_duration_fails_closed():
    result = analyze_stream([
        {"seq": 0, "device_time_ns": 100},
        {"seq": 1, "device_time_ns": 100},
    ])
    assert result["status"] == "not_measured"
    assert result["nonmonotonic_timestamps"] == 1
