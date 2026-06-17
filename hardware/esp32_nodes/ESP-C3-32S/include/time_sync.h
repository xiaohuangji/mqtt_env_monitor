#ifndef TIME_SYNC_H
#define TIME_SYNC_H

#include <Arduino.h>

void initTimeSync();

bool isTimeSynced();

String getBeijingTimestamp();

uint64_t getEpochMillis();

#endif