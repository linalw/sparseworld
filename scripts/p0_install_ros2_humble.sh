#!/usr/bin/env bash
# Install official ROS 2 Humble tools required for P0 rosbag work.
set -euo pipefail

if [[ "$(. /etc/os-release && printf '%s' "$VERSION_ID")" != "22.04" ]]; then
  echo "refusing: ROS 2 Humble P0 installer requires Ubuntu 22.04" >&2
  exit 2
fi

sudo apt-get update
sudo apt-get install -y software-properties-common curl ca-certificates gnupg
sudo add-apt-repository -y universe
sudo curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
printf 'deb [arch=%s signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu jammy main\n' \
  "$(dpkg --print-architecture)" | sudo tee /etc/apt/sources.list.d/ros2.list >/dev/null
sudo apt-get update
sudo apt-get install -y \
  ros-humble-ros-base \
  ros-humble-rosbag2 \
  ros-humble-rosbag2-storage-mcap \
  ros-humble-tf2-tools \
  ros-humble-tf2-ros \
  ros-humble-image-transport

echo "Installed ROS 2 Humble P0 base. Start a new shell and run: source /opt/ros/humble/setup.bash"
echo "Next: install a pinned Orbbec ROS 2 driver version, then run ros2 launch ... --show-args before capture."
