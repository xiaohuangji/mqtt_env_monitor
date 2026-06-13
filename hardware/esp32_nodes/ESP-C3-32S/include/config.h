#ifndef CONFIG_H
#define CONFIG_H

// =======================
// 节点配置
// =======================
#define NODE_ID "node03"

// =======================
// 传感器引脚配置
// =======================

// GPIO0：DHT11 温湿度传感器
#define DHT11_PIN 0

// GPIO1：预留光照传感器接口
#define LIGHT_PIN 1

// GPIO2：预留噪声检测模块接口
#define NOISE_PIN 2

// GPIO3：土壤湿度检测模块
#define SOIL_PIN 3

// GPIO4：MQ-2 气体传感器模块
#define MQ2_PIN 4

// =======================
// 采集周期配置
// WiFi 连接成功后，每 30 秒采集并输出一次
// =======================
#define COLLECT_INTERVAL_MS 30000

// =======================
// WiFi 配网网页门户配置
// =======================
#define WIFI_CONFIG_AP_SSID "ESP32C3_Config"
#define WIFI_CONFIG_AP_PASSWORD "12345678"
#define WIFI_CONNECT_TIMEOUT_MS 15000
#define WIFI_CONFIG_WEB_PORT 80

// =======================
// NTP 北京时间配置
// =======================
#define NTP_SERVER_1 "ntp.aliyun.com"
#define NTP_SERVER_2 "pool.ntp.org"

// 北京时间 UTC+8
#define GMT_OFFSET_SEC 28800

// 中国不使用夏令时
#define DAYLIGHT_OFFSET_SEC 0

#endif