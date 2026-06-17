#include "wifi_config.h"
#include "config.h"

#include <WiFi.h>
#include <WiFiManager.h>

// =======================
// WiFiManager 对象
// =======================

WiFiManager wm;

// =======================
// WiFi 状态监测变量
// =======================

bool lastWiFiConnected = false;
bool reconnectTiming = false;

unsigned long disconnectStartMs = 0;
unsigned long lastReconnectTryMs = 0;

// 断网后，每 5 秒尝试重连一次旧热点
#define WIFI_RECONNECT_INTERVAL_MS 5000

// 断网后，如果 30 秒还没有重连成功，则重新打开配网热点
#define WIFI_RECONFIG_TIMEOUT_MS 10000


// =======================
// 打印 WiFi 基本信息
// 只在首次连接成功或重新配网连接成功时调用
// =======================
void printWiFiBasicInfo()
{
    Serial.println();
    Serial.println("========== ESP32 WiFi Basic Info ==========");

    if (WiFi.status() == WL_CONNECTED)
    {
        Serial.println("[WiFi] Mode: STA");
        Serial.println("[WiFi] Status: Connected");

        Serial.print("[WiFi] SSID: ");
        Serial.println(WiFi.SSID());

        Serial.print("[WiFi] IP Address: ");
        Serial.println(WiFi.localIP());

        Serial.print("[WiFi] Gateway: ");
        Serial.println(WiFi.gatewayIP());

        Serial.print("[WiFi] Subnet Mask: ");
        Serial.println(WiFi.subnetMask());

        Serial.print("[WiFi] DNS: ");
        Serial.println(WiFi.dnsIP());

        Serial.print("[WiFi] MAC Address: ");
        Serial.println(WiFi.macAddress());

        Serial.print("[WiFi] RSSI: ");
        Serial.print(WiFi.RSSI());
        Serial.println(" dBm");
    }
    else
    {
        Serial.println("[WiFi] Status: Not connected");

        Serial.print("[WiFi] MAC Address: ");
        Serial.println(WiFi.macAddress());
    }

    Serial.println("===========================================");
}


// =======================
// 初始化 WiFi 配网模块
// WiFiManager 实现：
// 1. 自动连接已保存 WiFi
// 2. 没有保存 WiFi 或连接失败时自动开启 AP 配网门户
// 3. 手机/电脑连接 ESP32C3_Config 后访问 http://192.168.4.1 配网
// 4. 保存 WiFi 信息到 Flash，下次自动连接
// =======================
void initWiFiConfig()
{
    Serial.println();
    Serial.println("[WiFi] Init WiFiManager config module.");

    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.persistent(true);

    // 清理当前连接状态，但不清除 Flash 中已保存的 WiFi 信息
    WiFi.disconnect(false);
    delay(300);

    // 已保存 WiFi 的连接超时时间，单位：秒
    wm.setConnectTimeout(WIFI_CONNECT_TIMEOUT_MS / 1000);

    // 配网页面超时时间，单位：秒
    // 如果 180 秒内没有完成配网，autoConnect 会退出
    wm.setConfigPortalTimeout(180);

    // 设置配网页面标题
    wm.setTitle("ESP32-C3 WiFi Config");

    Serial.println("[WiFi] Try saved WiFi first.");
    Serial.println("[WiFi] If failed, start AP config portal.");
    Serial.print("[WiFi] AP SSID: ");
    Serial.println(WIFI_CONFIG_AP_SSID);
    Serial.print("[WiFi] AP Password: ");
    Serial.println(WIFI_CONFIG_AP_PASSWORD);
    Serial.println("[WiFi] Config URL: http://192.168.4.1");

    unsigned long startTime = millis();

    bool connected = wm.autoConnect(WIFI_CONFIG_AP_SSID, WIFI_CONFIG_AP_PASSWORD);

    unsigned long costMs = millis() - startTime;

    if (connected)
    {
        Serial.println();
        Serial.println("[WiFi] Connected successfully.");
        Serial.print("[WiFi] Connect cost: ");
        Serial.print(costMs);
        Serial.println(" ms");

        lastWiFiConnected = true;
        reconnectTiming = false;

        printWiFiBasicInfo();
    }
    else
    {
        Serial.println();
        Serial.println("[WiFi] WiFiManager autoConnect failed or timeout.");
        Serial.println("[WiFi] Device will stay disconnected.");
        Serial.println("[WiFi] You can reset WiFi settings and try again.");

        lastWiFiConnected = false;
        reconnectTiming = false;
    }
}


