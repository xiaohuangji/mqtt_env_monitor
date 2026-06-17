#include "mqtt_message.h"

String buildMqttTopic(const SensorData& data)
{
    String topic = "";

    topic += "env_monitor";
    topic += "/";
    topic += data.node_id;
    topic += "/";
    topic += data.data_type;

    return topic;
}

String buildJsonPayload(const SensorData& data)
{
    String json = "";

    json += "{";
    json += "\"node_id\":\"" + data.node_id + "\",";
    json += "\"data_type\":\"" + data.data_type + "\",";
    json += "\"value\":" + String(data.value, 2) + ",";
    json += "\"unit\":\"" + data.unit + "\",";
    json += "\"timestamp\":\"" + data.timestamp + "\",";
    json += "\"seq\":" + String(data.seq);
    json += "}";

    return json;
}