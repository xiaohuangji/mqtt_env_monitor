#include "wifi_config.h"
#include "config.h"

#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <Preferences.h>

// =======================
// 全局对象
// =======================

WebServer configServer(WIFI_CONFIG_WEB_PORT);
DNSServer dnsServer;
Preferences preferences;

const byte DNS_PORT = 53;

// 是否正在运行 AP 配网页面
bool configPortalRunning = false;

// WiFi 状态监测变量
bool lastWiFiConnected = false;
bool reconnectTiming = false;

unsigned long disconnectStartMs = 0;
unsigned long lastReconnectTryMs = 0;

// 重连尝试间隔
#define WIFI_RECONNECT_INTERVAL_MS 5000


// =======================
// 打印 STA 模式下的 WiFi 基本信息
// 只在启动后第一次成功连接 WiFi 时调用一次
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
// 打印 AP 配网门户信息
// =======================
void printWiFiConfigPortalInfo()
{
    Serial.println();
    Serial.println("========== ESP32 WiFi Config Portal ==========");

    Serial.print("[WiFi] AP SSID: ");
    Serial.println(WIFI_CONFIG_AP_SSID);

    Serial.print("[WiFi] AP Password: ");
    Serial.println(WIFI_CONFIG_AP_PASSWORD);

    Serial.print("[WiFi] AP IP: ");
    Serial.println(WiFi.softAPIP());

    Serial.println("[WiFi] Config URL: http://192.168.4.1");
    Serial.println("[WiFi] Use phone or PC to connect this AP first.");
    Serial.println("==============================================");
}


// =======================
// 生成 WiFi 扫描列表
// =======================
String buildWiFiOptions()
{
    String options = "";

    int networkCount = WiFi.scanNetworks();

    if (networkCount <= 0)
    {
        options += "<option value=''>未扫描到 WiFi</option>";
        return options;
    }

    for (int i = 0; i < networkCount; i++)
    {
        String ssid = WiFi.SSID(i);
        int rssi = WiFi.RSSI(i);

        options += "<option value='";
        options += ssid;
        options += "'>";

        options += ssid;
        options += "  信号强度: ";
        options += String(rssi);
        options += " dBm";

        options += "</option>";
    }

    return options;
}


// =======================
// 构建 AP 配网页面
// =======================
String buildConfigPage()
{
    String html = "";

    html += "<!DOCTYPE html>";
    html += "<html>";
    html += "<head>";
    html += "<meta charset='UTF-8'>";
    html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
    html += "<title>ESP32 WiFi 配网</title>";

    html += "<style>";
    html += "body{font-family:Arial;background:#f5f5f5;margin:0;padding:20px;}";
    html += ".box{max-width:420px;margin:30px auto;background:white;padding:25px;border-radius:10px;box-shadow:0 2px 8px #ccc;}";
    html += "h2{text-align:center;}";
    html += "label{display:block;margin-top:15px;}";
    html += "input,select{width:100%;padding:10px;margin-top:6px;box-sizing:border-box;}";
    html += "button{width:100%;padding:12px;margin-top:20px;background:#0078d7;color:white;border:0;border-radius:5px;font-size:16px;}";
    html += ".clear{background:#cc3333;}";
    html += ".tip{font-size:14px;color:#666;margin-top:10px;line-height:1.5;}";
    html += "</style>";

    html += "</head>";
    html += "<body>";

    html += "<div class='box'>";
    html += "<h2>ESP32-C3 WiFi 配网</h2>";

    html += "<p class='tip'>";
    html += "当前处于 AP 配网模式。请填写需要连接的 WiFi，例如手机热点或路由器 WiFi。";
    html += "</p>";

    html += "<form action='/save' method='POST'>";

    html += "<label>选择扫描到的 WiFi</label>";
    html += "<select name='ssid_select'>";
    html += buildWiFiOptions();
    html += "</select>";

    html += "<label>或手动输入 WiFi 名称</label>";
    html += "<input type='text' name='ssid_manual' placeholder='例如：iPhone_Hotspot'>";

    html += "<label>WiFi 密码</label>";
    html += "<input type='password' name='password' placeholder='请输入 WiFi 密码'>";

    html += "<button type='submit'>保存并重启</button>";
    html += "</form>";

    html += "<form action='/clear' method='POST'>";
    html += "<button class='clear' type='submit'>清除已保存 WiFi</button>";
    html += "</form>";

    html += "<p class='tip'>";
    html += "如果需要更换其他手机热点，可以先清除已保存 WiFi，然后重新配网。";
    html += "</p>";

    html += "</div>";

    html += "</body>";
    html += "</html>";

    return html;
}


// =======================
// 处理首页
// =======================
void handleRoot()
{
    configServer.send(200, "text/html", buildConfigPage());
}


// =======================
// 保存 WiFi 信息
// =======================
void handleSave()
{
    String ssidSelect = configServer.arg("ssid_select");
    String ssidManual = configServer.arg("ssid_manual");
    String password = configServer.arg("password");

    String ssid = ssidManual;

    if (ssid.length() == 0)
    {
        ssid = ssidSelect;
    }

    if (ssid.length() == 0)
    {
        configServer.send(200, "text/html", "<meta charset='UTF-8'>SSID 不能为空，请返回重新填写。");
        return;
    }

    preferences.begin("wifi", false);
    preferences.putString("ssid", ssid);
    preferences.putString("password", password);
    preferences.end();

    String html = "";

    html += "<meta charset='UTF-8'>";
    html += "<h2>WiFi 信息已保存</h2>";
    html += "<p>ESP32 即将重启并尝试连接 WiFi：</p>";
    html += "<p><b>";
    html += ssid;
    html += "</b></p>";

    configServer.send(200, "text/html", html);

    delay(1500);
    ESP.restart();
}


