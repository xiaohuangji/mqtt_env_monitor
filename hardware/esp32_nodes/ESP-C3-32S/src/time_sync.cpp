#include "time_sync.h"
#include "config.h"

#include <time.h>

bool timeSynced = false;

// =======================
// 初始化 NTP 时间同步
// 必须在 WiFi 连接成功后调用
// =======================
void initTimeSync()
{
    Serial.println("[Time] Start NTP time sync...");

    configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER_1, NTP_SERVER_2);

    struct tm timeInfo;
    int retryCount = 0;

    while (!getLocalTime(&timeInfo) && retryCount < 10)
    {
        Serial.print("[Time] Waiting for NTP sync...");
        Serial.println(retryCount + 1);
        delay(1000);
        retryCount++;
    }

    if (retryCount < 10)
    {
        timeSynced = true;
        Serial.println("[Time] NTP sync success.");
        Serial.print("[Time] Current Beijing time: ");
        Serial.println(getBeijingTimestamp());
    }
    else
    {
        timeSynced = false;
        Serial.println("[Time] NTP sync failed.");
    }
}

// =======================
// 判断时间是否同步成功
// =======================
bool isTimeSynced()
{
    return timeSynced;
}

// =======================
// 获取北京时间 ISO 8601 时间戳
// 格式：2026-06-08T22:30:00+08:00
// =======================
String getBeijingTimestamp()
{
    struct tm timeInfo;

    if (!getLocalTime(&timeInfo))
    {
        return "time_not_synced";
    }

    char timeBuffer[32];

    strftime(timeBuffer, sizeof(timeBuffer), "%Y-%m-%dT%H:%M:%S+08:00", &timeInfo);

    return String(timeBuffer);
}