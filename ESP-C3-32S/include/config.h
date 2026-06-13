#ifndef CONFIG_H
#define CONFIG_H

// =======================
// 节点配置
// =======================
#define NODE_ID "node03"

// =======================
// 传感器引脚配置
// ESP32-C3 建议优先使用 GPIO0、GPIO1、GPIO2 作为 ADC 输入
// =======================
#define MQ2_PIN   0
#define RAIN_PIN  1
#define SOIL_PIN  2

// =======================
// 采集周期
// =======================
#define COLLECT_INTERVAL_MS 3000

#endif