// =======================
// 清除 WiFi 信息
// =======================
void handleClear()
{
    preferences.begin("wifi", false);
    preferences.clear();
    preferences.end();

    String html = "";

    html += "<meta charset='UTF-8'>";
    html += "<h2>已清除 WiFi 配置信息</h2>";
    html += "<p>ESP32 即将重启。</p>";

    configServer.send(200, "text/html", html);

    delay(1500);
    ESP.restart();
}


// =======================
// 未匹配路径统一跳转首页
// 方便手机自动弹出配网页面
// =======================
void handleNotFound()
{
    configServer.sendHeader("Location", "/", true);
    configServer.send(302, "text/plain", "");
}


// =======================
// 尝试连接已保存 WiFi
// =======================
bool connectSavedWiFi()
{
    preferences.begin("wifi", true);
    String ssid = preferences.getString("ssid", "");
    String password = preferences.getString("password", "");
    preferences.end();

    if (ssid.length() == 0)
    {
        Serial.println("[WiFi] No saved WiFi config.");
        return false;
    }

    Serial.print("[WiFi] Try to connect saved WiFi: ");
    Serial.println(ssid);

    WiFi.disconnect(true);
    delay(300);

    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.persistent(false);

    WiFi.begin(ssid.c_str(), password.c_str());

    unsigned long startTime = millis();

    while (WiFi.status() != WL_CONNECTED)
    {
        delay(500);
        Serial.print(".");

        if (millis() - startTime > WIFI_CONNECT_TIMEOUT_MS)
        {
            Serial.println();
            Serial.println("[WiFi] Connect timeout.");
            return false;
        }
    }

    unsigned long connectCostMs = millis() - startTime;

    Serial.println();
    Serial.println("[WiFi] Connected successfully.");
    Serial.print("[WiFi] Initial connect cost: ");
    Serial.print(connectCostMs);
    Serial.println(" ms");

    lastWiFiConnected = true;
    reconnectTiming = false;

    // 只在启动后第一次连接到热点成功时打印一次完整 WiFi 信息
    printWiFiBasicInfo();

    return true;
}


// =======================
// 启动 AP 配网门户
// =======================
void startConfigPortal()
{
    Serial.println("[WiFi] Start AP config portal.");

    WiFi.disconnect(true);
    delay(500);

    // 当前只做网页配网，AP 模式更稳定
    WiFi.mode(WIFI_AP);

    bool apStarted = WiFi.softAP(WIFI_CONFIG_AP_SSID, WIFI_CONFIG_AP_PASSWORD);

    if (apStarted)
    {
        Serial.println("[WiFi] AP started.");
    }
    else
    {
        Serial.println("[WiFi] AP start failed.");
    }

    dnsServer.start(DNS_PORT, "*", WiFi.softAPIP());

    configServer.on("/", HTTP_GET, handleRoot);
    configServer.on("/save", HTTP_POST, handleSave);
    configServer.on("/clear", HTTP_POST, handleClear);
    configServer.onNotFound(handleNotFound);

    configServer.begin();

    configPortalRunning = true;

    printWiFiConfigPortalInfo();
}


// =======================
// 初始化 WiFi 配网模块
// =======================
void initWiFiConfig()
{
    Serial.println("[WiFi] Init WiFi config module.");

    bool connected = connectSavedWiFi();

    if (!connected)
    {
        startConfigPortal();
    }
}


// =======================
// 处理 WiFi 状态变化与断线重连
// =======================
void handleWiFiReconnectMonitor()
{
    // 配网门户运行时，不做 STA 自动重连监测
    if (configPortalRunning)
    {
        return;
    }

    bool currentConnected = WiFi.status() == WL_CONNECTED;
    unsigned long now = millis();

    // 之前连接，现在断开：记录断开起始时间
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
        Serial.println("[WiFi] Sensor collection will be paused until WiFi reconnects.");
    }

    // 断开状态下，定时尝试重连
    if (!currentConnected && reconnectTiming)
    {
        if (now - lastReconnectTryMs >= WIFI_RECONNECT_INTERVAL_MS)
        {
            lastReconnectTryMs = now;

            Serial.println("[WiFi] Trying to reconnect...");
            WiFi.reconnect();
        }
    }

    // 之前断开，现在重新连接成功：计算恢复耗时
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
// loop 中处理配网页面请求、WiFi 状态监测
// =======================
void handleWiFiConfig()
{
    if (configPortalRunning)
    {
        dnsServer.processNextRequest();
        configServer.handleClient();
    }

    handleWiFiReconnectMonitor();
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
        status += ", rssi=";
        status += String(WiFi.RSSI());
        status += "dBm";

        return status;
    }

    if (configPortalRunning)
    {
        return "config_portal_running";
    }

    if (reconnectTiming)
    {
        return "reconnecting";
    }

    return "disconnected";
}


// =======================
// 清除已保存 WiFi 信息
// =======================
void clearSavedWiFiConfig()
{
    preferences.begin("wifi", false);
    preferences.clear();
    preferences.end();
}