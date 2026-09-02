# Indoor Gemini 335 rosbag protocol

The run is an attended, hand-carried, motor-disabled P0 observability capture.
Clear the test zone, verify the exact device serial and required topics, and
record metadata before opening streams.

## Preflight and stationary check

Run `ros2 launch orbbec_camera gemini_330_series.launch.py --show-args` and
inspect arguments before any stream once ROS 2 and the matching driver are
installed. The preflight must confirm RGB, depth, left/right IR, camera-info,
IMU, and TF topics plus QoS match the profile before recording. The SDK-only
stationary timestamp capture is separate evidence; it does not substitute for
ROS topics, camera-info, TF, QoS, or MCAP replay.

The ROS 2 base tools and pinned official Orbbec driver are now installed on the
reference host. For a fresh host, `bash scripts/p0_install_ros2_humble.sh`
remains the reviewed base installer (it prompts for local sudo and deliberately
does not choose an Orbbec driver version). On the reference host, source
`/opt/ros/humble/setup.bash` and
`/home/ubuntu/ros2_ws/install-systempy4/setup.bash`, then rerun the
`--show-args` preflight before opening streams.

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
  /camera/left_ir/image_raw /camera/left_ir/camera_info \
  /camera/right_ir/image_raw /camera/right_ir/camera_info \
  /camera/accel/sample /camera/gyro/sample \
  /camera/accel/imu_info /camera/gyro/imu_info /camera/device_status \
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

## User-space diagnostic MCAP fallback

When ROS 2 and the official Orbbec driver are unavailable, the optional
`.[mcap]` Python extra can package existing normalized SDK timestamp rows into
a ROS 2 MCAP container using `rosbags`. This produces exactly one topic,
`/sparseworld/p0/normalized_sample` of type `std_msgs/msg/String`; each message
is the canonical JSON of one pre-existing SDK row, recorded at that row's host
receive time. It deliberately does **not** synthesize camera images,
camera-info, TF, QoS, message headers, or missing frames.

Use this only for user-space container-readability and timestamp-diagnostic
replay. It is not an Orbbec ROS-driver bag and cannot satisfy the required ROS
topic/TF/camera-info preflight, hardware synchronization, calibration, SLAM,
or navigation evidence. Preserve the resulting MCAP, `metadata.yaml`, source
JSONL hash, MCAP hash, tool versions, and this interpretation alongside the
capture evidence.
