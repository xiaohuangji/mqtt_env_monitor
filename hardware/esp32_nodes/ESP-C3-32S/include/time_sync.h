#ifndef TIME_SYNC_H
#define TIME_SYNC_H

#include <Arduino.h>

// 初始化 NTP 时间同步
void initTimeSync();

// 判断时间是否已经同步成功
bool isTimeSynced();

// 获取北京时间 ISO 8601 格式时间戳
// 示例：2026-06-08T22:30:00+08:00
String getBeijingTimestamp();

#endif