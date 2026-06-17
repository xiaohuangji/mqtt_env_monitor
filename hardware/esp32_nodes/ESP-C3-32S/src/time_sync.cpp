#include "time_sync.h"
#include "config.h"

#include <time.h>
#include <sys/time.h>

bool timeSynced = false;

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
        Serial.print("[Time] Beijing time: ");
        Serial.println(getBeijingTimestamp());

        Serial.print("[Time] Epoch ms: ");
        Serial.println((unsigned long)getEpochMillis());
    }
    else
    {
        timeSynced = false;
        Serial.println("[Time] NTP sync failed.");
    }
}

bool isTimeSynced()
{
    return timeSynced;
}

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

uint64_t getEpochMillis()
{
    struct timeval tv;
    gettimeofday(&tv, nullptr);

    uint64_t epochMillis = (uint64_t)tv.tv_sec * 1000ULL + tv.tv_usec / 1000ULL;

    return epochMillis;
}