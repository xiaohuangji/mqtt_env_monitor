#include "mqtt_message.h"
#include "config.h"

String uint64ToString(uint64_t value)
{
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%llu", (unsigned long long)value);
    return String(buffer);
}

String buildMqttTopic(const SensorData& data)
{
    String topic = "";

    topic += MQTT_TOPIC_PREFIX;
    topic += "/";
    topic += data.node_id;
    topic += "/";
    topic += data.data_type;

    return topic;
}

String buildCompactJsonPayload(const SensorData& data, uint64_t epochMillis)
{
    String json = "";

    json += "{";
    json += "\"n\":\"" + data.node_id + "\",";
    json += "\"d\":\"" + data.data_type + "\",";
    json += "\"v\":" + String(data.value, 2) + ",";
    json += "\"t\":" + uint64ToString(epochMillis) + ",";
    json += "\"s\":" + String(data.seq);
    json += "}";

    return json;
}