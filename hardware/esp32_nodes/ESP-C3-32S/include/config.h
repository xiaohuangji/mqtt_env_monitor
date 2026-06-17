#ifndef CONFIG_H
#define CONFIG_H

// =======================
// 节点基础配置
// =======================

// 远程联调临时节点 ID
#define NODE_ID "esp32hyh0614"


// =======================
// ESP32-C3 引脚配置
// =======================

// DHT11 温湿度传感器
// 原 GPIO0 读取不稳定，已更换为 GPIO5
#define DHT11_PIN 5

// GY-302 / BH1750 光照度传感器 I2C 引脚
// SDA 接 GPIO1
// SCL 接 GPIO2
#define BH1750_SDA_PIN 1
#define BH1750_SCL_PIN 2

// GPIO3：FC-28 土壤湿度传感器
#define SOIL_PIN 3

// GPIO4：MQ-2 气体传感器
#define MQ2_PIN 4


// =======================
// 数据采集配置
// =======================

// 每 30 秒采集并发布一次数据
#define COLLECT_INTERVAL_MS 30000


// =======================
// WiFiManager 配网配置
// =======================

#define WIFI_CONFIG_AP_SSID "ESP32C3_Config"
#define WIFI_CONFIG_AP_PASSWORD "12345678"
#define WIFI_CONNECT_TIMEOUT_MS 15000
#define WIFI_CONFIG_WEB_PORT 80


// =======================
// NTP 时间同步配置
// =======================

#define NTP_SERVER_1 "ntp.aliyun.com"
#define NTP_SERVER_2 "pool.ntp.org"

#define GMT_OFFSET_SEC 28800
#define DAYLIGHT_OFFSET_SEC 0


// =======================
// MQTT 配置
// =======================

// 远程联调公网 Broker
#define MQTT_BROKER_HOST "123.56.225.40"
#define MQTT_BROKER_PORT 1883

#define MQTT_KEEPALIVE_SEC 30

#define MQTT_CLIENT_ID "esp32hyh0614_client"

#define MQTT_TOPIC_PREFIX "env_monitor"

#define MQTT_QOS_LEVEL 1

#endif