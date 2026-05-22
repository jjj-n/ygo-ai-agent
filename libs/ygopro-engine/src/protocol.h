#pragma once

#include "bridge.h"
#include <nlohmann/json.hpp>
#include <string>

using json = nlohmann::json;

// JSON protocol handler for stdin/stdout communication
class ProtocolHandler {
public:
    ProtocolHandler(DuelBridge& bridge);

    // Process a single JSON command, return JSON response
    json handle_command(const json& cmd);

    // Command handlers
    json cmd_init(const json& params);
    json cmd_get_state(const json& params);
    json cmd_get_legal_moves(const json& params);
    json cmd_do_move(const json& params);
    json cmd_respond_chain(const json& params);
    json cmd_draw(const json& params);
    json cmd_reset(const json& params);
    json cmd_query_field(const json& params);

private:
    DuelBridge& bridge_;

    // Cached messages from last process cycle (needed because get_messages() clears the buffer)
    std::vector<uint8_t> cached_messages_;

    // Track the last prompt type for correct response encoding
    uint8_t last_prompt_type_ = 0;

    // Helper: serialize game state to JSON
    json serialize_state();

    // Helper: serialize raw query data to JSON
    json serialize_query_data(const std::vector<uint8_t>& data);

    // Helper: parse message buffer into events
    json parse_messages(const std::vector<uint8_t>& buf);

    // Helper: parse legal moves from message buffer
    json parse_legal_moves(const std::vector<uint8_t>& buf);
};
