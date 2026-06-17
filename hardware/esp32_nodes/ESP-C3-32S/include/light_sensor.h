#ifndef LIGHT_SENSOR_H
#define LIGHT_SENSOR_H

#include <Arduino.h>
#include "sensor_data.h"

// 初始化 BH1750 光照度传感器
void initLightSensor();

// 读取 BH1750 光照度数据
SensorData readLightSensor(const String& nodeId, const String& timestamp, unsigned long seq);

#endif