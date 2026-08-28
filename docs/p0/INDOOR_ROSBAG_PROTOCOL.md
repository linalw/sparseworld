# Indoor Gemini 335 rosbag protocol

The run is an attended, hand-carried, motor-disabled P0 observability capture.
Clear the test zone, verify the exact device serial and required topics, and
record metadata before opening streams.

## Preflight and stationary check

Run `ros2 launch orbbec_camera gemini_330_series.launch.py --show-args` and
inspect arguments before any stream. Confirm RGB, depth, left/right IR,
camera-info, IMU, and TF topics plus QoS match the profile. Record 30 seconds
stationary with the camera on a stable surface; monitor dropped frames,
timestamps, exposure/blur, depth validity, and IMU saturation.

## Exact route

Use one continuous bag and the same pace throughout:

`start -> textured wall/doorframe -> 90-degree turn -> texture-poor wall -> doorway -> return -> stop`

Keep lighting stable and diffuse where possible; walk at a measured, repeatable
pace. Stop immediately for a person entering the zone, cable/device movement,
thermal or USB errors, stream loss, saturation, unsafe clearance, or an
operator unable to maintain the route. Repeat rather than splice segments.

## Recording, metadata, replay

Example command (adapt storage/output names only after preflight):

```bash
ros2 bag record -o artifacts/rosbags/<run-id> \
  /camera/color/image_raw /camera/color/camera_info \
  /camera/depth/image_raw /camera/depth/camera_info \
  /camera/left/image_raw /camera/right/image_raw /camera/imu \
  /tf /tf_static
```

Store the profile and hash, serial/model/firmware, SDK and ROS/driver versions,
operator, UTC start/stop, room/light notes, route pace, topic types/QoS, and
preflight output beside the bag. Export timestamps with
`scripts/p0_export_rosbag_timestamps.py`; recorded bag time and message-header
time must remain separate and unknown sequences must be null. Replay only proves
bag readability and timing inspection:

```bash
ros2 bag play artifacts/rosbags/<run-id> --clock
```

Replay does not establish SLAM, ATE/RPE, navigation, semantic, or safety
performance. Every quality/calibration/time gate remains `not_measured` until
raw evidence is reviewed.