// =======================
// 处理 WiFi 状态变化与断线重连
// 逻辑：
// 1. 正常连接时，持续监测 WiFi 状态
// 2. 如果热点关闭导致断网，先尝试重连旧热点
// 3. 如果 10 秒还没连上，自动重新开启 ESP32C3_Config 配网热点
// 4. 重新填写新的热点信息后，ESP32 自动连接新热点
// =======================
void handleWiFiConfig()
{
    bool currentConnected = WiFi.status() == WL_CONNECTED;
    unsigned long now = millis();

    // 情况 1：之前已连接，现在断开
    if (lastWiFiConnected && !currentConnected)
    {
        lastWiFiConnected = false;
        reconnectTiming = true;
        disconnectStartMs = now;
        lastReconnectTryMs = 0;

        Serial.println();
        Serial.println("[WiFi] Connection lost.");
        Serial.print("[WiFi] Disconnect start ms: ");
        Serial.print(disconnectStartMs);
        Serial.println(" ms");
        Serial.println("[WiFi] Sensor collection and MQTT publish will be paused.");
        Serial.println("[WiFi] Will try to reconnect saved WiFi first.");
        Serial.println("[WiFi] If reconnect timeout, config portal will start again.");
    }

    // 情况 2：断开状态下，定时尝试重连旧热点
    if (!currentConnected && reconnectTiming)
    {
        if (now - lastReconnectTryMs >= WIFI_RECONNECT_INTERVAL_MS)
        {
            lastReconnectTryMs = now;

            Serial.println("[WiFi] Trying to reconnect saved WiFi...");
            WiFi.reconnect();
        }

        // 情况 3：断开超过 0 秒还没有重连成功，重新开启 WiFiManager 配网门户
        if (now - disconnectStartMs >= WIFI_RECONFIG_TIMEOUT_MS)
        {
            Serial.println();
            Serial.println("[WiFi] Reconnect timeout.");
            Serial.println("[WiFi] Start WiFiManager config portal again.");
            Serial.print("[WiFi] AP SSID: ");
            Serial.println(WIFI_CONFIG_AP_SSID);
            Serial.print("[WiFi] AP Password: ");
            Serial.println(WIFI_CONFIG_AP_PASSWORD);
            Serial.println("[WiFi] Please connect to ESP32 AP and open http://192.168.4.1");
            Serial.println("[WiFi] You can now configure a new hotspot.");

            reconnectTiming = false;

            // 停止当前 STA 连接尝试，但不清除 Flash 中保存的 WiFi 信息
            WiFi.disconnect(false);
            delay(300);

            // 重新开启 WiFiManager 配网门户
            // 注意：startConfigPortal 是阻塞式，用户完成配网或超时后才会继续往下运行
            bool connected = wm.startConfigPortal(WIFI_CONFIG_AP_SSID, WIFI_CONFIG_AP_PASSWORD);

            if (connected)
            {
                Serial.println();
                Serial.println("[WiFi] New WiFi configured and connected successfully.");

                lastWiFiConnected = true;
                reconnectTiming = false;

                printWiFiBasicInfo();
            }
            else
            {
                Serial.println();
                Serial.println("[WiFi] Config portal timeout or failed.");
                Serial.println("[WiFi] Device remains disconnected.");
                Serial.println("[WiFi] You can reset the board or wait for another config attempt.");

                lastWiFiConnected = false;
                reconnectTiming = false;
            }
        }
    }

    // 情况 4：之前断开，现在重新连接成功
    if (!lastWiFiConnected && currentConnected)
    {
        lastWiFiConnected = true;

        if (reconnectTiming)
        {
            unsigned long reconnectCostMs = now - disconnectStartMs;

            Serial.println();
            Serial.println("[WiFi] Reconnected successfully.");
            Serial.print("[WiFi] Reconnect cost: ");
            Serial.print(reconnectCostMs);
            Serial.println(" ms");

            Serial.print("[WiFi] Current SSID: ");
            Serial.println(WiFi.SSID());

            Serial.print("[WiFi] Current IP: ");
            Serial.println(WiFi.localIP());

            reconnectTiming = false;
        }
        else
        {
            Serial.println("[WiFi] Connected.");
        }
    }
}


// =======================
// 判断 WiFi 是否连接
// =======================
bool isWiFiConnected()
{
    return WiFi.status() == WL_CONNECTED;
}


// =======================
// 获取 WiFi 状态文本
// =======================
String getWiFiStatusText()
{
    if (isWiFiConnected())
    {
        String status = "connected, ssid=";
        status += WiFi.SSID();
        status += ", ip=";
        status += WiFi.localIP().toString();
        status += ", gateway=";
        status += WiFi.gatewayIP().toString();
        status += ", rssi=";
        status += String(WiFi.RSSI());
        status += "dBm";

        return status;
    }

    if (reconnectTiming)
    {
        return "reconnecting";
    }

    return "disconnected";
}


// =======================
// 清除已保存 WiFi 信息
// 用于主动更换 Windows 移动热点时重新配网
// 用法：
// 在 main.cpp 的 setup() 中临时调用 clearSavedWiFiConfig();
// 上传运行一次后再注释掉
// =======================
void clearSavedWiFiConfig()
{
    Serial.println("[WiFi] Reset saved WiFi settings.");

    wm.resetSettings();

    WiFi.disconnect(true, true);
    delay(500);

    lastWiFiConnected = false;
    reconnectTiming = false;

    Serial.println("[WiFi] Saved WiFi settings cleared.");
}