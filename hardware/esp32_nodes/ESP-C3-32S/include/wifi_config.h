#ifndef WIFI_CONFIG_H
#define WIFI_CONFIG_H

#include <Arduino.h>

// 初始化 WiFi 配网模块
void initWiFiConfig();

// 在 loop 中处理 WiFi 状态监测和断线重连
void handleWiFiConfig();

// 判断 WiFi 是否已经连接
bool isWiFiConnected();

// 获取当前 WiFi 状态文本
String getWiFiStatusText();

// 清除已保存 WiFi 信息
void clearSavedWiFiConfig();

// 打印 WiFi 基本信息
void printWiFiBasicInfo();

#endif