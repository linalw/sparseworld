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
