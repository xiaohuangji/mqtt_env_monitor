#ifndef MQTT_CLIENT_H
#define MQTT_CLIENT_H

#include <Arduino.h>
#include "sensor_data.h"

// 初始化 MQTT 客户端
void initMqttClient();

// 在 loop 中维护 MQTT 连接
void handleMqttClient();

// 判断 MQTT 是否连接
bool isMqttConnected();

// 连接 MQTT Broker
void connectMqttBroker();

// QoS 1 发布传感器数据
bool publishSensorDataQoS1(const SensorData& data);

// 兼容可能写成 Qos1 的函数名
bool publishSensorDataQos1(const SensorData& data);

#endif