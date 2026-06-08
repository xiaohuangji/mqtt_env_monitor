# 基于 MQTT 的多节点环境监测系统

## 项目简介

本项目为《数据通信与网络技术》课程设计，选题为《数据通信与网络技术课程设计题目和要求2026》中的题目 12：基于 MQTT 的多节点环境监测系统设计。

系统目标是构建一个多节点环境监测系统。多个环境监测节点通过 MQTT 协议发布环境数据，监控端订阅相关主题并显示各节点数据，重点体现 MQTT 的发布/订阅机制、主题设计、QoS 机制、节点掉线重连、消息延迟与到达率统计等网络通信内容。

## 项目信息

- 小组成员：胡艺瀚、孙博宇、韦煜城、曾家豪
- 指导老师：和洁、傅攀峰、刘若辰
- 课程名称：数据通信与网络技术
- 选题编号：题目 12
- 选题名称：基于 MQTT 的多节点环境监测系统设计

## 系统目标

- 至少实现 2 个环境监测节点，可先使用 PC 模拟节点，后续接入 ESP32 真实硬件节点。
- 每个节点采集或模拟一种环境数据，如温度、湿度、光照、噪声等。
- 搭建本地或云端 MQTT Broker。
- 设计清晰、可扩展的 MQTT 主题结构。
- 监控端能够订阅主题并显示节点编号、数据类型、数据值和上传时间。
- 对不同 QoS 等级、节点断开重连、消息延迟、消息到达率等进行测试和分析。

## 目录结构

```text
mqtt_env_monitor/
├─ README.md
├─ .gitignore
├─ docs/
│  ├─ course_materials/
│  │  ├─ 原始课程要求与模板/
│  │  └─ 课程要求摘要.md
│  ├─ project_outputs/
│  │  ├─ 项目日志.md
│  │  ├─ 课程设计报告/
│  │  ├─ 汇报PPT/
│  │  └─ 测试证据/
│  └─ team/
│     ├─ 项目要求说明.md
│     ├─ 会议记录.md
│     ├─ 专业知识汇总.md
│     ├─ GitHub使用方法.md
│     └─ daily/
├─ src/
│  ├─ broker/
│  ├─ simulated_nodes/
│  ├─ monitor/
│  ├─ server/
│  └─ common/
├─ hardware/
│  ├─ esp32_nodes/
│  ├─ wiring/
│  └─ README.md
├─ tests/
│  ├─ functional/
│  ├─ protocol/
│  └─ performance/
├─ captures/
│  ├─ wireshark/
│  └─ mqttx/
└─ scripts/
```

## 当前进度

| 时间 | 负责人 | 内容 |
| --- | --- | --- |
| 2026-06-08 15:44 | 胡艺瀚 | 完成项目目录规划、课程资料归档、README 初版和团队协作文档初始化。 |
| 2026-06-08 22:20 | 胡艺瀚 | 完成需求分析与设计指标初稿，明确应用场景、功能需求、性能指标和验证方式。 |

## 后续计划

1. 完成系统需求分析与总体方案设计。
2. 设计 MQTT 主题结构和消息数据格式。
3. 实现 PC 模拟节点、MQTT Broker 配置和监控端原型。
4. 编写功能测试、协议测试和性能测试记录。
5. 接入 ESP32 环境监测节点，采集真实环境数据。
6. 整理课程设计报告、汇报 PPT、抓包文件、日志和测试附件。

## GitHub 协作方式

- `main` 分支保存稳定版本。
- 每个功能、问题修复或文档更新建议创建独立分支。
- 使用 Issue 记录待办事项、问题和改进建议。
- 使用 Pull Request 合并分支，合并前说明修改内容和测试结果。
- 提交信息建议使用简洁格式，例如：

```text
docs: add course requirement summary
feat: add simulated mqtt node
fix: handle mqtt reconnect failure
test: add qos delivery test records
```
