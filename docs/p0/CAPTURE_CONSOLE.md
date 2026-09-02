# Gemini 335 采集控制台

## 启动

```bash
conda activate sparseworld
source /opt/ros/humble/setup.bash
source /home/ubuntu/ros2_ws/install-systempy4/setup.bash
pip install -e '.[console]'
sparseworld-p0 capture-console --host 127.0.0.1 --port 8765 --output-dir artifacts/rosbags
```

在本机浏览器打开 <http://127.0.0.1:8765/>。默认只监听本机；不要把端口暴露到局域网。代理变量只用于下载依赖或模型，不需要为本地服务设置。

## 采集流程

确认 Gemini 335 已连接且无人进入测试区，填写路线名称和备注，点击“开始录制”。按固定路线手持移动：纹理墙/门框 → 90° 转弯 → 低纹理墙 → 门口 → 返回。发生人员进入、线缆移动、USB/热异常、画面冻结或不安全间距时立即停止并重复采集。

点击“停止并保存”后，控制台会终止 ROS 驱动与 rosbag 子进程并保留运行目录。目录中的 `capture_manifest.json`、日志和 bag 是原始证据，不要手工拼接多个片段。

## 结果解释

控制台显示的完成状态只表示录制目录已保存。`not_measured` 不等于通过；采集本身不能证明 RGB-depth 对齐、时间同步、SLAM 位姿、语义识别精度、导航或安全性能。只有后续导出帧、接入 `map_T_camera` 并完成标定/同步/路线评估，才能生成可靠的全局语义地图。

如预览不可用，rosbag 仍可录制；请在备注中记录该情况。异常停止会保留 `failed_incomplete` 目录，优先保留日志供排查。
