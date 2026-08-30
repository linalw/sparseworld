# P0 Timing and Quality Assessment

Source SHA-256: `03547685cb53c2456b39d5206371aec25cda6951ad8871a3d6f88486a5ace514`

| Gate | Status | Value |
|---|---|---|
| acceleration_saturation | not_measured | None |
| blur | not_measured | None |
| depth_valid_fraction | not_measured | 0.45031404393287605 |
| device_host_offset | not_measured | 1.7878797630853156e+18 |
| gyro_saturation | not_measured | None |
| hand_carried_supervised_route | not_measured | None |
| stationary_calibration | not_measured | None |

Timing:

- depth: status=measured, rate=29.56377022023407, missing=None, nonmonotonic=0
- imu: status=not_measured, rate=None, missing=None, nonmonotonic=1800
- imu.accel: status=measured, rate=199.011817874556, missing=None, nonmonotonic=0
- imu.gyro: status=measured, rate=199.011817874556, missing=None, nonmonotonic=0
- left: status=measured, rate=29.56377022023407, missing=None, nonmonotonic=0
- rgb: status=measured, rate=29.9982377306445, missing=None, nonmonotonic=0
- right: status=measured, rate=29.56377022023407, missing=None, nonmonotonic=0

Capture manifest:
- status=captured_unassessed, manifest_sha256=5d1d2a850423038ad606e9127e89df9ef16f08b6ab4c9174c4242953567a73c7
- depth: missing_frame_numbers=13, duplicate_frame_numbers=[], out_of_order_frame_numbers=0
- imu.accel: missing_frame_numbers=4, duplicate_frame_numbers=[], out_of_order_frame_numbers=0
- imu.gyro: missing_frame_numbers=4, duplicate_frame_numbers=[], out_of_order_frame_numbers=0
- left: missing_frame_numbers=13, duplicate_frame_numbers=[], out_of_order_frame_numbers=0
- rgb: missing_frame_numbers=0, duplicate_frame_numbers=[], out_of_order_frame_numbers=0
- right: missing_frame_numbers=13, duplicate_frame_numbers=[], out_of_order_frame_numbers=0
