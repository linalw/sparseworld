# 实时稀疏建图模式

控制台中选择“实时稀疏建图（低存储）”后，系统默认不录制完整 rosbag，只保留关键帧、轨迹/地图导出、语义对象和少量预览缓存。语义处理不会逐帧执行：默认每 1 秒最多触发一次，或移动 0.35 m、旋转 15° 时触发；队列容量为 1，新关键帧会覆盖旧任务。

## 启动前

```bash
conda activate sparseworld
source /opt/ros/humble/setup.bash
source /home/ubuntu/ros2_ws/install-systempy4/setup.bash
pip install -e '.[console]'
sparseworld-p0 capture-console --host 127.0.0.1 --port 8765 --output-dir artifacts/rosbags
```

本机若没有 `rtabmap_ros`，实时模式会显示 `SLAM unavailable`，不会伪造轨迹或地图。安装 RTAB-Map 后再进行短时人工监护验证；该模式仍不代表 ATE/RPE、标定、同步、语义精度或导航验收。

勾选“同时录制原始 bag（调试）”只在需要回放/标定时使用，会显著增加存储。停止后运行目录会保存 manifest、日志、对象快照和可用地图文件。

## 仿真验证入口（2026-09-04）

新增轻量确定性仿真核心与 Isaac Sim 适配入口：

```bash
PYTHONPATH=src conda run -n sparseworld python -m sparseworld_p0.cli sim-smoke \
  --output artifacts/evidence/simulation_smoke.json
```

输出 JSON 包含 `evidence_class=simulation_evidence`、RGB/depth/camera_info/IMU/odom/TF 契约、轨迹、终点误差、路径长度、碰撞和重规划计数。它使用简化差速运动学，仅验证规划/执行接口，不代表 Gemini 335 或真实底盘可通行性。

Isaac Sim 6 适配器入口为 `scripts/isaacsim_semantic_nav_smoke.py`，应使用 `/home/ubuntu/linalw/App/isaacsim/_build/linux-x86_64/release/python.sh` 启动；当前仅做依赖与 ROS 2 bridge 检查，Carter/Jetbot USD 场景、传感器发布和 Nav2 闭环仍待接入。
