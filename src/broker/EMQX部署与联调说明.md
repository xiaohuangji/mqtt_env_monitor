# EMQX 部署与 ESP32 联调说明

## 方案说明

本项目演示使用的 Broker 是 **EMQX 5.8.9**（与性能压测同版本，与"方案升级为 EMQX"的设计主线一致），在本地以 Docker 容器运行，由笔记本扮演"自建服务器层"。`mosquitto.conf` 保留作**无 Docker 环境时的离线备用方案**，两者对客户端（节点、ESP32）完全等价，连接地址端口一致。

关联：Issue #34（对接规范）、#35（ESP32 配网）。

## 一、首次部署（一次性）

前提：笔记本已安装 Docker Desktop。

1. 启动 Docker Desktop，等右下角图标变绿（引擎就绪）。
2. 拉取并启动 EMQX（首次需**登录 Docker Hub**，否则拉取会报 `registry-1.docker.io: EOF`）：

   ```powershell
   docker run -d --name emqx -p 1883:1883 -p 18083:18083 emqx/emqx:5.8.9
   ```

3. 确认：`docker ps` 看到 `emqx` 状态 `Up`，端口 `0.0.0.0:1883->1883`、`0.0.0.0:18083->18083`（绑 `0.0.0.0` 才能让 ESP32 经热点连入）。

## 二、日常启停

| 操作 | 命令 |
| --- | --- |
| 启动（已拉过镜像，秒级） | `docker start emqx` |
| 停止（省资源） | `docker stop emqx` |
| 看实时日志 | `docker logs -f emqx` |
| EMQX 内部状态 | `docker exec emqx emqx ctl status` |
| Dashboard | 浏览器开 `http://localhost:18083`，账号 `admin` 密码 `public`（首次登录改密） |

> Docker Desktop 关闭后引擎停止、容器随之停。联调前先确保 Docker Desktop 在运行。

## 三、联调前准备（笔记本侧，每次联调）

1. `docker start emqx` —— 启动 Broker。
2. 启动监控端（另一个终端）：

   ```powershell
   D:\anaconda\python.exe src\monitor\web_monitor.py
   ```

3. 防火墙放行 1883（**管理员** PowerShell，一次性）：

   ```powershell
   netsh advfirewall firewall add rule name="MQTT 1883" dir=in action=allow protocol=TCP localport=1883
   ```

4. 开 **Windows 移动热点**（设置 → 网络和 Internet → 移动热点）：
   - **务必确保笔记本自己联着网**（热点共享互联网），否则 ESP32 NTP 对不了时、按现固件逻辑不会发数据。
   - 热点网段下笔记本 IP 固定为 `192.168.137.1`，即 ESP32 端配置的 Broker 地址。

## 四、ESP32 侧（孙博宇负责）

- 配网：用 `tzapu/WiFiManager` 库实现"自动连/AP 配网门户"（见 Issue #35 评论）。
- MQTT：连 `192.168.137.1:1883`，QoS 1，MQTT 3.1.1，topic `env_monitor/node03/{data_type}`，data_type 取 `temperature`/`humidity`/`mq2_gas`/`soil_moisture`，payload 用完整 JSON 即可（详见 Issue #34 对接规范）。

## 五、验证流程（自底向上，每层先验证再上一层）

1. **服务器侧自检**（用 PC 模拟节点替 ESP32 先验，确认 Broker + 监控端 + 端口映射就绪）：

   ```powershell
   D:\anaconda\python.exe src\simulated_nodes\sim_node.py --host 192.168.137.1 --node-id node03 --types temperature,humidity,mq2_gas,soil_moisture --format json --mqtt-version 311 --qos 1 --count 5
   ```

   浏览器开 `http://127.0.0.1:8080/`，出现 node03 的温度/湿度/可燃气体/土壤湿度 = 服务器侧链路 OK。

2. **ESP32 接入**：孙博宇的 ESP32 上电 → 配网连热点 → 连 Broker → 发布。
3. **监控页确认** node03 的真实传感器数据；**Dashboard** 看连接数/消息速率曲线（答辩展示用）。

## 六、常见问题排查

| 现象 | 原因 | 解法 |
| --- | --- | --- |
| ESP32 WiFi 连上但连不上 1883 | Windows 防火墙未放行（最常见） | 跑第三步的 `netsh` 命令 |
| ESP32 卡在"时间未同步"、一条不发 | 热点没联网，NTP 失败 | 确保笔记本开热点时自己联着网 |
| 拉镜像报 `EOF` | 未登录 Docker Hub | 登录 Docker Desktop 后重试；或配国内镜像加速器 |
| 模拟节点连 192.168.137.1 失败 | 移动热点未开（该 IP 不存在） | 先开 Windows 移动热点 |
| 端口 1883 被占 | 之前的 Broker/容器没停 | `docker stop emqx` 或排查占用进程 |
